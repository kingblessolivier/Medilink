from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.facilities.models import Facility

from .models import Provider, Specialty
from .serializers import (
    ProviderDetailSerializer,
    ProviderListSerializer,
    ProviderQuerySerializer,
    ProviderSerializer,
    SpecialtyListSerializer,
    SpecialtySerializer,
)
from .services import providers_queryset


@extend_schema(
    summary="Specialties",
    description=(
        "The shared clinical vocabulary. Each specialty carries the facility "
        "service codes a clinician in it delivers, which is what lets a Care "
        "Guide recommendation reach the facility search."
    ),
    responses=SpecialtyListSerializer,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def specialties(request):
    queryset = Specialty.objects.prefetch_related("service_types")
    if request.query_params.get("triage_only") == "true":
        queryset = queryset.filter(is_triage_target=True)
    return Response({"results": SpecialtySerializer(queryset, many=True).data})


@extend_schema(
    operation_id="provider_list",
    summary="Doctors directory",
    parameters=[
        OpenApiParameter("specialty", str, description="Specialty code"),
        OpenApiParameter("facility", str, description="Facility slug"),
        OpenApiParameter("service", str, description="ServiceType code"),
        OpenApiParameter("language", str, description="rw | en | fr | sw"),
        OpenApiParameter("search", str, description="Name or specialty"),
        OpenApiParameter("limit", int),
    ],
    responses=ProviderListSerializer,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def provider_list(request):
    params = ProviderQuerySerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    v = params.validated_data

    queryset = providers_queryset(
        specialty=v.get("specialty"),
        facility_slug=v.get("facility"),
        service=v.get("service"),
        language=v.get("language"),
        search=v.get("search"),
    )
    # Count before slicing: the client needs to know a filter matched more
    # than it is being shown.
    total = queryset.count()
    results = queryset[: v["limit"]]

    return Response(
        {"count": total, "results": ProviderSerializer(results, many=True).data}
    )


@extend_schema(
    operation_id="provider_detail",
    summary="Doctor profile",
    responses=ProviderDetailSerializer,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def provider_detail(request, slug):
    provider = get_object_or_404(
        Provider.objects.filter(active=True).prefetch_related(
            "specialties", "placements__facility", "placements__service_types"
        ),
        slug=slug,
    )
    return Response(ProviderDetailSerializer(provider).data)


@extend_schema(
    operation_id="facility_providers",
    summary="Doctors practising at a facility",
    parameters=[
        OpenApiParameter("specialty", str),
        OpenApiParameter("service", str),
    ],
    responses=ProviderListSerializer,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def facility_providers(request, slug):
    facility = get_object_or_404(
        Facility.objects.filter(verified_at__isnull=False), slug=slug
    )
    queryset = providers_queryset(
        facility_slug=facility.slug,
        specialty=request.query_params.get("specialty") or None,
        service=request.query_params.get("service") or None,
    )
    return Response(
        {
            "count": queryset.count(),
            "results": ProviderSerializer(queryset, many=True).data,
        }
    )
