"""Oversight: what is happening on the platform.

`test_platform_admin.py` covers the three original endpoints. These cover the
six that answer "what is happening, and is anything wrong?".

The controls are the same two as everywhere else in this app, and they matter
more here because these endpoints reach across every facility:

1. Only a superuser gets in.
2. Nothing names a patient - not in the activity counts, not in the delivery
   report, and above all not in the access log. An oversight tool that
   discloses the people it exists to protect is worse than no tool.
"""

from datetime import time, timedelta

import pytest
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient

from apps.facilities.models import Facility, OpeningHours, ServiceType
from apps.notifications.models import Notification
from apps.patients.models import Patient, PatientAccessLog
from apps.queueing.models import QueueEntry
from apps.staff.models import StaffMember

FACILITIES = "/api/v1/platform/facilities"
PROVIDERS = "/api/v1/platform/providers"
STAFF = "/api/v1/platform/staff"
ACTIVITY = "/api/v1/platform/activity"
ACCESS_LOG = "/api/v1/platform/access-log"
DELIVERY = "/api/v1/platform/delivery"

OVERSIGHT = [FACILITIES, PROVIDERS, STAFF, ACTIVITY, ACCESS_LOG, DELIVERY]


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


@pytest.fixture
def facility(db):
    f = Facility.objects.create(
        name="Kimironko HC", slug="kimironko-hc", ownership="public",
        level="health_centre", district="Gasabo",
        location=Point(30.11, -1.94, srid=4326),
        verified_at=timezone.now(), reports_queue=True,
    )
    for weekday in range(7):
        OpeningHours.objects.create(
            facility=f, weekday=weekday,
            opens_at=time(0, 0), closes_at=time(23, 59),
        )
    return f


@pytest.fixture
def general(db):
    return ServiceType.objects.create(
        code="general_consultation", name_en="General", name_rw="x", name_fr="x"
    )


# --------------------------------------------------------------------------
# 1. Who gets in
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_every_oversight_endpoint_is_superuser_only(client_as, db):
    editor = User.objects.create_user(
        username="lookup-editor", password="pw-for-tests", is_staff=True
    )
    anonymous = APIClient()

    for path in OVERSIGHT:
        assert anonymous.get(path).status_code in (401, 403), path
        assert client_as(editor).get(path).status_code == 403, path


@pytest.mark.django_db
def test_facility_staff_cannot_reach_oversight(client_as, facility):
    """A receptionist is scoped to one facility. These endpoints cross all
    of them."""
    user = User.objects.create_user(username="desk", password="pw-for-tests")
    StaffMember.objects.create(
        user=user, facility=facility, role="receptionist", active=True
    )

    for path in OVERSIGHT:
        assert client_as(user).get(path).status_code == 403, path


# --------------------------------------------------------------------------
# 2. Facilities and staff - the things that look fine and are not
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_facility_with_no_staff_is_visible_as_such(client_as, admin, facility):
    """A verified facility with no active staff account cannot check anybody
    in. It looks perfectly healthy from the patient side while doing nothing,
    and this count is the only place that shows up."""
    row = next(
        f for f in client_as(admin).get(FACILITIES).json()["results"]
        if f["slug"] == "kimironko-hc"
    )

    assert row["verified"] is True
    assert row["staff_count"] == 0


@pytest.mark.django_db
def test_the_staff_list_says_who_can_read_what(client_as, admin, facility):
    user = User.objects.create_user(username="desk", password="pw-for-tests")
    StaffMember.objects.create(
        user=user, facility=facility, role="receptionist", active=True
    )

    row = next(
        s for s in client_as(admin).get(STAFF).json()["results"]
        if s["username"] == "desk"
    )

    assert row["facility"] == "Kimironko HC"
    assert row["role"] == "receptionist"
    assert row["can_manage_queue"] is True
    assert row["active"] is True


@pytest.mark.django_db
def test_a_deactivated_user_reads_as_inactive(client_as, admin, facility):
    """Two switches can close this door - the StaffMember row and the Django
    user - and the list has to reflect either. Saying `active` while the user
    is disabled would send somebody hunting a problem that is already fixed."""
    user = User.objects.create_user(username="former", password="pw-for-tests")
    StaffMember.objects.create(
        user=user, facility=facility, role="receptionist", active=True
    )
    user.is_active = False
    user.save(update_fields=["is_active"])

    row = next(
        s for s in client_as(admin).get(STAFF).json()["results"]
        if s["username"] == "former"
    )

    assert row["active"] is False


@pytest.mark.django_db
def test_a_user_with_no_surface_is_counted(client_as, admin):
    """A Django user who is neither staff nor superuser can sign in and land
    nowhere. Worth a number rather than a support ticket."""
    User.objects.create_user(username="stranded", password="pw-for-tests")

    accounts = client_as(admin).get(STAFF).json()["accounts"]

    assert accounts["stranded"] == 1


# --------------------------------------------------------------------------
# 3. The access log - the control docs/08 built and nothing surfaced
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_access_log_never_names_the_patient(client_as, admin, facility):
    """The point of an access review is who did the touching. Naming the
    patient would make the oversight tool its own disclosure risk."""
    patient = Patient.objects.create(phone="+250788111222", full_name="A. Uwase")
    actor = User.objects.create_user(username="desk", password="pw-for-tests")
    PatientAccessLog.objects.create(
        actor=actor, patient=patient, facility=facility,
        action=PatientAccessLog.Action.VIEW,
    )

    body = str(client_as(admin).get(ACCESS_LOG).json())

    assert "desk" in body
    assert "Uwase" not in body
    assert "788111222" not in body


