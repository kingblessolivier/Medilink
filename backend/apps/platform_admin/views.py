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
    AdminInsurerListSerializer,
    AdminInsurerSerializer,
    AdminInsurerWriteSerializer,
    AdminOverviewSerializer,
    AdminProviderListSerializer,
    AdminStaffListSerializer,
    DeliveryReportSerializer,
    PlatformActivitySerializer,
    PlatformSettingsSerializer,
    PlatformSettingsWriteSerializer,
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


# --------------------------------------------------------------------------
# Insurers
# --------------------------------------------------------------------------
#
# Insurers were a fixture file, so adding one was a deploy. There are a
# handful in Rwanda and the list changes rarely - but "rarely" is not "never",
# and a scheme launching mid-year should not wait for a release.
#
# Deactivating rather than deleting: an insurer with facilities pointing at it
# cannot be removed without silently dropping their acceptance records, and a
# facility that stops appearing under Mutuelle because somebody tidied a list
# is a patient sent to the wrong place.


@extend_schema(
    summary="Every insurer on the platform",
    responses=AdminInsurerListSerializer,
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def admin_insurers(request):
    from django.db.models import Count

    from apps.insurance.models import Insurer

    rows = Insurer.objects.annotate(
        facilities=Count("facilityinsurer", distinct=True)
    ).order_by("sort_order", "name")

    return Response(
        {
            "count": rows.count(),
            "results": [
                {
                    "code": row.code,
                    "name": row.name,
                    "is_public": row.is_public,
                    "sort_order": row.sort_order,
                    "facilities": row.facilities,
                }
                for row in rows
            ],
        }
    )


@extend_schema(
    summary="Add an insurer",
    request=AdminInsurerWriteSerializer,
    responses=AdminInsurerSerializer,
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def create_insurer(request):
    from apps.insurance.models import Insurer

    payload = AdminInsurerWriteSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    data = payload.validated_data

    if Insurer.objects.filter(code=data["code"]).exists():
        raise ValidationError({"code": "An insurer with that code exists."})

    row = Insurer.objects.create(
        code=data["code"],
        name=data["name"],
        is_public=data.get("is_public", True),
        sort_order=data.get("sort_order", 100),
    )
    return Response(
        {
            "code": row.code,
            "name": row.name,
            "is_public": row.is_public,
            "sort_order": row.sort_order,
            "facilities": 0,
        },
        status=201,
    )


@extend_schema(
    summary="Rename or reorder an insurer",
    request=AdminInsurerWriteSerializer,
    responses=AdminInsurerSerializer,
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def update_insurer(request, code):
    from django.db.models import Count

    from apps.insurance.models import Insurer

    row = Insurer.objects.filter(code=code).first()
    if row is None:
        raise NotFound("No such insurer.")

    payload = AdminInsurerWriteSerializer(data=request.data, partial=True)
    payload.is_valid(raise_exception=True)

    # `code` is deliberately not editable. Facilities, fixtures and the search
    # alias table all key on it, and renaming it would silently detach every
    # acceptance record pointing at the old value.
    for field in ("name", "is_public", "sort_order"):
        if field in payload.validated_data:
            setattr(row, field, payload.validated_data[field])
    row.save()

    facilities = (
        Insurer.objects.filter(pk=row.pk)
        .annotate(n=Count("facilityinsurer", distinct=True))
        .values_list("n", flat=True)
        .first()
    )
    return Response(
        {
            "code": row.code,
            "name": row.name,
            "is_public": row.is_public,
            "sort_order": row.sort_order,
            "facilities": facilities or 0,
        }
    )


# --------------------------------------------------------------------------
# Platform settings
# --------------------------------------------------------------------------


def _settings_payload() -> dict:
    """What can be changed while running, and what deliberately cannot.

    The fixed values are returned alongside the editable one on purpose. An
    administrator asking "why does this facility show no wait time" needs to
    see that the gate is 20 - especially because they cannot move it from
    here.

    A plain builder rather than one DRF view calling another, which loses the
    request context and breaks the moment either signature changes.
    """
    from django.conf import settings as django_settings

    from apps.platform_admin.settings_store import current

    row = current()
    return (
        {
            "default_search_radius_m": row.default_search_radius_m,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "fixed": [
                {
                    "key": "MIN_SERVICE_TIME_SAMPLES",
                    "value": str(
                        getattr(django_settings, "MIN_SERVICE_TIME_SAMPLES", "")
                    ),
                    "why": (
                        "The gate that stops a wait estimate being published "
                        "from too few visits. Changing it is a deploy-time "
                        "decision so it cannot be argued down when a facility "
                        "complains its waits show as unavailable."
                    ),
                },
                {
                    "key": "PRIVACY_NOTICE_VERSION",
                    "value": str(
                        getattr(django_settings, "PRIVACY_NOTICE_VERSION", "")
                    ),
                    "why": (
                        "Only meaningful next to the notice text it names, "
                        "which ships with the code. Bumping it here would "
                        "produce consent records pointing at a revision that "
                        "never existed."
                    ),
                },
                {
                    "key": "TRIAGE_PROTOCOL_VERSION",
                    "value": (
                        getattr(django_settings, "TRIAGE_PROTOCOL_VERSION", "")
                        or "not configured"
                    ),
                    "why": (
                        "A record that a named clinician signed off a specific "
                        "protocol. It is evidence, not a preference."
                    ),
                },
            ],
        }
    )


@extend_schema(
    summary="Platform configuration",
    responses=PlatformSettingsSerializer,
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_settings(request):
    return Response(_settings_payload())


@extend_schema(
    summary="Change platform configuration",
    request=PlatformSettingsWriteSerializer,
    responses=PlatformSettingsSerializer,
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def update_platform_settings(request):
    from apps.platform_admin.settings_store import current

    payload = PlatformSettingsWriteSerializer(data=request.data, partial=True)
    payload.is_valid(raise_exception=True)

    row = current()
    if "default_search_radius_m" in payload.validated_data:
        row.default_search_radius_m = payload.validated_data[
            "default_search_radius_m"
        ]
    row.updated_by = request.user
    row.save()

    return Response(_settings_payload())
