import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.facilities.models import ServiceType
from apps.patients.auth import IsPatient, current_patient
from apps.staff.permissions import IsFacilityStaff, IsQueueManager, active_staff

from .models import QueueEntry
from .serializers import (
    BoardSerializer,
    CheckInResponseSerializer,
    CheckInSerializer,
    QueueEntryPublicSerializer,
    QueueEntrySerializer,
    SyncResponseSerializer,
    SyncSerializer,
)
from .services import TRANSITIONS, QueueError, check_in, eta_for

logger = logging.getLogger(__name__)


def _conflict(message):
    return Response(
        {"type": "conflict", "detail": str(message)},
        status=status.HTTP_409_CONFLICT,
    )


def _scoped_entry(request, pk) -> QueueEntry:
    """Fetch an entry, scoped to the caller's facility.

    Returning 404 rather than 403 for another facility's entry avoids
    confirming that the id exists.
    """
    staff = active_staff(request)
    return get_object_or_404(
        QueueEntry.objects.select_related("facility", "service_type", "patient"),
        pk=pk,
        facility_id=staff.facility_id,
    )


@extend_schema(
    summary="Check a patient in",
    description=(
        "The most performance-sensitive write in the system. Send an "
        "Idempotency-Key header: a retry after a network timeout must return "
        "the original entry, not create a duplicate."
    ),
    request=CheckInSerializer,
    responses=CheckInResponseSerializer,
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsQueueManager])
def check_in_view(request):
    staff = active_staff(request)
    payload = CheckInSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    data = payload.validated_data

    service_type = get_object_or_404(ServiceType, code=data["service"])

    try:
        entry, created = check_in(
            facility=staff.facility,
            service_type=service_type,
            phone=data.get("phone") or None,
            walk_in_name=data.get("walk_in_name", ""),
            staff_user=request.user,
            idempotency_key=request.headers.get("Idempotency-Key", ""),
            joined_at=data.get("client_recorded_at"),
        )
    except QueueError as exc:
        return _conflict(exc)
    except DjangoValidationError as exc:
        return Response(
            {"type": "validation_error", "detail": exc.messages[0], "field": "phone"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    body = QueueEntrySerializer(entry).data
    body.update(eta_for(entry))
    return Response(
        body,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@extend_schema(
    summary="Queue board for the caller's facility",
    responses=BoardSerializer,
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsFacilityStaff])
def board(request):
    """Everything the reception screen needs, grouped by service."""
    staff = active_staff(request)
    entries = (
        QueueEntry.objects.filter(
            facility_id=staff.facility_id, status__in=QueueEntry.OPEN_STATUSES
        )
        .select_related("service_type", "patient")
        .order_by("service_type__sort_order", "joined_at")
    )

    grouped: dict[str, dict] = {}
    for entry in entries:
        code = entry.service_type.code
        group = grouped.setdefault(
            code,
            {
                "service": code,
                "service_name_rw": entry.service_type.name_rw,
                "service_name_en": entry.service_type.name_en,
                "waiting": [],
                "called": [],
            },
        )
        bucket = "waiting" if entry.status == QueueEntry.Status.WAITING else "called"
        group[bucket].append(QueueEntrySerializer(entry).data)

    return Response(
        {
            "facility": {
                "name": staff.facility.name,
                "slug": staff.facility.slug,
            },
            "as_of": timezone.localtime().isoformat(),
            "services": list(grouped.values()),
        }
    )


@extend_schema(
    operation_id="queue_entry_transition",
    summary="Move a queue entry: call, serve, skip or cancel",
    request=None,  # the action is in the path; there is no body
    responses=QueueEntrySerializer,
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsQueueManager])
def transition(request, pk, action):
    entry = _scoped_entry(request, pk)
    handler = TRANSITIONS.get(action)
    if handler is None:
        return Response(
            {"type": "not_found", "detail": f"Unknown action {action}."},
            status=status.HTTP_404_NOT_FOUND,
        )
    try:
        handler(entry)
    except QueueError as exc:
        return _conflict(exc)

    if action == "call":
        # Best effort: a failed SMS must never fail the receptionist's action.
        from apps.notifications.tasks import send_called_notification

        try:
            send_called_notification(entry)
        except Exception:  # noqa: BLE001
            logger.exception("called_notification_failed", extra={"entry": entry.pk})

    return Response(QueueEntrySerializer(entry).data)


@extend_schema(
    summary="One queue entry (patient-facing view)",
    responses=QueueEntryPublicSerializer,
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def entry_detail(request, pk):
    """Polled by the patient every 20 seconds.

    Scoped to the caller: a patient sees only their own entry, and facility
    staff see only entries at their own facility. Without this, an enumerated
    id reveals a stranger's position in a health queue.
    """
    queryset = QueueEntry.objects.select_related("facility", "service_type", "patient")

    patient = getattr(request.user, "patient", None)
    if patient is not None:
        entry = get_object_or_404(queryset, pk=pk, patient=patient)
    else:
        staff = active_staff(request)
        entry = get_object_or_404(queryset, pk=pk, facility_id=staff.facility_id)

    return Response(QueueEntryPublicSerializer(entry).data)


@extend_schema(
    summary="The signed-in patient's active queue entry",
    responses=QueueEntryPublicSerializer,
)
@api_view(["GET"])
@permission_classes([IsPatient])
def current_entry(request):
    """What the patient home screen calls on load to choose between
    state A (nothing active) and state B (in a queue).

    204 when there is nothing active - an empty body, not an error.
    """
    patient = current_patient(request)
    entry = (
        QueueEntry.objects.filter(
            patient=patient, status__in=QueueEntry.OPEN_STATUSES
        )
        .select_related("facility", "service_type", "patient")
        .order_by("-joined_at")
        .first()
    )
    if entry is None:
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(QueueEntryPublicSerializer(entry).data)


@extend_schema(
    summary="Replay actions recorded while the reception client was offline",
    request=SyncSerializer,
    responses=SyncResponseSerializer,
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsQueueManager])
def sync(request):
    """Apply queued offline actions, oldest client timestamp first.

    Per-item results, so one rejected action does not fail the whole batch -
    a receptionist reconnecting after an hour must not lose the other 39
    check-ins because one patient was a duplicate.
    """
    staff = active_staff(request)
    payload = SyncSerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    actions = sorted(
        payload.validated_data["actions"], key=lambda a: a["client_recorded_at"]
    )

    results = []
    for action in actions:
        key, kind = action["key"], action["type"]
        try:
            if kind == "check_in":
                data = CheckInSerializer(data=action["payload"])
                data.is_valid(raise_exception=True)
                service_type = ServiceType.objects.get(
                    code=data.validated_data["service"]
                )
                entry, created = check_in(
                    facility=staff.facility,
                    service_type=service_type,
                    phone=data.validated_data.get("phone") or None,
                    walk_in_name=data.validated_data.get("walk_in_name", ""),
                    staff_user=request.user,
                    idempotency_key=key,
                    # The receptionist's clock, not the server's arrival time.
                    joined_at=action["client_recorded_at"],
                )
                results.append(
                    {
                        "key": key,
                        "ok": True,
                        "created": created,
                        "entry_id": entry.id,
                        "ticket_code": entry.ticket_code,
                    }
                )
            else:
                entry = QueueEntry.objects.get(
                    pk=action["payload"].get("entry_id"),
                    facility_id=staff.facility_id,
                )
                TRANSITIONS[kind](entry)
                results.append({"key": key, "ok": True, "entry_id": entry.id})
        except QueueEntry.DoesNotExist:
            results.append(
                {"key": key, "ok": False, "error": "Queue entry no longer exists."}
            )
        except ServiceType.DoesNotExist:
            results.append({"key": key, "ok": False, "error": "Unknown service."})
        except (QueueError, DjangoValidationError) as exc:
            message = exc.messages[0] if hasattr(exc, "messages") else str(exc)
            results.append({"key": key, "ok": False, "error": message})

    return Response(
        {
            "applied": sum(1 for r in results if r["ok"]),
            "rejected": sum(1 for r in results if not r["ok"]),
            "results": results,
        }
    )
