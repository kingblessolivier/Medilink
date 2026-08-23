"""USSD routing.

The properties that matter on a feature phone:
  - the reply is never blank, whatever goes wrong
  - every screen fits, in every language
  - "my queue" costs one step
  - a wait time is never invented
  - the webhook fails closed
"""

from datetime import time, timedelta

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.facilities.models import Facility, FacilityService, OpeningHours, ServiceType
from apps.gateway.ussd import MAX_USSD_CHARS, UssdRouter
from apps.patients.models import Patient
from apps.queueing.models import QueueEntry
from apps.queueing.testing import make_service_time_stat
from apps.scheduling.models import ScheduleTemplate

USSD = "/api/v1/gateway/ussd"
PHONE = "+250788111222"
SECRET = "test-ussd-secret"


@pytest.fixture(autouse=True)
def gateway_secret(settings):
    """The webhook fails closed, so every test must authenticate."""
    settings.USSD_SHARED_SECRET = SECRET
    settings.USSD_ALLOWED_IPS = []


@pytest.fixture
def general(db):
    return ServiceType.objects.create(
        code="general_consultation",
        name_en="General consultation",
        name_rw="Kwivuza rusange",
        name_fr="Consultation generale",
        sort_order=10,
    )


@pytest.fixture
def facility(db, general):
    facility = Facility.objects.create(
        name="Kimironko Health Centre",
        slug="kimironko-hc",
        ownership="public",
        level="health_centre",
        district="Gasabo",
        location=Point(30.1122, -1.9481, srid=4326),
        verified_at=timezone.now(),
        reports_queue=True,
    )
    for weekday in range(7):
        OpeningHours.objects.create(
            facility=facility,
            weekday=weekday,
            opens_at=time(0, 0),
            closes_at=time(23, 59),
        )
    FacilityService.objects.create(
        facility=facility, service_type=general, available=True
    )
    return facility


@pytest.fixture
def patient(db):
    return Patient.objects.create(phone=PHONE, district="Gasabo")


def post(client, text, phone=PHONE, session="s1", secret=SECRET, **extra):
    return client.post(
        USSD,
        {
            "sessionId": session,
            "phoneNumber": phone,
            "serviceCode": "*384*1#",
            "text": text,
        },
        HTTP_X_GATEWAY_SECRET=secret,
        **extra,
    )


def body(response) -> str:
    return response.content.decode()


# --------------------------------------------------------------------------
# The webhook fails closed
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_wrong_secret_is_refused(client):
    """An unauthenticated USSD endpoint would let anyone act as any phone
    number: read a stranger position in a queue, or book in their name."""
    assert post(client, "", secret="guess").status_code == 403


@pytest.mark.django_db
def test_a_missing_secret_is_refused(client):
    response = client.post(
        USSD, {"sessionId": "s1", "phoneNumber": PHONE, "text": ""}
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_an_unconfigured_gateway_refuses_everything(client, settings):
    """Fail closed, not open - including in development."""
    settings.USSD_SHARED_SECRET = ""
    assert post(client, "").status_code == 403


@pytest.mark.django_db
def test_a_rejection_is_never_a_500(client, settings):
    """The aggregator logs our status code; a stack trace in their dashboard
    helps nobody."""
    settings.USSD_SHARED_SECRET = ""

    response = post(client, "")

    assert response.status_code == 403
    assert b"Traceback" not in response.content


@pytest.mark.django_db
def test_ip_allowlist_is_enforced_when_set(client, settings):
    settings.USSD_ALLOWED_IPS = ["203.0.113.0/24"]

    assert post(client, "").status_code == 403
    assert post(client, "", REMOTE_ADDR="203.0.113.7").status_code == 200


# --------------------------------------------------------------------------
# Never blank
# --------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "text,prefix",
    [
        ("", "CON"),  # main menu
        ("3", "END"),  # my queue - one step
        ("4", "CON"),  # insurance menu
        ("5", "CON"),  # language menu
        ("9", "END"),  # invalid choice, handled gracefully
        ("abc", "END"),  # nonsense
        ("1*99", "END"),  # out-of-range submenu choice
    ],
)
def test_every_path_returns_a_usable_reply(client, text, prefix):
    response = post(client, text)

    assert response.status_code == 200
    assert body(response).startswith(prefix)
    assert len(body(response)) > 4  # never just "END " with nothing after it


