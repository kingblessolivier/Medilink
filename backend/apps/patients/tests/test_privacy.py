"""Data subject rights and the audit trail.

These are legal obligations under Rwanda Law N° 058/2021, not features. The
tests assert the two things that are easy to get wrong: an export that quietly
omits the sensitive part, and an erasure that either fails or takes the
facility's statistics down with it.
"""

from datetime import time, timedelta

import pytest
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient

from apps.facilities.models import Facility, OpeningHours, ServiceType
from apps.notifications.models import Notification
from apps.patients.auth import tokens_for_patient
from apps.patients.models import Patient, PatientAccessLog
from apps.patients.privacy import anonymise, export
from apps.queueing.models import QueueEntry
from apps.scheduling.models import Appointment
from apps.staff.models import StaffMember

EXPORT = "/api/v1/me/export"
DELETE = "/api/v1/me/delete"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def general(db):
    return ServiceType.objects.create(
        code="general_consultation",
        name_en="General consultation",
        name_rw="Kwivuza rusange",
        name_fr="Consultation generale",
    )


@pytest.fixture
def facility(db):
    facility = Facility.objects.create(
        name="Kimironko HC",
        slug="kimironko-hc",
        ownership="public",
        level="health_centre",
        district="Gasabo",
        location=Point(30.1122, -1.9481, srid=4326),
        verified_at=timezone.now(),
    )
    for weekday in range(7):
        OpeningHours.objects.create(
            facility=facility, weekday=weekday, opens_at=time(0, 0),
            closes_at=time(23, 59),
        )
    return facility


@pytest.fixture
def patient(db):
    return Patient.objects.create(
        phone="+250788111222",
        full_name="Uwase Alice",
        district="Gasabo",
        home_location=Point(30.06, -1.95, srid=4326),
    )


@pytest.fixture
def history(patient, facility, general):
    """One of everything, so the export and erasure paths are exercised."""
    now = timezone.now()
    QueueEntry.objects.create(
        facility=facility,
        service_type=general,
        patient=patient,
        ticket_code="G-001",
        joined_at=now - timedelta(hours=2),
        served_at=now - timedelta(hours=1),
        status=QueueEntry.Status.SERVED,
    )
    Appointment.objects.create(
        facility=facility,
        service_type=general,
        patient=patient,
        slot_start=now + timedelta(days=1),
        slot_end=now + timedelta(days=1, minutes=15),
    )
    Notification.objects.create(
        patient=patient,
        phone=patient.phone,
        channel=Notification.Channel.SMS,
        kind=Notification.Kind.LEAVE_NOW,
        body="MediLink: uri nomero 3.",
    )


def authed(client, patient):
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + tokens_for_patient(patient)["access"]
    )
    return client


# --------------------------------------------------------------------------
# Right of access
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_export_includes_the_sensitive_history(patient, history):
    """Which facility, for what, on what date - that is the sensitive part.
    An export that returns only the profile is not an export."""
    data = export(patient)

    assert data["profile"]["phone"] == "+250788111222"
    assert len(data["queue_entries"]) == 1
    assert data["queue_entries"][0]["facility"] == "Kimironko HC"
    assert len(data["appointments"]) == 1
    assert len(data["messages_sent_to_you"]) == 1


@pytest.mark.django_db
def test_export_states_that_triage_answers_are_not_held(patient):
    data = export(patient)

    assert "note" in data
    assert "discarded" in data["note"].lower()


@pytest.mark.django_db
def test_export_endpoint_is_a_download(api_client, patient, history):
    authed(api_client, patient)

    response = api_client.get(EXPORT)

    assert response.status_code == 200
    assert "attachment" in response["Content-Disposition"]


@pytest.mark.django_db
def test_export_returns_only_your_own_data(api_client, patient, facility, general, db):
    other = Patient.objects.create(phone="+250788999000", full_name="Someone Else")
    QueueEntry.objects.create(
        facility=facility, service_type=general, patient=other, ticket_code="G-009"
    )

    authed(api_client, patient)
    body = api_client.get(EXPORT).json()

    assert body["profile"]["phone"] == patient.phone
    assert body["queue_entries"] == []


@pytest.mark.django_db
def test_export_requires_a_patient_token(api_client, facility, db):
    user = User.objects.create_user(username="reception", password="test-pass-123")
    StaffMember.objects.create(user=user, facility=facility, role="receptionist")
    api_client.force_authenticate(user)

    assert api_client.get(EXPORT).status_code == 403


