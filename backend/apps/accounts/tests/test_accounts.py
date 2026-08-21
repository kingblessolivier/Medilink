"""Unified sign-in.

The properties under test, in order of how much damage their absence causes:

1. A patient token still cannot satisfy a staff permission. Unifying the FORM
   must not unify the PRINCIPALS - that separation is what holds the
   facility-scoping model together.
2. The endpoint cannot be used to discover which usernames exist.
3. Usernames are unique across BOTH tables, because staff win the lookup.
4. Registering somebody else's phone number cannot take over their account.
"""

from datetime import time

import pytest
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient

from apps.facilities.models import Facility, OpeningHours
from apps.patients.models import Patient
from apps.staff.models import StaffMember

LOGIN = "/api/v1/auth/login"
REGISTER = "/api/v1/auth/register"
SESSION = "/api/v1/auth/session"
BOARD = "/api/v1/queue/board"
OVERVIEW = "/api/v1/platform/overview"

PASSWORD = "correct-horse-battery"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def facility(db):
    facility = Facility.objects.create(
        name="Kimironko HC", slug="kimironko-hc", ownership="public",
        level="health_centre", district="Gasabo",
        location=Point(30.11, -1.94, srid=4326),
        verified_at=timezone.now(), reports_queue=True,
    )
    for weekday in range(7):
        OpeningHours.objects.create(
            facility=facility, weekday=weekday,
            opens_at=time(0, 0), closes_at=time(23, 59),
        )
    return facility


@pytest.fixture
def receptionist(facility):
    user = User.objects.create_user(username="desk", password=PASSWORD)
    StaffMember.objects.create(
        user=user, facility=facility, role="receptionist", active=True
    )
    return user


@pytest.fixture
def admin(db):
    return User.objects.create_superuser(
        username="platform", password=PASSWORD, email="p@example.com"
    )


@pytest.fixture
def patient(db):
    p = Patient.objects.create(
        phone="+250788111222", username="alice", full_name="A. Uwase"
    )
    p.set_password(PASSWORD)
    p.save()
    return p


def bearer(api, token):
    api.credentials(HTTP_AUTHORIZATION="Bearer " + token)
    return api


# --------------------------------------------------------------------------
# 1. One form, three kinds
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_patient_signs_in(api, patient):
    body = api.post(
        LOGIN, {"username": "alice", "password": PASSWORD}, format="json"
    ).json()

    assert body["session"]["kind"] == "patient"
    assert body["session"]["display_name"] == "A. Uwase"
    assert body["access"]


@pytest.mark.django_db
def test_a_patient_may_use_their_phone_number_instead(api, patient):
    """The phone is the one credential every patient knows they have - it is
    what USSD, WhatsApp and every SMS we send already uses."""
    body = api.post(
        LOGIN, {"username": "+250788111222", "password": PASSWORD}, format="json"
    ).json()

    assert body["session"]["kind"] == "patient"


@pytest.mark.django_db
def test_a_local_phone_format_works_too(api, patient):
    body = api.post(
        LOGIN, {"username": "0788111222", "password": PASSWORD}, format="json"
    ).json()

    assert body["session"]["kind"] == "patient"


@pytest.mark.django_db
def test_a_receptionist_signs_in_and_carries_their_facility(api, receptionist):
    body = api.post(
        LOGIN, {"username": "desk", "password": PASSWORD}, format="json"
    ).json()

    assert body["session"]["kind"] == "staff"
    assert body["session"]["facility"]["slug"] == "kimironko-hc"
    assert body["session"]["can_manage_queue"] is True


@pytest.mark.django_db
def test_a_superuser_signs_in_as_admin(api, admin):
    body = api.post(
        LOGIN, {"username": "platform", "password": PASSWORD}, format="json"
    ).json()

    assert body["session"]["kind"] == "admin"


@pytest.mark.django_db
def test_a_user_who_is_neither_gets_a_null_kind(api, db):
    """They authenticated, but there is no surface for them. The client says
    so rather than looping them back to a form that keeps succeeding."""
    User.objects.create_user(username="nobody", password=PASSWORD)

    body = api.post(
        LOGIN, {"username": "nobody", "password": PASSWORD}, format="json"
    ).json()

    assert body["session"]["kind"] is None


@pytest.mark.django_db
def test_an_inactive_staff_member_is_not_staff(api, facility, db):
    """Deactivating somebody has to close the door, not just grey out a menu."""
    user = User.objects.create_user(username="former", password=PASSWORD)
    StaffMember.objects.create(
        user=user, facility=facility, role="receptionist", active=False
    )

    body = api.post(
        LOGIN, {"username": "former", "password": PASSWORD}, format="json"
    ).json()

    assert body["session"]["kind"] is None


