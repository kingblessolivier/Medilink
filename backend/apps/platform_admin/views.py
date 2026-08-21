"""Platform administration.

Django admin already does CRUD on every model. These endpoints serve the three
things it cannot: a verification workflow, platform aggregates, and triage
monitoring that reads outcomes without ever touching an answer.

Every endpoint is superuser-only - see permissions.py for why `is_staff` is
not enough.
"""

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.facilities.models import Facility
from apps.providers.models import Provider

from .permissions import IsPlatformAdmin
from .serializers import (
    AdminOverviewSerializer,
    TriageMonitoringSerializer,
    VerificationQueueSerializer,
    VerifiedSerializer,
    VerifySerializer,
)
from .services import overview, triage_monitoring, verification_queue

ADMIN_ONLY = [IsAuthenticated, IsPlatformAdmin]


def _window(request, default: int = 30, maximum: int = 365) -> int:
    """A bounded window. Unbounded is a table scan somebody can ask for."""
    try:
        days = int(request.query_params.get("days", default))
    except ValueError:
        raise ValidationError({"days": "Expected a number."})
    if not 1 <= days <= maximum:
        raise ValidationError({"days": f"Expected 1 to {maximum}."})
    return days


@extend_schema(
    summary="Platform-wide counts",
    parameters=[OpenApiParameter("days", int, description="1-365. Defaults to 30.")],
    responses=AdminOverviewSerializer,
)
@api_view(["GET"])
@permission_classes(ADMIN_ONLY)
def admin_overview(request):
    return Response(overview(days=_window(request)))


@extend_schema(
    summary="Facilities and providers awaiting verification",
    responses=VerificationQueueSerializer,
)
@api_view(["GET"])
@permission_classes(ADMIN_ONLY)
def admin_verification_queue(request):
    return Response(verification_queue())


@extend_schema(
    summary="Verify a facility, making it visible to patients",
    request=VerifySerializer,
    responses=VerifiedSerializer,
)
@api_view(["POST"])
@permission_classes(ADMIN_ONLY)
def verify_facility(request, pk: int):
    payload = VerifySerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    try:
        facility = Facility.objects.get(pk=pk)
    except Facility.DoesNotExist:
        raise NotFound("No such facility.")

    if facility.verified_at is not None:
        # Re-verifying would overwrite who checked it and when, losing the
        # only record of the original decision.
        raise ValidationError({"detail": "This facility is already verified."})

    facility.mark_verified(user=request.user, note=payload.validated_data["note"])

    return Response(
        {
            "id": facility.id,
            "name": facility.name,
            "verified_at": facility.verified_at,
            "verified_by": request.user.get_username(),
        }
    )


@extend_schema(
    summary="Verify a provider's listing",
    request=VerifySerializer,
    responses=VerifiedSerializer,
)
@api_view(["POST"])
@permission_classes(ADMIN_ONLY)
def verify_provider(request, pk: int):
    payload = VerifySerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    try:
        provider = Provider.objects.get(pk=pk)
    except Provider.DoesNotExist:
        raise NotFound("No such provider.")

    if provider.verified_at is not None:
        raise ValidationError({"detail": "This provider is already verified."})

    provider.verified_at = timezone.now()
    provider.save(update_fields=["verified_at"])

    return Response(
        {
            "id": provider.id,
            "name": provider.full_name,
            "verified_at": provider.verified_at,
            "verified_by": request.user.get_username(),
        }
    )


@extend_schema(
    summary="Triage outcome aggregates - never answers",
    parameters=[OpenApiParameter("days", int, description="1-365. Defaults to 30.")],
    responses=TriageMonitoringSerializer,
)
@api_view(["GET"])
@permission_classes(ADMIN_ONLY)
def admin_triage_monitoring(request):
    return Response(triage_monitoring(days=_window(request)))