@pytest.mark.django_db
def test_the_access_log_groups_by_actor(client_as, admin, facility):
    """One "viewed 40 records" row is a queue board. Forty of them from one
    account is something else, and that only shows up grouped."""
    actor = User.objects.create_user(username="desk", password="pw-for-tests")
    for _ in range(5):
        PatientAccessLog.objects.create(
            actor=actor, facility=facility,
            action=PatientAccessLog.Action.BOARD, record_count=20,
        )

    body = client_as(admin).get(ACCESS_LOG).json()

    assert body["total_events"] == 5
    assert body["by_actor"][0]["actor"] == "desk"
    assert body["by_actor"][0]["events"] == 5


@pytest.mark.django_db
def test_a_patient_acting_on_their_own_record_is_labelled_not_named(
    client_as, admin
):
    """Exporting or erasing your own data is the one access nobody needs to
    review, and it is certainly not an anomaly worth a name."""
    patient = Patient.objects.create(phone="+250788111222", full_name="A. Uwase")
    PatientAccessLog.objects.create(
        acting_patient=patient, patient=patient,
        action=PatientAccessLog.Action.EXPORT,
    )

    body = client_as(admin).get(ACCESS_LOG).json()

    assert body["recent"][0]["actor"] == "the patient themselves"
    assert "Uwase" not in str(body)


@pytest.mark.django_db
def test_events_outside_the_window_are_excluded(client_as, admin, facility):
    actor = User.objects.create_user(username="desk", password="pw-for-tests")
    old = PatientAccessLog.objects.create(
        actor=actor, facility=facility, action=PatientAccessLog.Action.BOARD,
    )
    # auto_now_add ignores an assigned value, so it is moved afterwards.
    PatientAccessLog.objects.filter(pk=old.pk).update(
        occurred_at=timezone.now() - timedelta(days=30)
    )

    assert client_as(admin).get(ACCESS_LOG, {"days": "7"}).json()["total_events"] == 0
    assert client_as(admin).get(ACCESS_LOG, {"days": "60"}).json()["total_events"] == 1


# --------------------------------------------------------------------------
# 4. Delivery - a message that never sent is a patient still at home
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_delivery_failures_are_reported(client_as, admin):
    patient = Patient.objects.create(phone="+250788111222")
    Notification.objects.create(
        patient=patient, phone=patient.phone, channel="sms",
        kind=Notification.Kind.CALLED, body="x", sent_at=timezone.now(),
    )
    Notification.objects.create(
        patient=patient, phone=patient.phone, channel="sms",
        kind=Notification.Kind.LEAVE_NOW, body="y", failed_at=timezone.now(),
    )

    body = client_as(admin).get(DELIVERY).json()

    assert body["total"] == 2
    assert body["sent"] == 1
    assert body["failed"] == 1
    assert body["failure_rate"] == 0.5


@pytest.mark.django_db
def test_delivery_reports_no_rate_when_nothing_was_sent(client_as, admin):
    """No messages is not a 100% success rate - the same rule the wait times
    follow."""
    assert client_as(admin).get(DELIVERY).json()["failure_rate"] is None


@pytest.mark.django_db
def test_no_message_body_is_ever_returned(client_as, admin):
    """Several kinds carry a queue position and one carries a sign-in code."""
    patient = Patient.objects.create(phone="+250788111222")
    Notification.objects.create(
        patient=patient, phone=patient.phone, channel="sms",
        kind=Notification.Kind.OTP, body="Your code is 123456",
        sent_at=timezone.now(),
    )

    body = str(client_as(admin).get(DELIVERY).json())

    assert "123456" not in body
    assert "Your code" not in body


# --------------------------------------------------------------------------
# 5. Activity - counts, never people
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_activity_reports_counts_never_patients(
    client_as, admin, facility, general
):
    patient = Patient.objects.create(phone="+250788111222", full_name="A. Uwase")
    QueueEntry.objects.create(
        facility=facility, service_type=general, patient=patient,
        ticket_code="G-1", status=QueueEntry.Status.WAITING,
    )

    body = client_as(admin).get(ACTIVITY).json()

    assert body["totals"]["waiting_now"] == 1
    assert "Uwase" not in str(body)
    assert "788111222" not in str(body)


@pytest.mark.django_db
def test_an_onboarded_but_idle_facility_is_countable(
    client_as, admin, facility, general
):
    """Verified, staffed, and nobody has ever been checked in. That is a
    facility onboarded on paper only, and it is invisible without this."""
    body = client_as(admin).get(ACTIVITY).json()

    assert body["totals"]["facilities_active"] == 0

    QueueEntry.objects.create(
        facility=facility, service_type=general, ticket_code="G-1",
        status=QueueEntry.Status.WAITING,
    )

    assert client_as(admin).get(ACTIVITY).json()["totals"]["facilities_active"] == 1


@pytest.mark.django_db
def test_the_oversight_windows_are_bounded(client_as, admin):
    """An unbounded window is a table scan somebody can ask for repeatedly."""
    for path in (ACTIVITY, ACCESS_LOG, DELIVERY):
        assert client_as(admin).get(path, {"days": "0"}).status_code == 400, path
        assert client_as(admin).get(path, {"days": "91"}).status_code == 400, path