# --------------------------------------------------------------------------
# 2. The principals stay separate - the control that matters most
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_patient_token_cannot_reach_a_staff_endpoint(api, patient, facility):
    """The whole point of the separation. A patient principal has no
    `staffmember`, so it cannot satisfy IsFacilityStaff no matter what a view
    forgets to check."""
    token = api.post(
        LOGIN, {"username": "alice", "password": PASSWORD}, format="json"
    ).json()["access"]

    assert bearer(api, token).get(BOARD).status_code in (401, 403)


@pytest.mark.django_db
def test_a_patient_token_cannot_reach_the_platform_portal(api, patient):
    token = api.post(
        LOGIN, {"username": "alice", "password": PASSWORD}, format="json"
    ).json()["access"]

    assert bearer(api, token).get(OVERVIEW).status_code in (401, 403)


@pytest.mark.django_db
def test_a_receptionist_token_cannot_reach_the_platform_portal(
    api, receptionist
):
    token = api.post(
        LOGIN, {"username": "desk", "password": PASSWORD}, format="json"
    ).json()["access"]

    assert bearer(api, token).get(OVERVIEW).status_code == 403


# --------------------------------------------------------------------------
# 3. No account enumeration
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_every_failure_looks_identical(api, patient, receptionist):
    """Unknown username, wrong password, and a real account with the wrong
    password must be indistinguishable. Anything else turns this endpoint into
    a way to find out who has an account here - at a health service."""
    responses = [
        api.post(LOGIN, {"username": "nobody-at-all", "password": "x"}, format="json"),
        api.post(LOGIN, {"username": "alice", "password": "wrong"}, format="json"),
        api.post(LOGIN, {"username": "desk", "password": "wrong"}, format="json"),
        api.post(LOGIN, {"username": "+250788111222", "password": "wrong"}, format="json"),
    ]

    assert {r.status_code for r in responses} == {401}
    assert len({r.json()["detail"] for r in responses}) == 1


@pytest.mark.django_db
def test_a_patient_without_a_password_cannot_be_signed_into(api, db):
    """USSD-only patients have no password. An empty hash must never match an
    empty submission."""
    Patient.objects.create(phone="+250788999000", username="ussd-only")

    for password in ("", " ", "None"):
        response = api.post(
            LOGIN, {"username": "ussd-only", "password": password}, format="json"
        )
        assert response.status_code in (400, 401), password


