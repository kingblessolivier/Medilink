"""Patient authentication: phone plus a six-digit SMS code.

No passwords. Patients will not manage them, and password reuse across a health
service would be worse than an OTP.

Patient tokens are deliberately NOT Django users. A patient principal has no
`staffmember` attribute, so it can never satisfy IsFacilityStaff no matter what
a view forgets to check. Keeping the two identity types structurally separate
is what makes the facility-scoping model in docs/08 hold.
"""

import hashlib
import secrets

from django.conf import settings
from django.utils import timezone
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import authentication, exceptions, permissions, status
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import OTPCode, Patient


class OTPError(exceptions.APIException):
    """A bad or expired sign-in code.

    DRF downgrades AuthenticationFailed to 403 when no authenticator ran, which
    is what happens on an anonymous POST. Declaring 401 explicitly keeps the
    response honest: the credential was wrong, not the permission.
    """

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "That code is not correct."
    default_code = "authentication_required"


TOKEN_TYPE_CLAIM = "principal"
PATIENT_PRINCIPAL = "patient"


# --------------------------------------------------------------------------
# One-time codes
# --------------------------------------------------------------------------


def hash_code(phone: str, code: str) -> str:
    """Store a hash, never the code itself."""
    pepper = getattr(settings, "SECRET_KEY", "")
    return hashlib.sha256(f"{pepper}:{phone}:{code}".encode()).hexdigest()


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def issue_otp(phone: str) -> OTPCode:
    """Create a code. The caller is responsible for sending it."""
    # Only one live code per phone, so an attacker cannot farm several at once.
    OTPCode.objects.filter(phone=phone, consumed_at__isnull=True).update(
        consumed_at=timezone.now()
    )

    code = generate_code()
    record = OTPCode.objects.create(
        phone=phone,
        code_hash=hash_code(phone, code),
        expires_at=timezone.now() + settings.OTP_LIFETIME,
    )
    # Never persisted; handed straight to the SMS backend by the caller.
    record.plaintext = code
    return record


def verify_otp(phone: str, code: str) -> Patient:
    record = (
        OTPCode.objects.filter(phone=phone, consumed_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if record is None or record.expires_at <= timezone.now():
        raise OTPError("That code has expired. Request a new one.")

    if record.attempts >= settings.OTP_MAX_ATTEMPTS:
        record.consumed_at = timezone.now()
        record.save(update_fields=["consumed_at"])
        raise OTPError("Too many attempts. Request a new code.")

    if not secrets.compare_digest(record.code_hash, hash_code(phone, code)):
        record.attempts += 1
        record.save(update_fields=["attempts"])
        raise OTPError("That code is not correct.")

    record.consumed_at = timezone.now()
    record.save(update_fields=["consumed_at"])

    patient, _ = Patient.objects.get_or_create(phone=phone)
    Patient.objects.filter(pk=patient.pk).update(last_seen_at=timezone.now())
    return patient


# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------


class PatientRefreshToken(RefreshToken):
    @classmethod
    def for_patient(cls, patient: Patient) -> "PatientRefreshToken":
        token = cls()
        token["patient_id"] = patient.id
        token[TOKEN_TYPE_CLAIM] = PATIENT_PRINCIPAL
        return token


def tokens_for_patient(patient: Patient) -> dict:
    refresh = PatientRefreshToken.for_patient(patient)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class PatientPrincipal:
    """Stands in for request.user when a patient token is presented.

    Intentionally minimal: no `staffmember`, no permissions, no database
    identity beyond the patient row.
    """

    is_authenticated = True
    is_anonymous = False
    is_staff = False
    is_superuser = False
    # Part of the contract every permission class assumes of request.user.
    # Its absence was not a missing feature but a 500: IsPlatformAdmin reads
    # `user.is_active`, so a patient token aimed at the platform portal raised
    # AttributeError instead of being refused. Minimal is good; incomplete is
    # not, and "deny" has to be reachable for a principal that fails the check.
    is_active = True

    def __init__(self, patient: Patient):
        self.patient = patient

    @property
    def pk(self):
        return self.patient.pk

    def __str__(self) -> str:
        return f"patient:{self.patient.pk}"


class PatientJWTAuthentication(authentication.BaseAuthentication):
    """Accepts only tokens carrying the patient principal claim.

    Staff tokens fall through untouched so that the standard
    JWTAuthentication class handles them.
    """

    keyword = "Bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).split()
        if not header or header[0].lower() != self.keyword.lower().encode():
            return None
        if len(header) != 2:
            return None

        try:
            token = PatientRefreshToken.access_token_class(header[1].decode())
        except (TokenError, InvalidToken):
            return None

        if token.get(TOKEN_TYPE_CLAIM) != PATIENT_PRINCIPAL:
            return None  # a staff token - let JWTAuthentication handle it

        patient = Patient.objects.filter(pk=token.get("patient_id")).first()
        if patient is None:
            raise exceptions.AuthenticationFailed("This account no longer exists.")

        return PatientPrincipal(patient), token


class IsPatient(permissions.BasePermission):
    message = "Sign in with your phone number to do that."

    def has_permission(self, request, view):
        return isinstance(request.user, PatientPrincipal)


def current_patient(request) -> Patient:
    if not isinstance(request.user, PatientPrincipal):
        raise exceptions.NotAuthenticated("Sign in with your phone number.")
    return request.user.patient


class PatientJWTScheme(OpenApiAuthenticationExtension):
    """Describes the patient bearer token in the OpenAPI schema.

    Without this, drf-spectacular cannot resolve the custom authenticator and
    every endpoint is emitted with no security scheme at all.
    """

    target_class = "apps.patients.auth.PatientJWTAuthentication"
    name = "patientJWT"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Patient token from POST /auth/otp/verify. Structurally "
                "separate from staff tokens: it can never satisfy a staff "
                "permission."
            ),
        }