@pytest.mark.django_db
def test_backend_failure_never_returns_a_blank_screen(client, monkeypatch):
    """A traceback reaching the aggregator shows the patient a dead phone."""

    def boom(self, text):
        raise RuntimeError("database on fire")

    monkeypatch.setattr(UssdRouter, "handle", boom)

    response = post(client, "")

    assert response.status_code == 200
    assert body(response).startswith("END ")
    assert len(body(response)) > 10


@pytest.mark.django_db
def test_unreadable_phone_number_is_handled(client):
    response = post(client, "", phone="not-a-number")

    assert response.status_code == 200
    assert body(response).startswith("END ")


@pytest.mark.django_db
def test_content_type_is_plain_text(client):
    """The aggregator reads plain text; JSON renders as literal braces."""
    assert post(client, "")["Content-Type"].startswith("text/plain")


# --------------------------------------------------------------------------
# Screen budget
# --------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("text", ["", "1", "1*1", "2", "3", "4", "5"])
def test_no_screen_overflows(client, facility, patient, text):
    payload = body(post(client, text))[4:]  # strip CON/END

    assert len(payload) <= MAX_USSD_CHARS, f"{text!r} produced {len(payload)} chars"


# --------------------------------------------------------------------------
# My queue - one step
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_my_queue_is_reachable_in_one_step(client, facility, general, patient):
    QueueEntry.objects.create(
        facility=facility, service_type=general, patient=patient, ticket_code="G-007"
    )

    response = post(client, "3")

    assert body(response).startswith("END ")
    assert "1" in body(response)  # a position is shown


@pytest.mark.django_db
def test_my_queue_when_not_waiting(client, patient):
    assert body(post(client, "3")).startswith("END ")


@pytest.mark.django_db
def test_my_queue_never_invents_a_wait(client, facility, general, patient):
    """No statistics behind it, so the screen must not carry minutes at all."""
    QueueEntry.objects.create(
        facility=facility, service_type=general, patient=patient, ticket_code="G-007"
    )

    assert "min" not in body(post(client, "3")).lower()


@pytest.mark.django_db
def test_my_queue_shows_minutes_once_statistics_exist(
    client, facility, general, patient
):
    make_service_time_stat(
        facility,
        general,
        median=9.0,
        samples=120,
    )
    QueueEntry.objects.create(
        facility=facility,
        service_type=general,
        walk_in_name="Ahead",
        joined_at=timezone.now() - timedelta(minutes=10),
        ticket_code="G-001",
    )
    QueueEntry.objects.create(
        facility=facility, service_type=general, patient=patient, ticket_code="G-002"
    )

    text = body(post(client, "3"))

    assert "2" in text  # position
    assert "9" in text  # one person ahead x 9 minutes


# --------------------------------------------------------------------------
# Nearby
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_returning_users_skip_the_district_screen(client, facility, general, patient):
    """`patient.district` is set, so "1" goes straight to the service menu.

    USSD sessions are billed per step, so this is a cost saving as well as a
    convenience.
    """
    response = post(client, "1")

    assert body(response).startswith("CON ")
    assert "Kwivuza" in body(response)  # service menu, not the district menu


@pytest.mark.django_db
def test_new_users_are_asked_for_their_district(client, facility, general):
    assert "Gasabo" in body(post(client, "1", phone="+250788999000"))


@pytest.mark.django_db
def test_district_is_remembered_after_the_first_session(client, facility, general):
    new_phone = "+250788999000"
    Patient.objects.create(phone=new_phone)

    post(client, "1*1", phone=new_phone)  # choose Gasabo

    assert Patient.objects.get(phone=new_phone).district == "Gasabo"


@pytest.mark.django_db
def test_nearby_lists_facilities_in_the_district(client, facility, general, patient):
    response = post(client, "1*1")

    assert body(response).startswith("END ")
    assert "Kimironko HC" in body(response)  # shortened to fit


