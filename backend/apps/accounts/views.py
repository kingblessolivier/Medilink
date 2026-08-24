"""Unified sign-in, registration, and "who am I".

One door for patients, facility staff and platform admins. See README.md in
this directory for the reasoning, and services.py for the rules.
"""

from django.conf import settings
from django.contrib.auth.models import User
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.patients.auth import PatientJWTAuthentication
from apps.patients.models import Patient

from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    SessionSerializer,
    SignInResponseSerializer,
)
from .services import (
    SignInFailed,
    UsernameTaken,
    register_patient,
    session_for_patient,
    session_for_user,
    sign_in,
)


class SignInThrottle(AnonRateThrottle):
    """Password guessing is the attack this endpoint invites.

    Separate from the global anon bucket so that ordinary browsing cannot use
    up a would-be attacker's budget, and vice versa.
    """

    scope = "signin"

    def get_rate(self):
        """No configured rate means no throttling, rather than a 500.

        This throttle is attached to the view directly, so clearing
        DEFAULT_THROTTLE_CLASSES does not detach it - which is how the test
        settings switch throttling off everywhere else. Without this the suite
        would either crash here or reintroduce the shared-IP flakiness that
        config/settings/test.py exists to prevent.
        """
        rates = getattr(settings, "REST_FRAMEWORK", {}).get(
            "DEFAULT_THROTTLE_RATES", {}
        )
        return rates.get(self.scope)


@extend_schema(
    summary="Sign in with a username and password",
    description=(
        "One endpoint for patients, facility staff and platform admins. The "
        "response says which kind the caller is; the client routes on that. A "
        "patient may use either their username or their phone number."
    ),
    request=LoginSerializer,
    responses=SignInResponseSerializer,
)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([SignInThrottle])
def login(request):
    payload = LoginSerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    try:
        tokens, session = sign_in(
            payload.validated_data["username"], payload.validated_data["password"]
        )
    except SignInFailed:
        # One message for every failure mode: unknown username, wrong
        # password, deactivated account. Anything more specific turns this
        # into a way to enumerate who has an account.
        return Response(
            {
                "type": "authentication_required",
                "detail": "That username and password did not match.",
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    return Response({**tokens, "session": session})


@extend_schema(
    summary="Register as a patient",
    description=(
        "Creates a patient account, or attaches web credentials to a phone "
        "number that has only ever used USSD. Staff and admin accounts are "
        "created by MediLink, never self-served.\n\n"
        "Requires a one-time code from POST /auth/otp/request. Registration "
        "writes to whatever record already holds that number, so the number "
        "must be proved first - otherwise anyone knowing it could claim that "
        "patient's history. Returns 401 if the code is wrong or expired."
    ),
    request=RegisterSerializer,
    responses=SignInResponseSerializer,
)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([SignInThrottle])
def register(request):
    payload = RegisterSerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    try:
        patient = register_patient(**payload.validated_data)
    except UsernameTaken as exc:
        return Response(
            {"type": "conflict", "detail": str(exc)},
            status=status.HTTP_409_CONFLICT,
        )

    tokens, session = sign_in(
        patient.username, payload.validated_data["password"]
    )
    return Response(
        {**tokens, "session": session}, status=status.HTTP_201_CREATED
    )


@extend_schema(
    summary="The signed-in caller and what kind of thing they are",
    description=(
        "The client calls this on load to decide which surface to show. It "
        "accepts either principal - a staff/admin JWT or a patient JWT."
    ),
    responses=SessionSerializer,
)
@api_view(["GET"])
# Both authenticators, and the ORDER matters. DRF stops the chain the moment
# one raises; only returning None means "try the next". PatientJWTAuthentication
# returns None for a staff token, so it is safe to run first - whereas
# SimpleJWT's raises on a patient token and would reject it before the patient
# authenticator ever saw it.
@authentication_classes([PatientJWTAuthentication, JWTAuthentication])
@permission_classes([IsAuthenticated])
def session(request):
    principal = request.user
    patient = getattr(principal, "patient", None)

    if isinstance(patient, Patient):
        return Response(session_for_patient(patient))
    if isinstance(principal, User):
        return Response(session_for_user(principal))

    # Authenticated as something this endpoint does not know how to describe.
    # Fail closed rather than guessing at a surface to send them to.
    return Response(
        {
            "kind": None,
            "display_name": "",
            "username": "",
            "facility": None,
            "can_manage_queue": False,
        }
    )
