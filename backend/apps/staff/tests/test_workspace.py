"""The facility workspace: appointment list, transitions, and reports.

Two things are being protected here. Facility scoping, because one missing
filter shows another clinic's patients. And the honesty of the reports, because
a manager will act on a median wait whether or not there is enough data behind
it - so an under-sampled median must come back null, not zero.
"""

from datetime import datetime, time, timedelta

import pytest
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient

from apps.facilities.models import Facility, OpeningHours, ServiceType
from apps.patients.models import Patient, PatientAccessLog
from apps.queueing.models import QueueEntry
from apps.scheduling.models import Appointment
from apps.staff.models import StaffMember

APPOINTMENTS = "/api/v1/staff/appointments"
REPORTS = "/api/v1/staff/reports"


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def general(db):
    return ServiceType.objects.create(
        code="general_consultation", name_en="General", name_rw="x", name_fr="x"
    )


def make_facility(name, slug):
    facility = Facility.objects.create(
        name=name, slug=slug, ownership="public", level="health_centre",
        district="Gasabo", location=Point(30.11, -1.94, srid=4326),
        verified_at=timezone.now(), reports_queue=True,
    )
    for weekday in range(7):
        OpeningHours.objects.create(
            facility=facility, weekday=weekday,
            opens_at=time(0, 0), closes_at=time(23, 59),
        )
    return facility


@pytest.fixture
def facility(db):
    return make_facility("Kimironko HC", "kimironko-hc")


@pytest.fixture
def other_facility(db):
    return make_facility("Remera HC", "remera-hc")


def make_staff(facility, username, role="receptionist"):
    user = User.objects.create_user(username=username, password="pw-for-tests")
    StaffMember.objects.create(user=user, facility=facility, role=role, active=True)
    return user


@pytest.fixture
def desk(facility):
    return make_staff(facility, "desk")


