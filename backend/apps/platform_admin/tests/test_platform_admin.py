"""Platform administration.

The controls under test, in order of how much damage they prevent:

1. Only a superuser gets in. `is_staff` is not enough - it is routinely
   granted to somebody who needs to edit one lookup table, and these endpoints
   cross every facility and patient count in the country.
2. Nothing here returns a patient. Counts only.
3. Triage monitoring reads `TriageOutcome` and nothing else - no answers, no
   sessions, no patient link.
4. Verification is not reversible by accident and requires a note saying what
   was checked.
"""

from datetime import time, timedelta

import pytest
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient

from apps.facilities.models import Facility, OpeningHours, ServiceType
from apps.patients.models import Patient
from apps.providers.models import Provider, Specialty
from apps.queueing.models import QueueEntry
from apps.scheduling.models import Appointment
from apps.staff.models import StaffMember
from apps.triage.models import TriageOutcome

OVERVIEW = "/api/v1/platform/overview"
QUEUE = "/api/v1/platform/verification"
TRIAGE = "/api/v1/platform/triage-monitoring"


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def client_as(db):
    def _sign_in(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _sign_in


@pytest.fixture
def admin(db):
    return User.objects.create_superuser(
        username="platform-admin", password="pw-for-tests", email="a@example.com"
    )


def make_facility(name, slug, *, verified=True):
    facility = Facility.objects.create(
        name=name, slug=slug, ownership="public", level="health_centre",
        district="Gasabo", location=Point(30.11, -1.94, srid=4326),
        verified_at=timezone.now() if verified else None,
        reports_queue=True,
    )
    for weekday in range(7):
        OpeningHours.objects.create(
            facility=facility, weekday=weekday,
            opens_at=time(0, 0), closes_at=time(23, 59),
        )
    return facility


@pytest.fixture
def verified_facility(db):
    return make_facility("Kimironko HC", "kimironko-hc")


@pytest.fixture
def pending_facility(db):
    return make_facility("New Clinic", "new-clinic", verified=False)


def outcome(**kwargs):
    defaults = {
        "protocol_version": "2026.1",
        "recommended_service": "general_consultation",
        "escalated_emergency": False,
        "questions_answered": 3,
        "date": timezone.localdate(),
        "hour_bucket": 10,
    }
    return TriageOutcome.objects.create(**{**defaults, **kwargs})


# --------------------------------------------------------------------------
# 1. Who gets in
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_callers_are_refused(db):
    client = APIClient()

    for path in (OVERVIEW, QUEUE, TRIAGE):
        assert client.get(path).status_code in (401, 403), path


@pytest.mark.django_db
def test_an_ordinary_signed_in_user_is_refused(client_as, db):
    user = User.objects.create_user(username="nobody", password="pw-for-tests")

    for path in (OVERVIEW, QUEUE, TRIAGE):
        assert client_as(user).get(path).status_code == 403, path


@pytest.mark.django_db
def test_is_staff_is_not_enough(client_as, db):
    """`is_staff` only means "may open Django admin", and it gets granted to
    somebody who needs to edit one lookup table. Reading platform-wide figures
    and approving hospitals into patient search is a different privilege."""
    editor = User.objects.create_user(
        username="lookup-editor", password="pw-for-tests", is_staff=True
    )

    for path in (OVERVIEW, QUEUE, TRIAGE):
        assert client_as(editor).get(path).status_code == 403, path


@pytest.mark.django_db
def test_facility_staff_cannot_reach_the_platform_endpoints(
    client_as, verified_facility
):
    """A receptionist is scoped to one facility. These endpoints are the
    opposite of that."""
    user = User.objects.create_user(username="desk", password="pw-for-tests")
    StaffMember.objects.create(
        user=user, facility=verified_facility, role="receptionist", active=True
    )

    assert client_as(user).get(OVERVIEW).status_code == 403


@pytest.mark.django_db
def test_a_deactivated_superuser_is_refused(client_as, db):
    """Deactivating an account has to close every door, not just the login
    form - a token issued before the deactivation must stop working."""
    user = User.objects.create_superuser(
        username="former-admin", password="pw-for-tests", email="f@example.com"
    )
    user.is_active = False
    user.save(update_fields=["is_active"])

    assert client_as(user).get(OVERVIEW).status_code == 403


@pytest.mark.django_db
def test_a_superuser_gets_in(client_as, admin):
    for path in (OVERVIEW, QUEUE, TRIAGE):
        assert client_as(admin).get(path).status_code == 200, path


# --------------------------------------------------------------------------
# 2. Nothing here returns a patient
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_overview_reports_a_patient_count_and_nothing_else(
    client_as, admin, db
):
    Patient.objects.create(phone="+250788111222", full_name="A. Uwase")

    body = client_as(admin).get(OVERVIEW).json()

    assert body["patients"] == {"registered": 1}
    # No phone number, no name, anywhere in the payload.
    assert "788111222" not in str(body)
    assert "Uwase" not in str(body)


# --------------------------------------------------------------------------
# 3. Overview figures
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_verification_backlog_is_reported(
    client_as, admin, verified_facility, pending_facility
):
    body = client_as(admin).get(OVERVIEW).json()

    assert body["facilities"]["total"] == 2
    assert body["facilities"]["verified"] == 1
    assert body["facilities"]["awaiting_verification"] == 1


@pytest.mark.django_db
def test_booking_channels_are_counted(client_as, admin, verified_facility, db):
    service = ServiceType.objects.create(
        code="general_consultation", name_en="General", name_rw="x", name_fr="x"
    )
    start = timezone.localtime() + timedelta(hours=1)
    for via in ("ussd", "ussd", "app"):
        Appointment.objects.create(
            facility=verified_facility, service_type=service,
            slot_start=start, slot_end=start + timedelta(minutes=15),
            booked_via=via,
        )
        start += timedelta(minutes=30)

    channels = {
        row["channel"]: row["count"]
        for row in client_as(admin).get(OVERVIEW).json()["activity"]["by_channel"]
    }

    assert channels == {"ussd": 2, "app": 1}


@pytest.mark.django_db
def test_the_window_is_bounded(client_as, admin):
    for days in ("0", "366", "-1"):
        assert client_as(admin).get(OVERVIEW, {"days": days}).status_code == 400, days

    assert client_as(admin).get(OVERVIEW, {"days": "7"}).json()["days"] == 7


@pytest.mark.django_db
def test_a_malformed_window_is_a_400_not_a_500(client_as, admin):
    response = client_as(admin).get(OVERVIEW, {"days": "lots"})

    assert response.status_code == 400
    assert response.json()["field"] == "days"


@pytest.mark.django_db
def test_activity_outside_the_window_is_excluded(
    client_as, admin, verified_facility, db
):
    service = ServiceType.objects.create(
        code="general_consultation", name_en="General", name_rw="x", name_fr="x"
    )
    QueueEntry.objects.create(
        facility=verified_facility, service_type=service, ticket_code="G-old",
        joined_at=timezone.localtime() - timedelta(days=45),
    )

    assert client_as(admin).get(OVERVIEW, {"days": "30"}).json()["activity"][
        "check_ins"
    ] == 0
    assert client_as(admin).get(OVERVIEW, {"days": "60"}).json()["activity"][
        "check_ins"
    ] == 1


# --------------------------------------------------------------------------
# 4. Verification
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_queue_lists_only_unverified_facilities(
    client_as, admin, verified_facility, pending_facility
):
    body = client_as(admin).get(QUEUE).json()

    assert [f["slug"] for f in body["facilities"]] == ["new-clinic"]


@pytest.mark.django_db
def test_verifying_a_facility_records_who_and_what_they_checked(
    client_as, admin, pending_facility
):
    response = client_as(admin).post(
        f"{QUEUE}/facilities/{pending_facility.id}",
        {"note": "Licence 2026/114 sighted; coordinates captured on site."},
        format="json",
    )

    assert response.status_code == 200
    pending_facility.refresh_from_db()
    assert pending_facility.verified_at is not None
    assert pending_facility.verified_by_id == admin.id
    assert "2026/114" in pending_facility.verification_note


@pytest.mark.django_db
def test_a_note_is_required(client_as, admin, pending_facility):
    """An approval with no record of what was checked is indistinguishable
    from a mis-click, and this one puts a facility in front of patients."""
    for payload in ({}, {"note": ""}, {"note": "   "}):
        response = client_as(admin).post(
            f"{QUEUE}/facilities/{pending_facility.id}", payload, format="json"
        )
        assert response.status_code == 400, payload

    pending_facility.refresh_from_db()
    assert pending_facility.verified_at is None


@pytest.mark.django_db
def test_verifying_twice_is_refused(client_as, admin, verified_facility):
    """Re-verifying would overwrite who checked it and when, losing the only
    record of the original decision."""
    response = client_as(admin).post(
        f"{QUEUE}/facilities/{verified_facility.id}",
        {"note": "second look"},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_verifying_a_facility_that_does_not_exist(client_as, admin):
    response = client_as(admin).post(
        f"{QUEUE}/facilities/999999", {"note": "x"}, format="json"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_an_ordinary_user_cannot_verify_a_facility(client_as, pending_facility, db):
    editor = User.objects.create_user(
        username="lookup-editor", password="pw-for-tests", is_staff=True
    )

    response = client_as(editor).post(
        f"{QUEUE}/facilities/{pending_facility.id}", {"note": "x"}, format="json"
    )

    assert response.status_code == 403
    pending_facility.refresh_from_db()
    assert pending_facility.verified_at is None


@pytest.mark.django_db
def test_verifying_a_provider(client_as, admin, db):
    specialty = Specialty.objects.create(
        code="paediatrics", name_en="Paediatrics", name_rw="x", name_fr="x"
    )
    provider = Provider.objects.create(
        slug="dr-k", full_name="Dr K. Habimana", verified_at=None
    )
    provider.specialties.add(specialty)

    response = client_as(admin).post(
        f"{QUEUE}/providers/{provider.id}",
        {"note": "RMDC registration 4471 confirmed."},
        format="json",
    )

    assert response.status_code == 200
    provider.refresh_from_db()
    assert provider.verified_at is not None


# --------------------------------------------------------------------------
# 5. Triage monitoring reads outcomes only
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_thin_sample_reports_no_escalation_rate(client_as, admin, db):
    """Nobody should tune a clinical protocol on four sessions."""
    for _ in range(4):
        outcome()

    body = client_as(admin).get(TRIAGE).json()

    assert body["escalation_rate"] is None
    assert body["enough_data"] is False
    assert body["sessions"] == 4


@pytest.mark.django_db
def test_enough_sessions_produce_an_escalation_rate(client_as, admin, db):
    for _ in range(15):
        outcome()
    for _ in range(5):
        outcome(escalated_emergency=True, recommended_service="")

    body = client_as(admin).get(TRIAGE).json()

    assert body["sessions"] == 20
    assert body["escalations"] == 5
    assert body["escalation_rate"] == 0.25
    assert body["enough_data"] is True


@pytest.mark.django_db
def test_outcomes_are_grouped_by_protocol_version(client_as, admin, db):
    """A rule change has to be traceable to what it did to the numbers."""
    for _ in range(3):
        outcome(protocol_version="2026.1")
    outcome(protocol_version="2026.2", escalated_emergency=True)

    versions = {
        row["protocol_version"]: row
        for row in client_as(admin).get(TRIAGE).json()["by_version"]
    }

    assert versions["2026.1"]["sessions"] == 3
    assert versions["2026.2"]["escalations"] == 1


@pytest.mark.django_db
def test_outcomes_outside_the_window_are_excluded(client_as, admin, db):
    outcome(date=timezone.localdate() - timedelta(days=45))

    assert client_as(admin).get(TRIAGE, {"days": "30"}).json()["sessions"] == 0
    assert client_as(admin).get(TRIAGE, {"days": "60"}).json()["sessions"] == 1


@pytest.mark.django_db
def test_monitoring_exposes_no_answers_and_no_session_identifiers(
    client_as, admin, db
):
    """TriageOutcome carries no patient link, no session id and no answers by
    design. Pin the payload's SHAPE, so widening it later is a deliberate act
    that breaks this test rather than a quiet leak.

    Checked on keys rather than on a substring: `sessions` is a count and
    legitimately contains the word "session"."""
    outcome()

    body = client_as(admin).get(TRIAGE).json()

    assert set(body) == {
        "days", "sessions", "escalations", "escalation_rate",
        "enough_data", "minimum_sessions", "by_service", "by_version",
    }
    assert set(body["by_service"][0]) == {"service", "count"}
    assert set(body["by_version"][0]) == {
        "protocol_version", "sessions", "escalations",
    }

    # And nothing anywhere is an identifier or an answer.
    def keys(node):
        if isinstance(node, dict):
            for key, value in node.items():
                yield key
                yield from keys(value)
        elif isinstance(node, list):
            for item in node:
                yield from keys(item)

    for key in keys(body):
        assert key not in {
            "session_id", "patient", "patient_id", "phone",
            "answers", "answer", "question", "question_code",
        }, key
