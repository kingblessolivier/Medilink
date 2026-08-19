from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.notifications.models import Notification
from apps.notifications.services import dispatch

from .auth import IsPatient, current_patient, issue_otp, tokens_for_patient, verify_otp
from .models import normalise_phone
from .serializers import (
    OTPRequestSerializer,
    OTPVerifySerializer,
    PatientSerializer,
    TokenPairSerializer,
)


class OTPRequestThrottle(ScopedRateThrottle):
    scope = "otp"


@extend_schema(
    summary="Request a sign-in code",
    description=(
        "Always returns 204, whether or not the number is known - the response "
        "must not reveal which numbers are registered."
    ),
    request=OTPRequestSerializer,
    responses={204: None},
)
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([OTPRequestThrottle])
def otp_request(request):
    payload = OTPRequestSerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    try:
        phone = normalise_phone(payload.validated_data["phone"])
    except DjangoValidationError:
        # Do not leak whether the number was even well-formed.
        return Response(status=status.HTTP_204_NO_CONTENT)

    from django.conf import settings

    record = issue_otp(phone)
    dispatch(
        kind=Notification.Kind.OTP,
        phone=phone,
        code=record.plaintext,
        minutes=int(settings.OTP_LIFETIME.total_seconds() // 60),
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    summary="Exchange a sign-in code for tokens",
    request=OTPVerifySerializer,
    responses=TokenPairSerializer,
)
@api_view(["POST"])
@permission_classes([AllowAny])
def otp_verify(request):
    payload = OTPVerifySerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    phone = normalise_phone(payload.validated_data["phone"])
    patient = verify_otp(phone, payload.validated_data["code"])

    body = tokens_for_patient(patient)
    body["patient"] = PatientSerializer(patient).data
    return Response(body)


@extend_schema(
    summary="The signed-in patient",
    responses=PatientSerializer,
    methods=["GET"],
)
@extend_schema(
    summary="Update the signed-in patient",
    request=PatientSerializer,
    responses=PatientSerializer,
    methods=["PATCH"],
)
@api_view(["GET", "PATCH"])
@permission_classes([IsPatient])
def me(request):
    patient = current_patient(request)

    if request.method == "PATCH":
        serializer = PatientSerializer(patient, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(last_seen_at=timezone.now())
        return Response(serializer.data)

    return Response(PatientSerializer(patient).data)
