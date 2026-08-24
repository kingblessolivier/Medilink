"""Who is signing in, and what kind of thing they are.

One entry point for three kinds of principal. The rules that matter:

- **Staff are tried before patients.** Both failures return the identical
  message, so this cannot be used to discover which usernames exist.
- **Registration proves the phone number before it writes anything.** A
  verified one-time code is required, always. Attaching credentials to a
  number you have not proved you hold is account takeover of every patient
  who reached MediLink through USSD, WhatsApp or a reception desk, because
  all of them have a blank password.
- **Registration enforces uniqueness across BOTH tables.** Because staff win
  the lookup, a patient allowed to take an existing staff username would be
  locked out permanently - and a staff member who later took a patient's
  username would silently shadow them.
- **Patient principals stay non-Django.** Unifying the form must not unify the
  principals; see apps/patients/auth.py for why that separation holds the
  facility-scoping model together.
"""

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.patients.auth import tokens_for_patient, verify_otp
from apps.patients.models import Patient, normalise_phone


class Kind:
    ADMIN = "admin"
    STAFF = "staff"
    PATIENT = "patient"


class SignInFailed(Exception):
    """Deliberately carries no detail about which half of the pair was wrong."""


class UsernameTaken(Exception):
    pass


def _staff_tokens(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def username_is_free(username: str) -> bool:
    """Free means free in BOTH tables. See the module docstring."""
    return not (
        User.objects.filter(username__iexact=username).exists()
        or Patient.objects.filter(username__iexact=username).exists()
    )


def sign_in(username: str, password: str) -> tuple[dict, dict]:
    """Return (tokens, session) or raise SignInFailed."""
    username = (username or "").strip()
    if not username or not password:
        raise SignInFailed()

    # --- staff and platform admins ---------------------------------------
    user = authenticate(username=username, password=password)
    if user is not None:
        if not user.is_active:
            raise SignInFailed()
        return _staff_tokens(user), session_for_user(user)

    # --- patients ---------------------------------------------------------
    # A patient may sign in with the username they chose OR their phone
    # number, because the phone is the one credential every patient already
    # knows they have - it is what USSD, WhatsApp and every SMS we send uses.
    patient = Patient.objects.filter(username__iexact=username).first()
    if patient is None:
        try:
            patient = Patient.objects.filter(phone=normalise_phone(username)).first()
        except Exception:  # noqa: BLE001 - not a phone number, which is fine
            patient = None

    if patient is not None and patient.check_password(password):
        return tokens_for_patient(patient), session_for_patient(patient)

    # Identical failure for both branches.
    raise SignInFailed()


@transaction.atomic
def register_patient(
    *,
    username: str,
    password: str,
    phone: str,
    code: str,
    full_name: str = "",
    consent: bool = False,
) -> Patient:
    """Create, or attach web credentials to, a patient.

    A phone that already exists is NOT an error: somebody who has been using
    USSD for a year and now opens the website is the same person, and refusing
    them would force a second account against the same number.

    **That is exactly why a verified code is required.** "The same person" is
    an assumption, and until it is checked it is the attacker's assumption too:
    every patient created by a USSD session, a WhatsApp message or a reception
    check-in has a blank password, so without proof of the number anyone who
    knew it could claim that record - its visit history, its appointments, its
    home location - by registering over the top of it.

    `verify_otp` consumes the code and raises on a bad or expired one, so this
    runs before anything is written. It is required for a NEW number too: that
    also stops somebody registering a number they do not hold and receiving the
    SMS traffic meant for whoever eventually uses it.
    """
    username = username.strip()
    phone = normalise_phone(phone)

    # Raises OTPError (401) on a wrong, expired or already-used code.
    # Also creates the Patient row for a number we have never seen, so
    # `existing` below is always present by this point.
    verify_otp(phone, code)

    existing = Patient.objects.filter(phone=phone).first()

    # select_for_update on the row we are about to claim, so two simultaneous
    # registrations for the same phone cannot both pass the check below.
    if existing is not None:
        existing = Patient.objects.select_for_update().get(pk=existing.pk)
        if existing.password:
            # Already has web credentials. Sending them to sign-in is right,
            # and it avoids letting anybody overwrite a stranger's password by
            # "registering" their phone number.
            raise UsernameTaken(
                "An account already exists for that phone number. Sign in instead."
            )

    if not username_is_free(username) and (
        existing is None or (existing.username or "").lower() != username.lower()
    ):
        raise UsernameTaken("That username is taken.")

    patient = existing or Patient(phone=phone)
    patient.username = username
    patient.set_password(password)
    if full_name:
        patient.full_name = full_name

    # Recorded at the moment it is given, against the notice version in force.
    # The serializer has already refused anything but True.
    if consent:
        patient.consented_at = timezone.now()
        patient.consent_version = settings.PRIVACY_NOTICE_VERSION

    patient.save()
    return patient


# --------------------------------------------------------------------------
# Session: what the client needs to route on
# --------------------------------------------------------------------------


def session_for_user(user: User) -> dict:
    staff = getattr(user, "staffmember", None)

    if user.is_superuser:
        kind = Kind.ADMIN
    elif staff is not None and staff.active:
        kind = Kind.STAFF
    else:
        # A Django user who is neither. They authenticated, but there is no
        # surface for them - the client says so rather than looping them back
        # to a sign-in form that will keep succeeding.
        kind = None

    session = {
        "kind": kind,
        "display_name": user.get_full_name() or user.get_username(),
        "username": user.get_username(),
        "facility": None,
        "can_manage_queue": False,
    }

    if kind == Kind.STAFF:
        session["facility"] = {
            "id": staff.facility_id,
            "slug": staff.facility.slug,
            "name": staff.facility.name,
            "district": staff.facility.district,
        }
        session["can_manage_queue"] = staff.can_manage_queue

    return session


def session_for_patient(patient: Patient) -> dict:
    return {
        "kind": Kind.PATIENT,
        "display_name": patient.full_name or patient.phone,
        "username": patient.username or patient.phone,
        "facility": None,
        "can_manage_queue": False,
    }