# --------------------------------------------------------------------------
# Right of erasure
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_erasure_keeps_the_facility_counts(patient, history, facility):
    """Deleting rows would corrupt ServiceTimeStat, and with it the wait
    estimate shown to every other patient at that facility."""
    anonymise(patient)

    assert QueueEntry.objects.filter(facility=facility).count() == 1
    assert Appointment.objects.filter(facility=facility).count() == 1


@pytest.mark.django_db
def test_erasure_severs_the_person_from_the_records(patient, history):
    anonymise(patient)

    entry = QueueEntry.objects.get()
    assert entry.patient_id is None
    assert entry.walk_in_name == ""

    appointment = Appointment.objects.get()
    assert appointment.patient_id is None
    assert appointment.status == Appointment.Status.CANCELLED


@pytest.mark.django_db
def test_erasure_clears_the_profile(patient, history):
    anonymise(patient)
    patient.refresh_from_db()

    assert patient.full_name == ""
    assert patient.district == ""
    assert patient.home_location is None
    assert patient.national_id_hash == ""
    assert not patient.phone.startswith("+250")
    assert patient.phone.startswith("del-")
    assert len(patient.phone) <= 20  # the column is varchar(20)


@pytest.mark.django_db
def test_erasure_removes_messages(patient, history):
    """Message bodies name facilities and times."""
    anonymise(patient)

    assert Notification.objects.filter(patient=patient).count() == 0


@pytest.mark.django_db
def test_two_erasures_do_not_collide(db, facility, general):
    """`phone` is unique, so blanking it would make the second erasure fail."""
    first = Patient.objects.create(phone="+250788111000")
    second = Patient.objects.create(phone="+250788222000")

    anonymise(first)
    anonymise(second)

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.phone != second.phone


@pytest.mark.django_db
def test_erasure_endpoint(api_client, patient, history):
    authed(api_client, patient)

    response = api_client.delete(DELETE)

    assert response.status_code == 204
    patient.refresh_from_db()
    assert patient.full_name == ""


# --------------------------------------------------------------------------
# Audit trail
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_check_in_is_attributable(api_client, facility, general, db):
    user = User.objects.create_user(username="reception", password="test-pass-123")
    StaffMember.objects.create(user=user, facility=facility, role="receptionist")
    api_client.force_authenticate(user)

    api_client.post(
        "/api/v1/queue/entries",
        {"service": general.code, "phone": "+250788111222"},
        format="json",
    )

    log = PatientAccessLog.objects.get(action=PatientAccessLog.Action.CHECK_IN)
    assert log.actor == user
    assert log.facility == facility
    assert log.patient is not None


@pytest.mark.django_db
def test_a_board_view_is_logged_once_with_a_count(
    api_client, facility, general, db
):
    """One row per bulk read, not one per patient - otherwise the anomaly this
    table exists to surface is buried in noise."""
    user = User.objects.create_user(username="reception", password="test-pass-123")
    StaffMember.objects.create(user=user, facility=facility, role="receptionist")
    for index in range(3):
        QueueEntry.objects.create(
            facility=facility,
            service_type=general,
            walk_in_name=f"P{index}",
            ticket_code=f"G-{index:03d}",
        )

    api_client.force_authenticate(user)
    api_client.get("/api/v1/queue/board")

    log = PatientAccessLog.objects.get(action=PatientAccessLog.Action.BOARD)
    assert log.record_count == 3
    assert log.patient is None


@pytest.mark.django_db
def test_patient_self_service_is_attributed_to_the_patient(
    api_client, patient, history
):
    authed(api_client, patient)
    api_client.get(EXPORT)

    log = PatientAccessLog.objects.get(action=PatientAccessLog.Action.EXPORT)
    assert log.acting_patient == patient
    assert log.actor is None


@pytest.mark.django_db
def test_erasure_is_logged_before_the_link_is_broken(api_client, patient, history):
    authed(api_client, patient)

    api_client.delete(DELETE)

    log = PatientAccessLog.objects.get(action=PatientAccessLog.Action.ERASE)
    assert log.acting_patient_id == patient.pk


@pytest.mark.django_db
def test_an_audit_failure_never_breaks_the_request(
    api_client, facility, general, db, monkeypatch
):
    """A reception desk that stops working because logging failed is worse
    than a missing log line."""
    from apps.patients import audit

    def boom(*args, **kwargs):
        raise RuntimeError("audit table gone")

    monkeypatch.setattr(audit.PatientAccessLog.objects, "create", boom)

    user = User.objects.create_user(username="reception", password="test-pass-123")
    StaffMember.objects.create(user=user, facility=facility, role="receptionist")
    api_client.force_authenticate(user)

    response = api_client.post(
        "/api/v1/queue/entries",
        {"service": general.code, "walk_in_name": "Uwase"},
        format="json",
    )

    assert response.status_code == 201
