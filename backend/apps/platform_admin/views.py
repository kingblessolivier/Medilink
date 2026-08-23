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

from .oversight import (
    access_log,
    account_summary,
    delivery_report,
    facility_directory,
    platform_activity,
    provider_directory,
    staff_directory,
)
from .permissions import IsPlatformAdmin
from .serializers import (
    AccessLogSerializer,
    AdminFacilityListSerializer,
    AdminOverviewSerializer,
    AdminProviderListSerializer,
    AdminStaffListSerializer,
    DeliveryReportSerializer,
    PlatformActivitySerializer,
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
        raise ValidationError({"days": "Expected a number."}) from None
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
        raise NotFound("No such facility.") from None

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
        raise NotFound("No such provider.") from None

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


# --------------------------------------------------------------------------
# Oversight: what is happening on the platform
#
# services.py answers "is the platform being used?". These answer "what is
# happening on it, and is anything wrong?" - the question somebody actually
# opens a dashboard to ask. All superuser-only; see permissions.py.
# --------------------------------------------------------------------------


@extend_schema(
    summary="Every facility, with what an admin can act on",
    responses=AdminFacilityListSerializer,
)
@api_view(["GET"])
@permission_classes(ADMIN_ONLY)
def admin_facilities(request):
    rows = facility_directory()
    return Response({"count": len(rows), "results": rows})


@extend_schema(
    summary="Every listed doctor",
    responses=AdminProviderListSerializer,
)
@api_view(["GET"])
@permission_classes(ADMIN_ONLY)
def admin_providers(request):
    rows = provider_directory()
    return Response({"count": len(rows), "results": rows})


@extend_schema(
    summary="Who can read patient records, and where",
    description=(
        "An access-control list. A dormant account left active is a standing "
        "door into one facility's patient data."
    ),
    responses=AdminStaffListSerializer,
)
@api_view(["GET"])
@permission_classes(ADMIN_ONLY)
def admin_staff(request):
    rows = staff_directory()
    return Response(
        {"count": len(rows), "results": rows, "accounts": account_summary()}
    )


@extend_schema(
    summary="Operational state across every facility",
    parameters=[OpenApiParameter("days", int, description="1-90. Defaults to 7.")],
    responses=PlatformActivitySerializer,
)
@api_view(["GET"])
@permission_classes(ADMIN_ONLY)
def admin_activity(request):
    return Response(platform_activity(days=_window(request, default=7, maximum=90)))


@extend_schema(
    summary="Who looked at whose record",
    description=(
        "The audit trail from docs/08 section 6. The PATIENT is never named - "
        "who did the touching, how much and when is what an access review "
        "needs, and naming the patient would make the oversight tool its own "
        "disclosure risk."
    ),
    parameters=[OpenApiParameter("days", int, description="1-90. Defaults to 7.")],
    responses=AccessLogSerializer,
)
@api_view(["GET"])
@permission_classes(ADMIN_ONLY)
def admin_access_log(request):
    return Response(access_log(days=_window(request, default=7, maximum=90)))


@extend_schema(
    summary="Did the messages arrive?",
    description=(
        "A 'leave now' SMS that never sent is a patient still sitting at "
        "home. Message bodies are never returned - several carry a queue "
        "position and one carries a sign-in code."
    ),
    parameters=[OpenApiParameter("days", int, description="1-90. Defaults to 7.")],
    responses=DeliveryReportSerializer,
)
@api_view(["GET"])
@permission_classes(ADMIN_ONLY)
def admin_delivery(request):
    return Response(delivery_report(days=_window(request, default=7, maximum=90)))