@pytest.fixture
def client_as(db):
    def _sign_in(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _sign_in


def make_appointment(facility, service, patient=None, *, offset_hours=1, **kwargs):
    """Anchored to 09:00 on the local DATE, not to "now plus an hour".

    Anchoring on now made these tests time-of-day dependent: they passed all
    day and failed after 23:00, because `now + 1h` rolled into tomorrow and
    the "today" appointment stopped being today. A suite that only fails late
    at night is worse than one that fails always - it looks like whatever you
    changed last.

    09:00 also matches how a facility's day is actually laid out, so
    `offset_hours=30` lands mid-afternoon tomorrow rather than at 05:00.
    """
    start = timezone.make_aware(
        datetime.combine(timezone.localdate(), time(9, 0))
    ) + timedelta(hours=offset_hours)
    return Appointment.objects.create(
        facility=facility, service_type=service, patient=patient,
        slot_start=start, slot_end=start + timedelta(minutes=15), **kwargs
    )


# --------------------------------------------------------------------------
# Scoping - the control that matters most
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_list_shows_only_the_callers_facility(
    client_as, desk, facility, other_facility, general
):
    mine = make_appointment(facility, general)
    make_appointment(other_facility, general)

    body = client_as(desk).get(APPOINTMENTS).json()

    assert [row["reference"] for row in body["results"]] == [mine.reference]


@pytest.mark.django_db
def test_transitioning_another_facilitys_appointment_is_a_404(
    client_as, desk, other_facility, general
):
    """404 rather than 403, so a facility cannot probe for the existence of
    another facility's appointment ids."""
    theirs = make_appointment(other_facility, general)

    response = client_as(desk).post(
        f"{APPOINTMENTS}/{theirs.id}/status", {"status": "arrived"}, format="json"
    )

    assert response.status_code == 404
    theirs.refresh_from_db()
    assert theirs.status == Appointment.Status.BOOKED


@pytest.mark.django_db
def test_reports_count_only_the_callers_facility(
    client_as, desk, facility, other_facility, general
):
    QueueEntry.objects.create(
        facility=facility, service_type=general, ticket_code="G-1"
    )
    for n in range(5):
        QueueEntry.objects.create(
            facility=other_facility, service_type=general, ticket_code=f"R-{n}"
        )

    body = client_as(desk).get(REPORTS).json()

    assert body["facility"] == "Kimironko HC"
    assert body["period"]["checked_in"] == 1


@pytest.mark.django_db
def test_anonymous_callers_are_refused(db):
    client = APIClient()

    for path in (APPOINTMENTS, REPORTS):
        assert client.get(path).status_code in (401, 403)


@pytest.mark.django_db
def test_a_signed_in_user_who_is_not_staff_is_refused(client_as, db):
    outsider = User.objects.create_user(username="nobody", password="pw-for-tests")

    assert client_as(outsider).get(APPOINTMENTS).status_code == 403


# --------------------------------------------------------------------------
# The appointment list
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_list_defaults_to_today(client_as, desk, facility, general):
    today = make_appointment(facility, general)
    make_appointment(facility, general, offset_hours=30)

    body = client_as(desk).get(APPOINTMENTS).json()

    assert body["count"] == 1
    assert body["results"][0]["reference"] == today.reference


@pytest.mark.django_db
def test_another_day_can_be_asked_for(client_as, desk, facility, general):
    tomorrow = make_appointment(facility, general, offset_hours=30)
    day = timezone.localtime(tomorrow.slot_start).date()

    body = client_as(desk).get(APPOINTMENTS, {"date": day.isoformat()}).json()

    assert [row["reference"] for row in body["results"]] == [tomorrow.reference]


@pytest.mark.django_db
def test_a_malformed_date_is_a_400_not_a_500(client_as, desk):
    response = client_as(desk).get(APPOINTMENTS, {"date": "not-a-date"})

    assert response.status_code == 400
    assert response.json()["field"] == "date"


@pytest.mark.django_db
def test_cancelled_appointments_are_off_the_working_list(
    client_as, desk, facility, general
):
    """Noise on a list reception works through - but still reachable, and
    still counted in the reports."""
    make_appointment(facility, general, status=Appointment.Status.CANCELLED)

    assert client_as(desk).get(APPOINTMENTS).json()["count"] == 0
    assert client_as(desk).get(
        APPOINTMENTS, {"status": "cancelled"}
    ).json()["count"] == 1


@pytest.mark.django_db
def test_staff_see_the_phone_number_of_a_patient_booked_with_them(
    client_as, desk, facility, general
):
    """Reception has to be able to ring somebody who has not arrived. Scoped
    to their own facility, and written to the audit log."""
    patient = Patient.objects.create(phone="+250788111222", full_name="A. Uwase")
    make_appointment(facility, general, patient=patient)

    row = client_as(desk).get(APPOINTMENTS).json()["results"][0]

    assert row["patient_name"] == "A. Uwase"
    assert row["patient_phone"] == "+250788111222"


@pytest.mark.django_db
def test_viewing_the_list_is_written_to_the_audit_log(
    client_as, desk, facility, general
):
    make_appointment(facility, general)

    client_as(desk).get(APPOINTMENTS)

    entry = PatientAccessLog.objects.get()
    assert entry.action == PatientAccessLog.Action.VIEW
    assert entry.facility_id == facility.id
    # One bulk row for the whole list, not one per patient - the board rule.
    assert entry.record_count == 1


@pytest.mark.django_db
def test_an_empty_list_writes_nothing_to_the_audit_log(client_as, desk):
    """A quiet morning should not fill the log with rows recording that
    nobody's record was looked at."""
    client_as(desk).get(APPOINTMENTS)

    assert PatientAccessLog.objects.count() == 0


@pytest.mark.django_db
def test_an_anonymised_patient_leaves_a_row_with_nobody_to_name(
    client_as, desk, facility, general
):
    """Erasure nulls the FK rather than deleting the appointment, so the
    facility's own records stay intact. The row must still render."""
    make_appointment(facility, general, patient=None)

    row = client_as(desk).get(APPOINTMENTS).json()["results"][0]

    assert row["patient_name"] == "Removed"
    assert row["patient_phone"] is None


# --------------------------------------------------------------------------
# Transitions
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_marking_somebody_arrived(client_as, desk, facility, general):
    appointment = make_appointment(facility, general)

    body = client_as(desk).post(
        f"{APPOINTMENTS}/{appointment.id}/status", {"status": "arrived"},
        format="json",
    ).json()

    assert body["status"] == "arrived"
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.ARRIVED


@pytest.mark.django_db
def test_marking_a_no_show(client_as, desk, facility, general):
    appointment = make_appointment(facility, general)

    client_as(desk).post(
        f"{APPOINTMENTS}/{appointment.id}/status", {"status": "no_show"},
        format="json",
    )

    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.NO_SHOW


@pytest.mark.django_db
def test_cancelling_is_not_available_here(client_as, desk, facility, general):
    """A facility cancelling on a patient owes them a message, so it goes
    through the scheduling endpoint that sends one."""
    appointment = make_appointment(facility, general)

    response = client_as(desk).post(
        f"{APPOINTMENTS}/{appointment.id}/status", {"status": "cancelled"},
        format="json",
    )

    assert response.status_code == 400
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.BOOKED


@pytest.mark.django_db
def test_a_cancelled_appointment_cannot_be_marked_arrived(
    client_as, desk, facility, general
):
    """The patient was told it was off. Quietly reviving it would have them
    turn up to a slot nobody is expecting them in."""
    appointment = make_appointment(
        facility, general, status=Appointment.Status.CANCELLED
    )

    response = client_as(desk).post(
        f"{APPOINTMENTS}/{appointment.id}/status", {"status": "arrived"},
        format="json",
    )

    assert response.status_code == 400
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CANCELLED


@pytest.mark.django_db
def test_a_clinician_cannot_change_the_list(client_as, facility, general):
    """Clinicians read the workspace; they do not run the desk."""
    clinician = make_staff(facility, "dr-k", role="clinician")
    appointment = make_appointment(facility, general)

    response = client_as(clinician).post(
        f"{APPOINTMENTS}/{appointment.id}/status", {"status": "arrived"},
        format="json",
    )

    assert response.status_code == 403
    assert client_as(clinician).get(APPOINTMENTS).status_code == 200


# --------------------------------------------------------------------------
# Reports - honesty about the sample
# --------------------------------------------------------------------------


def served_entry(facility, service, *, waited_minutes, days_ago=1, code="G"):
    joined = timezone.localtime() - timedelta(days=days_ago)
    return QueueEntry.objects.create(
        facility=facility, service_type=service, ticket_code=code,
        joined_at=joined,
        called_at=joined + timedelta(minutes=waited_minutes),
        served_at=joined + timedelta(minutes=waited_minutes + 5),
        status=QueueEntry.Status.SERVED,
    )


@pytest.mark.django_db
def test_a_thin_sample_reports_no_median_at_all(
    client_as, desk, facility, general
):
    """Not zero, and not a number with a caveat next to it. A manager will act
    on whatever number is on the screen - so there must not be one."""
    for n in range(4):
        served_entry(facility, general, waited_minutes=20, code=f"G-{n}")

    wait = client_as(desk).get(REPORTS).json()["wait"]

    assert wait["median_minutes"] is None
    assert wait["enough_data"] is False
    assert wait["sample_size"] == 4


@pytest.mark.django_db
def test_enough_visits_produce_a_median(client_as, desk, facility, general):
    for n in range(11):
        served_entry(facility, general, waited_minutes=20, code=f"G-{n}")

    wait = client_as(desk).get(REPORTS).json()["wait"]

    assert wait["median_minutes"] == 20.0
    assert wait["enough_data"] is True


@pytest.mark.django_db
def test_an_entry_left_open_overnight_does_not_poison_the_median(
    client_as, desk, facility, general
):
    """A receptionist clearing yesterday's queue this morning would otherwise
    record a sixteen-hour wait and wreck the facility's own numbers."""
    for n in range(11):
        served_entry(facility, general, waited_minutes=20, code=f"G-{n}")
    served_entry(facility, general, waited_minutes=16 * 60, code="G-stale")

    assert client_as(desk).get(REPORTS).json()["wait"]["median_minutes"] == 20.0


@pytest.mark.django_db
def test_the_no_show_rate_is_null_when_there_are_no_appointments(
    client_as, desk
):
    """Zero out of zero is not a zero percent no-show rate."""
    assert client_as(desk).get(REPORTS).json()["appointments"]["no_show_rate"] is None


@pytest.mark.django_db
def test_the_no_show_rate(client_as, desk, facility, general):
    make_appointment(facility, general, status=Appointment.Status.NO_SHOW)
    for _ in range(3):
        make_appointment(facility, general, status=Appointment.Status.SERVED)

    appointments = client_as(desk).get(REPORTS).json()["appointments"]

    assert appointments["total"] == 4
    assert appointments["no_shows"] == 1
    assert appointments["no_show_rate"] == 0.25


@pytest.mark.django_db
def test_cancelled_appointments_still_count_in_the_reports(
    client_as, desk, facility, general
):
    make_appointment(facility, general, status=Appointment.Status.CANCELLED)

    assert client_as(desk).get(REPORTS).json()["appointments"]["total"] == 1


@pytest.mark.django_db
def test_demand_is_ordered_by_pressure(client_as, desk, facility, general, db):
    antenatal = ServiceType.objects.create(
        code="antenatal", name_en="Antenatal", name_rw="x", name_fr="x"
    )
    for n in range(3):
        QueueEntry.objects.create(
            facility=facility, service_type=general, ticket_code=f"G-{n}"
        )
    QueueEntry.objects.create(
        facility=facility, service_type=antenatal, ticket_code="A-1"
    )

    demand = client_as(desk).get(REPORTS).json()["demand"]

    assert [row["service"] for row in demand] == ["general_consultation", "antenatal"]
    assert demand[0]["count"] == 3


@pytest.mark.django_db
def test_the_window_is_bounded(client_as, desk):
    """An unbounded window is a table scan somebody can ask for repeatedly."""
    for days in ("0", "91", "-5"):
        response = client_as(desk).get(REPORTS, {"days": days})
        assert response.status_code == 400, days

    assert client_as(desk).get(REPORTS, {"days": "7"}).json()["days"] == 7


@pytest.mark.django_db
def test_a_malformed_window_is_a_400_not_a_500(client_as, desk):
    response = client_as(desk).get(REPORTS, {"days": "lots"})

    assert response.status_code == 400
    assert response.json()["field"] == "days"


@pytest.mark.django_db
def test_visits_outside_the_window_are_excluded(
    client_as, desk, facility, general
):
    served_entry(facility, general, waited_minutes=20, days_ago=45, code="G-old")

    assert client_as(desk).get(REPORTS, {"days": "30"}).json()["period"][
        "checked_in"
    ] == 0
    assert client_as(desk).get(REPORTS, {"days": "60"}).json()["period"][
        "checked_in"
    ] == 1


@pytest.mark.django_db
def test_todays_counts_are_separate_from_the_window(
    client_as, desk, facility, general
):
    QueueEntry.objects.create(
        facility=facility, service_type=general, ticket_code="G-now"
    )
    served_entry(facility, general, waited_minutes=20, days_ago=3, code="G-old")

    body = client_as(desk).get(REPORTS).json()

    assert body["today"]["checked_in"] == 1
    assert body["today"]["waiting"] == 1
    assert body["period"]["checked_in"] == 2


@pytest.mark.django_db
def test_a_no_show_can_be_put_right(client_as, desk, facility, general):
    """People turn up late and receptionists mis-tap. Correcting it must not
    need a support call."""
    appointment = make_appointment(
        facility, general, status=Appointment.Status.NO_SHOW
    )

    client_as(desk).post(
        f"{APPOINTMENTS}/{appointment.id}/status", {"status": "arrived"},
        format="json",
    )

    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.ARRIVED


@pytest.mark.django_db
def test_reviving_a_no_show_into_an_occupied_slot_is_a_409(
    client_as, desk, facility, general
):
    """one_active_appointment_per_slot. Reachable when the patient rebooked
    the identical slot after not turning up - a 409, not a 500."""
    patient = Patient.objects.create(phone="+250788333444", full_name="B. Keza")
    missed = make_appointment(
        facility, general, patient=patient, status=Appointment.Status.NO_SHOW
    )
    Appointment.objects.create(
        facility=facility, service_type=general, patient=patient,
        slot_start=missed.slot_start, slot_end=missed.slot_end,
        status=Appointment.Status.BOOKED,
    )

    response = client_as(desk).post(
        f"{APPOINTMENTS}/{missed.id}/status", {"status": "arrived"}, format="json"
    )

    assert response.status_code == 409
    missed.refresh_from_db()
    assert missed.status == Appointment.Status.NO_SHOW


# --------------------------------------------------------------------------
# Schedule management - the facility's own bookable hours
# --------------------------------------------------------------------------

SCHEDULE = "/api/v1/staff/schedule"
SCHEDULE_NEW = "/api/v1/staff/schedule/new"


@pytest.fixture
def offered(facility, general):
    """A facility can only schedule a service it actually offers."""
    from apps.facilities.models import FacilityService

    return FacilityService.objects.create(
        facility=facility, service_type=general, available=True
    )


@pytest.fixture
def clinician(facility):
    return make_staff(facility, "doctor", role="clinician")


@pytest.fixture
def schedule_patient(db):
    return Patient.objects.create(phone="+250788555777")



def _session(**overrides):
    body = {
        "weekday": 1,
        "service": "general_consultation",
        "start_time": "08:00",
        "end_time": "12:00",
        "slot_minutes": 15,
        "capacity_per_slot": 2,
    }
    body.update(overrides)
    return body


@pytest.mark.django_db
def test_a_facility_can_open_a_bookable_session(client_as, desk, general, facility, offered):
    """ScheduleTemplate drives the entire booking system and there was no way
    for a facility to create one."""
    from apps.scheduling.models import ScheduleTemplate

    response = client_as(desk).post(SCHEDULE_NEW, _session(), format="json")

    assert response.status_code == 201
    body = response.json()
    # 4 hours at 15 minutes is 16 slots, 2 patients each.
    assert body["slots_per_week"] == 32
    assert ScheduleTemplate.objects.filter(facility=facility).count() == 1


@pytest.mark.django_db
def test_a_new_session_becomes_bookable_immediately(
    client_as, desk, general, facility, offered
):
    """The point of the screen. A session nobody can book into is decoration."""
    from datetime import timedelta

    from apps.scheduling.services import available_slots

    # Open every weekday so the assertion does not depend on when it runs.
    for weekday in range(7):
        client_as(desk).post(
            SCHEDULE_NEW, _session(weekday=weekday), format="json"
        )

    days = available_slots(
        facility=facility,
        service_type=general,
        date_to=timezone.localtime().date() + timedelta(days=3),
    )

    assert days, "a session was opened but no slots were offered"


@pytest.mark.django_db
def test_a_session_cannot_be_opened_for_a_service_the_facility_lacks(
    client_as, desk, offered
):
    response = client_as(desk).post(
        SCHEDULE_NEW, _session(service="neurosurgery"), format="json"
    )

    assert response.status_code == 400
    assert "does not offer" in str(response.json())


@pytest.mark.django_db
def test_a_session_must_end_after_it_starts(client_as, desk, general, offered):
    response = client_as(desk).post(
        SCHEDULE_NEW,
        _session(start_time="14:00", end_time="09:00"),
        format="json",
    )

    assert response.status_code == 400
    assert "end after it starts" in str(response.json())


@pytest.mark.django_db
def test_a_slot_cannot_be_longer_than_its_session(client_as, desk, general, offered):
    """Otherwise the session produces zero slots and reads as broken rather
    than as misconfigured."""
    response = client_as(desk).post(
        SCHEDULE_NEW,
        _session(start_time="09:00", end_time="09:30", slot_minutes=60),
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_two_sessions_cannot_start_at_the_same_time(client_as, desk, general, offered):
    client_as(desk).post(SCHEDULE_NEW, _session(), format="json")

    response = client_as(desk).post(SCHEDULE_NEW, _session(), format="json")

    assert response.status_code == 400
    assert "already starts" in str(response.json())


@pytest.mark.django_db
def test_closing_a_session_stops_new_bookings(client_as, desk, general, facility, offered):
    """Deactivating is the safe operation: it closes the door without
    cancelling anybody who is already through it."""
    from datetime import timedelta

    from apps.scheduling.services import available_slots

    for weekday in range(7):
        client_as(desk).post(
            SCHEDULE_NEW, _session(weekday=weekday), format="json"
        )
    listed = client_as(desk).get(SCHEDULE).json()["results"]

    for row in listed:
        client_as(desk).patch(
            f"{SCHEDULE}/{row['id']}", {"active": False}, format="json"
        )

    days = available_slots(
        facility=facility,
        service_type=general,
        date_to=timezone.localtime().date() + timedelta(days=3),
    )
    assert days == []


@pytest.mark.django_db
def test_the_list_reports_how_many_patients_a_session_already_holds(
    client_as, desk, general, facility, offered, schedule_patient
):
    """The number a facility needs BEFORE closing a session. Deactivating
    stops new bookings and does not cancel existing ones, so somebody has to
    know they still have patients coming."""
    from datetime import timedelta

    from apps.scheduling.models import Appointment

    client_as(desk).post(SCHEDULE_NEW, _session(weekday=1), format="json")

    # A future Tuesday, matching the session's weekday.
    when = timezone.localtime() + timedelta(days=1)
    while when.weekday() != 1:
        when += timedelta(days=1)
    Appointment.objects.create(
        facility=facility,
        patient=schedule_patient,
        service_type=general,
        slot_start=when.replace(hour=9, minute=0, second=0, microsecond=0),
        slot_end=when.replace(hour=9, minute=15, second=0, microsecond=0),
    )

    row = client_as(desk).get(SCHEDULE).json()["results"][0]

    assert row["upcoming"] == 1


@pytest.mark.django_db
def test_a_clinician_from_another_facility_cannot_be_scheduled(
    client_as, desk, general, other_facility, offered
):
    """A staff member must not be able to open a session in another
    facility's doctor's name."""
    from apps.providers.models import Provider, ProviderFacility

    outsider = Provider.objects.create(
        full_name="Dr Elsewhere", slug="dr-elsewhere"
    )
    ProviderFacility.objects.create(provider=outsider, facility=other_facility)

    response = client_as(desk).post(
        SCHEDULE_NEW, _session(provider="dr-elsewhere"), format="json"
    )

    assert response.status_code == 400
    assert "does not work at this facility" in str(response.json())


@pytest.mark.django_db
def test_another_facilitys_session_is_not_editable(
    client_as, desk, other_facility, general, offered
):
    """404 rather than 403 - the response must not confirm the id exists."""
    from apps.scheduling.models import ScheduleTemplate

    theirs = ScheduleTemplate.objects.create(
        facility=other_facility,
        service_type=general,
        weekday=1,
        start_time=time(8, 0),
        end_time=time(12, 0),
    )

    response = client_as(desk).patch(
        f"{SCHEDULE}/{theirs.id}", {"active": False}, format="json"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_clinician_cannot_change_the_schedule(client_as, clinician, general, offered):
    """Same rule as the queue: clinicians read, receptionists and admins
    write."""
    response = client_as(clinician).post(SCHEDULE_NEW, _session(), format="json")

    assert response.status_code == 403


# --------------------------------------------------------------------------
# Insurance - maintained by the facility, confirmed by the facility
# --------------------------------------------------------------------------

INSURANCE = "/api/v1/staff/insurance"


@pytest.fixture
def mutuelle(db):
    from apps.insurance.models import Insurer

    return Insurer.objects.create(code="mutuelle", name="Mutuelle de Sante")


@pytest.mark.django_db
def test_every_insurer_is_listed_including_ones_not_accepted(
    client_as, desk, mutuelle, offered
):
    """A list of only the accepted ones gives nobody a way to add one."""
    body = client_as(desk).get(INSURANCE).json()

    codes = {row["code"] for row in body["results"]}
    assert "mutuelle" in codes
    assert body["results"][0]["accepted"] is False


@pytest.mark.django_db
def test_a_facility_can_accept_an_insurer_and_it_is_confirmed(
    client_as, desk, mutuelle, facility
):
    """The facility saying so IS the confirmation - it runs the counter that
    takes the card."""
    from apps.insurance.models import FacilityInsurer

    response = client_as(desk).patch(
        f"{INSURANCE}/mutuelle", {"accepted": True}, format="json"
    )

    assert response.status_code == 200
    assert response.json()["confirmed_at"] is not None
    link = FacilityInsurer.objects.get(facility=facility, insurer=mutuelle)
    assert link.confirmed_at is not None


@pytest.mark.django_db
def test_coverage_can_be_set_for_an_accepted_insurer(
    client_as, desk, mutuelle, general, offered, facility
):
    from apps.insurance.models import FacilityServiceInsurer

    client_as(desk).patch(f"{INSURANCE}/mutuelle", {"accepted": True}, format="json")

    response = client_as(desk).patch(
        f"{INSURANCE}/mutuelle/services/general_consultation",
        {"coverage": "full"},
        format="json",
    )

    assert response.status_code == 200
    row = FacilityServiceInsurer.objects.get()
    assert row.coverage == "full"
    # Confirmed, so `effective_coverage` reports it rather than falling back.
    assert row.effective_coverage == "full"


@pytest.mark.django_db
def test_coverage_needs_the_insurer_to_be_accepted_first(
    client_as, desk, mutuelle, general, offered
):
    """Otherwise a facility publishes "Mutuelle covers dental" while telling
    patients at the door that it does not take Mutuelle."""
    response = client_as(desk).patch(
        f"{INSURANCE}/mutuelle/services/general_consultation",
        {"coverage": "full"},
        format="json",
    )

    assert response.status_code == 400
    assert "Accept this insurer" in str(response.json())


@pytest.mark.django_db
def test_unknown_coverage_is_never_confirmed(
    client_as, desk, mutuelle, general, offered
):
    """`unknown` is the absence of an answer, not an answer. Storing it
    confirmed would publish "we checked, and we do not know"."""
    from apps.insurance.models import FacilityServiceInsurer

    client_as(desk).patch(f"{INSURANCE}/mutuelle", {"accepted": True}, format="json")
    client_as(desk).patch(
        f"{INSURANCE}/mutuelle/services/general_consultation",
        {"coverage": "unknown"},
        format="json",
    )

    row = FacilityServiceInsurer.objects.get()
    assert row.confirmed_at is None
    assert row.effective_coverage == "unknown"


@pytest.mark.django_db
def test_dropping_an_insurer_takes_its_coverage_with_it(
    client_as, desk, mutuelle, general, offered
):
    """Leaving "Mutuelle covers dental here" behind after "we no longer take
    Mutuelle" is a contradiction a patient would act on."""
    from apps.insurance.models import FacilityInsurer, FacilityServiceInsurer

    client_as(desk).patch(f"{INSURANCE}/mutuelle", {"accepted": True}, format="json")
    client_as(desk).patch(
        f"{INSURANCE}/mutuelle/services/general_consultation",
        {"coverage": "full"},
        format="json",
    )
    assert FacilityServiceInsurer.objects.count() == 1

    client_as(desk).patch(f"{INSURANCE}/mutuelle", {"accepted": False}, format="json")

    assert FacilityInsurer.objects.count() == 0
    assert FacilityServiceInsurer.objects.count() == 0


@pytest.mark.django_db
def test_coverage_cannot_be_set_for_a_service_the_facility_lacks(
    client_as, desk, mutuelle
):
    client_as(desk).patch(f"{INSURANCE}/mutuelle", {"accepted": True}, format="json")

    response = client_as(desk).patch(
        f"{INSURANCE}/mutuelle/services/neurosurgery",
        {"coverage": "full"},
        format="json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_clinician_cannot_change_what_the_facility_accepts(
    client_as, clinician, mutuelle
):
    response = client_as(clinician).patch(
        f"{INSURANCE}/mutuelle", {"accepted": True}, format="json"
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_one_facilitys_insurance_is_not_anothers(
    client_as, desk, mutuelle, other_facility
):
    """Facility scoping, asserted here as it is on every other staff
    endpoint."""
    from apps.insurance.models import FacilityInsurer

    client_as(desk).patch(f"{INSURANCE}/mutuelle", {"accepted": True}, format="json")

    assert FacilityInsurer.objects.filter(facility=other_facility).count() == 0


# --------------------------------------------------------------------------
# Facility settings
# --------------------------------------------------------------------------

FACILITY = "/api/v1/staff/facility"
LOOKUP = "/api/v1/staff/patients"


@pytest.mark.django_db
def test_a_facility_can_fix_its_own_contact_details(client_as, desk, facility):
    response = client_as(desk).patch(
        f"{FACILITY}/contact",
        {"phone": "+250788112233", "address": "KG 11 Ave"},
        format="json",
    )

    assert response.status_code == 200
    facility.refresh_from_db()
    assert facility.phone == "+250788112233"
    assert facility.address == "KG 11 Ave"


@pytest.mark.django_db
def test_the_verified_identity_is_not_editable_here(client_as, desk, facility):
    """Name, level and district are what `verified_at` attests to. A facility
    that could rename itself would be editing the thing MediLink checked."""
    original = facility.name

    client_as(desk).patch(
        f"{FACILITY}/contact",
        {"name": "Somewhere Else", "district": "Musanze", "phone": "+250788000111"},
        format="json",
    )

    facility.refresh_from_db()
    assert facility.name == original
    assert facility.district != "Musanze"
    # The field that IS editable still went through.
    assert facility.phone == "+250788000111"


@pytest.mark.django_db
def test_opening_hours_can_hold_a_lunch_break(client_as, desk, facility):
    """Two rows on one weekday. It is how a health centre actually runs, and
    the reason hours are replaced as a set rather than patched row by row."""
    from apps.facilities.models import OpeningHours

    response = client_as(desk).put(
        f"{FACILITY}/hours",
        {
            "hours": [
                {"weekday": 1, "opens_at": "08:00", "closes_at": "12:00"},
                {"weekday": 1, "opens_at": "14:00", "closes_at": "17:00"},
            ]
        },
        format="json",
    )

    assert response.status_code == 200
    tuesday = OpeningHours.objects.filter(facility=facility, weekday=1)
    assert tuesday.count() == 2


@pytest.mark.django_db
def test_a_facility_cannot_close_before_it_opens(client_as, desk):
    response = client_as(desk).put(
        f"{FACILITY}/hours",
        {"hours": [{"weekday": 1, "opens_at": "17:00", "closes_at": "08:00"}]},
        format="json",
    )

    assert response.status_code == 400
    assert "close after it opens" in str(response.json())


@pytest.mark.django_db
def test_replacing_hours_replaces_all_of_them(client_as, desk, facility):
    """The fixture opens every day. Sending one row must leave exactly one."""
    from apps.facilities.models import OpeningHours

    client_as(desk).put(
        f"{FACILITY}/hours",
        {"hours": [{"weekday": 3, "opens_at": "09:00", "closes_at": "16:00"}]},
        format="json",
    )

    assert OpeningHours.objects.filter(facility=facility).count() == 1


@pytest.mark.django_db
def test_a_clinician_cannot_change_facility_settings(client_as, clinician):
    response = client_as(clinician).patch(
        f"{FACILITY}/contact", {"phone": "+250788999888"}, format="json"
    )

    assert response.status_code == 403


# --------------------------------------------------------------------------
# Patient lookup - scoped, logged, throttled
# --------------------------------------------------------------------------


@pytest.fixture
def seen_here(db, facility, general):
    """A patient this facility has actually seen."""
    from apps.queueing.models import QueueEntry

    person = Patient.objects.create(
        phone="+250788121212", full_name="Uwase Alice"
    )
    QueueEntry.objects.create(
        facility=facility,
        service_type=general,
        patient=person,
        ticket_code="G-900",
        ticket_day=timezone.localtime().date(),
    )
    return person


@pytest.mark.django_db
def test_a_returning_patient_can_be_found_by_name(client_as, desk, seen_here):
    body = client_as(desk).get(LOOKUP, {"q": "Uwase"}).json()

    assert body["count"] == 1
    assert body["results"][0]["display_name"] == "Uwase Alice"
    assert body["results"][0]["visits_here"] == 1


@pytest.mark.django_db
def test_a_local_phone_format_finds_the_stored_one(client_as, desk, seen_here):
    """Typed as 0788…, stored as +250788…."""
    body = client_as(desk).get(LOOKUP, {"q": "0788121212"}).json()

    assert body["count"] == 1


@pytest.mark.django_db
def test_the_phone_is_masked_in_results(client_as, desk, seen_here):
    """A lookup screen is read across a reception desk like the queue board."""
    body = client_as(desk).get(LOOKUP, {"q": "Uwase"}).json()

    assert body["results"][0]["phone"] != "+250788121212"
    assert "..." in body["results"][0]["phone"]


@pytest.mark.django_db
def test_a_patient_seen_only_elsewhere_is_not_found(
    client_as, desk, other_facility, general
):
    """The breach that ends the project. A receptionist at one clinic must
    never be able to look up somebody who has only attended another."""
    from apps.queueing.models import QueueEntry

    stranger = Patient.objects.create(
        phone="+250788343434", full_name="Mukamana Grace"
    )
    QueueEntry.objects.create(
        facility=other_facility,
        service_type=general,
        patient=stranger,
        ticket_code="G-901",
        ticket_day=timezone.localtime().date(),
    )

    body = client_as(desk).get(LOOKUP, {"q": "Mukamana"}).json()

    assert body["count"] == 0


@pytest.mark.django_db
def test_a_short_query_returns_nothing_rather_than_everybody(
    client_as, desk, seen_here
):
    """Two characters matches most of the register, and a list of patients is
    exactly what this endpoint must not hand out."""
    body = client_as(desk).get(LOOKUP, {"q": "Uw"}).json()

    assert body["count"] == 0


@pytest.mark.django_db
def test_every_lookup_is_written_to_the_access_log(client_as, desk, seen_here):
    """A search that returns a patient is a read of a patient record.
    docs/08 s6 requires it to be attributable."""
    PatientAccessLog.objects.all().delete()

    client_as(desk).get(LOOKUP, {"q": "Uwase"})

    entry = PatientAccessLog.objects.get()
    assert entry.action == PatientAccessLog.Action.VIEW
    assert entry.record_count == 1


@pytest.mark.django_db
def test_a_lookup_shows_whether_they_are_already_in_the_queue(
    client_as, desk, seen_here
):
    """The reason reception is searching at all: is this person already
    checked in, or do I need to add them?"""
    body = client_as(desk).get(LOOKUP, {"q": "Uwase"}).json()

    assert body["results"][0]["in_queue_now"] is True
    assert body["results"][0]["ticket_code"] == "G-900"