@pytest.mark.django_db
def test_nearby_with_no_facilities(client, general, patient):
    assert body(post(client, "1*1")).startswith("END ")


# --------------------------------------------------------------------------
# Booking
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_booking_requires_a_known_patient(client, facility, general):
    assert body(post(client, "2", phone="+250788999000")).startswith("END ")


@pytest.mark.django_db
def test_booking_walks_through_facility_and_slot(client, facility, general, patient):
    for weekday in range(7):
        ScheduleTemplate.objects.create(
            facility=facility,
            service_type=general,
            weekday=weekday,
            start_time=time(8, 0),
            end_time=time(12, 0),
            slot_minutes=15,
            capacity_per_slot=2,
        )

    # 2 -> service -> facility -> slot
    assert body(post(client, "2")).startswith("CON ")
    assert body(post(client, "2*1")).startswith("CON ")
    assert body(post(client, "2*1*1")).startswith("CON ")

    final = body(post(client, "2*1*1*1"))
    assert final.startswith("END ")

    from apps.scheduling.models import Appointment

    appointment = Appointment.objects.get()
    assert appointment.booked_via == Appointment.BookedVia.USSD
    assert appointment.reference in final


@pytest.mark.django_db
def test_expired_session_state_restarts_gracefully(client, facility, general, patient):
    """A stale session must produce a readable message, not a crash."""
    from apps.gateway.session import clear_state

    post(client, "2*1")
    clear_state("s1")

    response = post(client, "2*1*1*1")

    assert response.status_code == 200
    assert body(response).startswith("END ")


# --------------------------------------------------------------------------
# Insurance and language
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_setting_insurance(client, patient, db):
    from apps.insurance.models import Insurer

    Insurer.objects.create(code="mutuelle", name="Mutuelle de Sante", sort_order=10)

    response = post(client, "4*1")

    assert body(response).startswith("END ")
    patient.refresh_from_db()
    assert patient.insurer.code == "mutuelle"


@pytest.mark.django_db
def test_setting_language_changes_later_screens(client, patient):
    post(client, "5*2")  # English

    patient.refresh_from_db()
    assert patient.language == "en"
    assert "My queue" in body(post(client, ""))


@pytest.mark.django_db
def test_language_menu_is_offered_to_unknown_callers(client):
    assert body(post(client, "5", phone="+250788999000")).startswith("CON ")


@pytest.mark.django_db
def test_an_invalid_district_does_not_trap_the_caller(client, facility, general):
    """Regression: re-showing the menu on a bad choice looped forever.

    USSD input is append-only. The bad digit stays in `text`, so a re-prompt
    reads the same bad digit again on the next request and the caller can
    never advance - they have to hang up and redial. End the session with a
    clear message instead.
    """
    new_phone = "+250788999000"

    first = post(client, "1*99", phone=new_phone)
    assert body(first).startswith("END ")

    # Whatever they press next, they are not stuck on the district screen.
    second = post(client, "1*99*1", phone=new_phone)
    assert body(second).startswith("END ")
    assert "Gasabo" not in body(second)


# --------------------------------------------------------------------------
# Name shortening
# --------------------------------------------------------------------------


def test_facility_names_are_abbreviated_not_sliced():
    from apps.gateway.ussd import short_name

    assert short_name("Kimironko Health Centre") == "Kimironko HC"
    assert short_name("Masaka District Hospital") == "Masaka DH"
    assert short_name("Baho International Hospital") == "Baho Intl H"


def test_long_names_trim_on_a_word_boundary():
    """A hard slice produces 'Croix du Sud Hospita', which a patient has to
    decode rather than read."""
    from apps.gateway.ussd import short_name

    result = short_name("Croix du Sud Hospital")

    assert len(result) <= 20
    assert not result.endswith(" ")
    # Never ends mid-word.
    assert result.split()[-1] in "Croix du Sud Hosp".split()


def test_a_single_unbroken_word_is_still_truncated():
    from apps.gateway.ussd import short_name

    result = short_name("Averyveryverylongsinglewordname")

    assert result
    assert len(result) <= 20
