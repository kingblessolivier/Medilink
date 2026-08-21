from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.patients.auth import IsPatient, current_patient

from .models import OPTIONAL_KINDS, Notification, NotificationPreference
from .serializers import (
    NotificationListSerializer,
    NotificationSerializer,
    PreferenceListSerializer,
    PreferenceUpdateSerializer,
)

# Shown in the preferences screen, in the order a patient cares about them.
LISTED_KINDS = [
    Notification.Kind.LEAVE_NOW,
    Notification.Kind.CALLED,
    Notification.Kind.APPT_REMINDER_24H,
    Notification.Kind.APPT_REMINDER_2H,
    Notification.Kind.APPT_CANCELLED,
]

# A sign-in code is never listed: it is not a message somebody receives, it is
# one they asked for by trying to sign in.
HISTORY_EXCLUDES = [Notification.Kind.OTP]


@extend_schema(
    operation_id="notification_list",
    summary="Messages MediLink has sent you",
    responses=NotificationListSerializer,
)
@api_view(["GET"])
@permission_classes([IsPatient])
def notifications(request):
    patient = current_patient(request)
    queryset = (
        Notification.objects.filter(patient=patient)
        .exclude(kind__in=HISTORY_EXCLUDES)
        # Only what actually went out. A queued-but-failed message is an
        # operational problem, not something to show a patient as received.
        .filter(sent_at__isnull=False)
        .order_by("-sent_at")
    )
    total = queryset.count()
    return Response(
        {"count": total, "results": NotificationSerializer(queryset[:50], many=True).data}
    )


@extend_schema(
    operation_id="notification_preferences",
    summary="Which messages you receive",
    responses=PreferenceListSerializer,
    methods=["GET"],
)
@extend_schema(
    operation_id="notification_preferences_update",
    summary="Turn one kind of message on or off",
    request=PreferenceUpdateSerializer,
    responses=PreferenceListSerializer,
    methods=["PATCH"],
)
@api_view(["GET", "PATCH"])
@permission_classes([IsPatient])
def preferences(request):
    patient = current_patient(request)

    if request.method == "PATCH":
        payload = PreferenceUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        kind = payload.validated_data["kind"]

        if kind not in OPTIONAL_KINDS:
            # Refused rather than silently ignored: a toggle that appears to
            # work and does nothing is worse than one that says no.
            return Response(
                {
                    "type": "validation_error",
                    "detail": "That message cannot be switched off.",
                    "field": "kind",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        NotificationPreference.objects.update_or_create(
            patient=patient,
            kind=kind,
            defaults={"enabled": payload.validated_data["enabled"]},
        )

    return Response({"results": _current(patient)})


def _current(patient) -> list:
    labels = dict(Notification.Kind.choices)
    return [
        {
            "kind": kind,
            "label": labels[kind],
            "enabled": NotificationPreference.is_enabled(patient, kind),
            "can_disable": kind in OPTIONAL_KINDS,
        }
        for kind in LISTED_KINDS
    ]