# --------------------------------------------------------------------------
# 4. Registration
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_registering_creates_a_patient_and_signs_them_in(api, db):
    response = api.post(
        REGISTER,
        {
            "username": "bosco",
            "password": PASSWORD,
            "phone": "0788444555",
            "full_name": "B. Habimana",
            "consent": True,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["session"]["kind"] == "patient"
    patient = Patient.objects.get(username="bosco")
    assert patient.phone == "+250788444555"
    # Never the raw value.
    assert patient.password != PASSWORD
    assert patient.check_password(PASSWORD)


@pytest.mark.django_db
def test_a_ussd_patient_can_claim_web_credentials(api, db):
    """Somebody who has used USSD for a year and now opens the website is the
    same person. Refusing them would force a second account on one number."""
    Patient.objects.create(phone="+250788777888", district="Gasabo")

    response = api.post(
        REGISTER,
        {
            "username": "claire",
            "password": PASSWORD,
            "phone": "0788777888",
            "consent": True,
        },
        format="json",
    )

    assert response.status_code == 201
    assert Patient.objects.filter(phone="+250788777888").count() == 1
    # And their history came with them.
    assert Patient.objects.get(phone="+250788777888").district == "Gasabo"


@pytest.mark.django_db
def test_registering_an_existing_account_cannot_reset_its_password(api, patient):
    """Otherwise anyone who knows a phone number could take over the account
    by 'registering' it."""
    response = api.post(
        REGISTER,
        {
            "username": "someone-else",
            "password": "attacker-chosen",
            "phone": "0788111222",
            "consent": True,
        },
        format="json",
    )

    assert response.status_code == 409
    patient.refresh_from_db()
    assert patient.check_password(PASSWORD)
    assert patient.username == "alice"


@pytest.mark.django_db
def test_a_patient_cannot_take_a_staff_username(api, receptionist):
    """Staff win the lookup in sign_in(), so a patient allowed to take one
    could never sign in again."""
    response = api.post(
        REGISTER,
        {"username": "desk", "password": PASSWORD, "phone": "0788444555", "consent": True},
        format="json",
    )

    assert response.status_code == 409
    assert not Patient.objects.filter(phone="+250788444555").exists()


@pytest.mark.django_db
def test_username_uniqueness_ignores_case(api, receptionist, db):
    response = api.post(
        REGISTER,
        {"username": "DESK", "password": PASSWORD, "phone": "0788444555", "consent": True},
        format="json",
    )

    assert response.status_code == 409


@pytest.mark.django_db
def test_two_patients_cannot_share_a_username(api, patient):
    response = api.post(
        REGISTER,
        {"username": "alice", "password": PASSWORD, "phone": "0788444555", "consent": True},
        format="json",
    )

    assert response.status_code == 409


@pytest.mark.django_db
def test_a_username_that_looks_like_a_phone_number_is_refused(api, db):
    """It would be ambiguous at sign-in, where the same field accepts both."""
    response = api.post(
        REGISTER,
        {"username": "+250788444555", "password": PASSWORD, "phone": "0788444555", "consent": True},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_a_short_password_is_refused(api, db):
    response = api.post(
        REGISTER,
        {"username": "shorty", "password": "abc", "phone": "0788444555", "consent": True},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_a_bad_phone_number_is_refused(api, db):
    response = api.post(
        REGISTER,
        {"username": "bosco", "password": PASSWORD, "phone": "12", "consent": True},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["field"] == "phone"


# --------------------------------------------------------------------------
# 5. Session
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_session_accepts_a_patient_token(api, patient):
    token = api.post(
        LOGIN, {"username": "alice", "password": PASSWORD}, format="json"
    ).json()["access"]

    body = bearer(api, token).get(SESSION).json()

    assert body["kind"] == "patient"
    assert body["display_name"] == "A. Uwase"


@pytest.mark.django_db
def test_session_accepts_a_staff_token(api, receptionist):
    token = api.post(
        LOGIN, {"username": "desk", "password": PASSWORD}, format="json"
    ).json()["access"]

    body = bearer(api, token).get(SESSION).json()

    assert body["kind"] == "staff"
    assert body["facility"]["name"] == "Kimironko HC"


@pytest.mark.django_db
def test_session_refuses_anonymous_callers(api):
    assert api.get(SESSION).status_code in (401, 403)


@pytest.mark.django_db
def test_the_session_carries_no_password_material(api, patient):
    token = api.post(
        LOGIN, {"username": "alice", "password": PASSWORD}, format="json"
    ).json()["access"]

    body = str(bearer(api, token).get(SESSION).json())

    assert "password" not in body.lower()
    assert PASSWORD not in body


# --------------------------------------------------------------------------
# 6. Rate limiting
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_repeated_guesses_get_throttled(api, patient, settings):
    """Password guessing is the attack this endpoint invites.

    Re-enabled explicitly here rather than globally - config/settings/test.py
    switches throttling off because the whole suite shares one IP and one
    cache, which made unrelated tests fail on a budget spent by earlier ones.
    """
    from django.core.cache import cache

    cache.clear()
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {"signin": "3/min"},
    }

    codes = [
        api.post(
            LOGIN, {"username": "alice", "password": f"guess-{n}"}, format="json"
        ).status_code
        for n in range(5)
    ]

    assert 429 in codes, codes
    # And the limit is on attempts, not on failures only - a correct password
    # after the budget is spent must not be a way around it.
    assert api.post(
        LOGIN, {"username": "alice", "password": PASSWORD}, format="json"
    ).status_code == 429
    cache.clear()


# --------------------------------------------------------------------------
# 7. Consent - Rwanda Law 058/2021, docs/08 section 6
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_registering_records_consent_with_a_timestamp_and_version(api, db):
    """"Captured and recorded" means both: when, and to WHAT. A later
    revision of the notice does not retroactively become what somebody
    agreed to."""
    api.post(
        REGISTER,
        {
            "username": "bosco",
            "password": PASSWORD,
            "phone": "0788444555",
            "consent": True,
        },
        format="json",
    )

    patient = Patient.objects.get(username="bosco")
    assert patient.consented_at is not None
    assert patient.consent_version != ""
    assert patient.has_consented is True


@pytest.mark.django_db
def test_registration_without_consent_is_refused(api, db):
    for payload in ({}, {"consent": False}):
        response = api.post(
            REGISTER,
            {
                "username": "bosco",
                "password": PASSWORD,
                "phone": "0788444555",
                **payload,
            },
            format="json",
        )
        assert response.status_code == 400, payload

    assert not Patient.objects.filter(username="bosco").exists()


@pytest.mark.django_db
def test_a_ussd_patient_has_no_consent_recorded(db):
    """Null, not a backfilled timestamp. Nobody collected it, and inventing a
    record of consent is worse than having none - it is the one field you can
    never honestly reconstruct."""
    patient = Patient.objects.create(phone="+250788777888")

    assert patient.consented_at is None
    assert patient.has_consented is False
