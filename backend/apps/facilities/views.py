from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Facility, ServiceType
from .serializers import (
    DistrictListSerializer,
    FacilityDetailSerializer,
    FacilityNearbySerializer,
    NearbyQuerySerializer,
    NearbyResponseSerializer,
    ServiceTypeListSerializer,
)
from .services import find_nearby
from .wait import wait_snapshot


@extend_schema(
    summary="Nearby facilities",
    description=(
        "Verified facilities near a coordinate, ranked by (tier, distance). "
        "Results are never ranked by wait time - only a minority of facilities "
        "report queue data, so ranking on it would bury good facilities that "
        "simply do not report."
    ),
    parameters=[
        OpenApiParameter("lat", float, required=True),
        OpenApiParameter("lng", float, required=True),
        OpenApiParameter("radius", int, description="Metres. Default 5000, max 50000."),
        OpenApiParameter("insurer", str, description="Insurer code, e.g. mutuelle"),
        OpenApiParameter("service", str, description="Service type code"),
        OpenApiParameter(
            "specialty",
            str,
            description="Specialty code, from a Care Guide recommendation",
        ),
        OpenApiParameter("level", str, many=True),
        OpenApiParameter("open_now", bool),
        OpenApiParameter("limit", int),
    ],
    responses=NearbyResponseSerializer,
)
@api_view(["GET"])
def nearby(request):
    params = NearbyQuerySerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    v = params.validated_data

    facilities, effective_radius, expanded = find_nearby(
        lat=v["lat"],
        lng=v["lng"],
        radius_m=v["radius"],
        insurer=v.get("insurer"),
        service=v.get("service"),
        specialty=v.get("specialty"),
        levels=v.get("level") or None,
        open_now=v["open_now"],
        limit=v["limit"],
    )

    waits = wait_snapshot(facilities, v.get("service"))

    return Response(
        {
            "as_of": timezone.localtime().isoformat(),
            "query": {
                "lat": v["lat"],
                "lng": v["lng"],
                "radius": effective_radius,
                "radius_expanded": expanded,
                "insurer": v.get("insurer"),
                "service": v.get("service"),
                "specialty": v.get("specialty"),
                "open_now": v["open_now"],
            },
            "count": len(facilities),
            "results": FacilityNearbySerializer(
                facilities, many=True, context={"waits": waits}
            ).data,
        }
    )


@extend_schema(summary="Facility detail", responses=FacilityDetailSerializer)
@api_view(["GET"])
def facility_detail(request, slug):
    facility = get_object_or_404(
        Facility.objects.filter(verified_at__isnull=False).prefetch_related(
            "insurers__insurer", "services__service_type", "opening_hours"
        ),
        slug=slug,
    )
    waits = wait_snapshot([facility])
    return Response(
        FacilityDetailSerializer(facility, context={"waits": waits}).data
    )


@extend_schema(summary="Service types", responses=ServiceTypeListSerializer)
@api_view(["GET"])
def service_types(request):
    """Small, cacheable reference list. Includes all three language names so
    that USSD and WhatsApp can render without a second call."""
    return Response(
        {
            "results": [
                {
                    "code": s.code,
                    "name_rw": s.name_rw,
                    "name_en": s.name_en,
                    "name_fr": s.name_fr,
                }
                for s in ServiceType.objects.all()
            ]
        }
    )


@extend_schema(
    summary="Districts with verified facilities",
    responses=DistrictListSerializer,
)
@api_view(["GET"])
def districts(request):
    """Drives the fallback picker when geolocation is denied or out of bounds,
    and the first USSD menu in Phase 3."""
    names = (
        Facility.objects.filter(verified_at__isnull=False)
        .values_list("district", flat=True)
        .distinct()
        .order_by("district")
    )
    return Response({"results": list(names)})
