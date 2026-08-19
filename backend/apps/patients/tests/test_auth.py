"""Patient authentication.

The critical property is isolation: a patient token must never satisfy a staff
permission, no matter what a view forgets to check.
"""

from datetime import time, timedelta

import pytest
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient

from apps.facilities.models import Facility, OpeningHours, ServiceType
from apps.notifications.models import Notification
from apps.patients.auth import issue_otp, tokens_for_patient
from apps.patients.models import Patient
from apps.staff.models import StaffMember

REQUEST = "/api/v1/auth/otp/request"
VERIFY = "/api/v1/auth/otp/verify"


@pytest.fixture
def api_client():
    return APIClient()


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
            facility=facility,
            weekday=weekday,
            opens_at=time(0, 0),
            closes_at=time(23, 59),
        )
    return facility


@pytest.fixture
def general(db):
    return ServiceType.objects.create(
        code="general_consultation",
        name_en="General consultation",
        name_rw="Kwivuza rusange",
        name_fr="Consultation generale",
    )


@pytest.fixture
def patient(db):
    return Patient.objects.create(phone="+250788111222")


def authed(client, patient):
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + tokens_for_patient(patient)["access"]
    )
    return client


# --------------------------------------------------------------------------
# OTP
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_otp_request_never_reveals_whether_a_number_is_known(api_client, patient):
    known = api_client.post(REQUEST, {"phone": "+250788111222"}, format="json")
    unknown = api_client.post(REQUEST, {"phone": "+250788999888"}, format="json")
    malformed = api_client.post(REQUEST, {"phone": "not-a-phone"}, format="json")

    assert known.status_code == 204
    assert unknown.status_code == 204
    assert malformed.status_code == 204
    assert known.content == unknown.content == malformed.content == b""


@pytest.mark.django_db
def test_otp_request_sends_a_code(api_client):
    api_client.post(REQUEST, {"phone": "0788111222"}, format="json")

    notification = Notification.objects.get(kind=Notification.Kind.OTP)
    assert notification.phone == "+250788111222"
    assert notification.sent_at is not None


@pytest.mark.django_db
def test_the_code_itself_is_never_stored(api_client):
    record = issue_otp("+250788111222")

    from apps.patients.models import OTPCode

    stored = OTPCode.objects.get(pk=record.pk)
    assert record.plaintext not in stored.code_hash
    assert len(stored.code_hash) == 64


@pytest.mark.django_db
def test_verify_returns_tokens_and_creates_the_patient(api_client):
    record = issue_otp("+250788333444")

    response = api_client.post(
        VERIFY,
        {"phone": "+250788333444", "code": record.plaintext},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access"] and body["refresh"]
    assert body["patient"]["phone"] == "+250788333444"
    assert Patient.objects.filter(phone="+250788333444").exists()


@pytest.mark.django_db
def test_a_code_can_be_used_only_once(api_client):
    record = issue_otp("+250788111222")
    payload = {"phone": "+250788111222", "code": record.plaintext}

    assert api_client.post(VERIFY, payload, format="json").status_code == 200
    assert api_client.post(VERIFY, payload, format="json").status_code == 401


@pytest.mark.django_db
def test_wrong_code_is_rejected_and_counted(api_client):
    issue_otp("+250788111222")

    response = api_client.post(
        VERIFY, {"phone": "+250788111222", "code": "000000"}, format="json"
    )

    assert response.status_code == 401

    from apps.patients.models import OTPCode

    assert OTPCode.objects.get().attempts == 1


@pytest.mark.django_db
def test_code_locks_after_too_many_attempts(api_client, settings):
    record = issue_otp("+250788111222")

    for _ in range(settings.OTP_MAX_ATTEMPTS):
        api_client.post(
            VERIFY, {"phone": "+250788111222", "code": "000000"}, format="json"
        )

    # Even the correct code is refused once the record is burnt.
    response = api_client.post(
        VERIFY,
        {"phone": "+250788111222", "code": record.plaintext},
        format="json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_expired_code_is_rejected(api_client):
    record = issue_otp("+250788111222")

    from apps.patients.models import OTPCode

    OTPCode.objects.filter(pk=record.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )

    response = api_client.post(
        VERIFY,
        {"phone": "+250788111222", "code": record.plaintext},
        format="json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_requesting_a_new_code_invalidates_the_previous_one(api_client):
    first = issue_otp("+250788111222")
    issue_otp("+250788111222")

    response = api_client.post(
        VERIFY, {"phone": "+250788111222", "code": first.plaintext}, format="json"
    )
    assert response.status_code == 401


# --------------------------------------------------------------------------
# Isolation between patient and staff identities
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_patient_token_cannot_reach_staff_endpoints(api_client, patient, facility):
    """The property the whole two-identity design exists to guarantee."""
    authed(api_client, patient)

    for path in ("/api/v1/queue/board", "/api/v1/staff/me"):
        assert api_client.get(path).status_code == 403


@pytest.mark.django_db
def test_a_patient_token_cannot_check_anyone_in(
    api_client, patient, facility, general
):
    authed(api_client, patient)

    response = api_client.post(
        "/api/v1/queue/entries",
        {"service": general.code, "walk_in_name": "Someone"},
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_a_staff_token_cannot_reach_patient_endpoints(api_client, facility):
    user = User.objects.create_user(username="reception", password="test-pass-123")
    StaffMember.objects.create(user=user, facility=facility, role="receptionist")
    api_client.force_authenticate(user)

    assert api_client.get("/api/v1/me").status_code == 403
    assert api_client.get("/api/v1/queue/current").status_code == 403


@pytest.mark.django_db
def test_me_returns_and_updates_the_signed_in_patient(api_client, patient, db):
    from apps.insurance.models import Insurer

    Insurer.objects.create(code="mutuelle", name="Mutuelle de Sante")
    authed(api_client, patient)

    assert api_client.get("/api/v1/me").json()["phone"] == patient.phone

    response = api_client.patch(
        "/api/v1/me",
        {
            "full_name": "Uwase Alice",
            "language": "en",
            "insurer": "mutuelle",
            "home_location": {"lat": -1.9536, "lng": 30.0606},
        },
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Uwase Alice"
    assert body["insurer"] == "mutuelle"
    assert body["home_location"] == {"lat": -1.9536, "lng": 30.0606}


@pytest.mark.django_db
def test_anonymous_callers_cannot_reach_patient_endpoints(api_client):
    for path in ("/api/v1/me", "/api/v1/queue/current", "/api/v1/appointments"):
        assert api_client.get(path).status_code in (401, 403)
