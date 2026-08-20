from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .serializers import SearchQuerySerializer, SearchResponseSerializer
from .services import search


@extend_schema(
    operation_id="global_search",
    summary="One search across specialties, services, doctors and facilities",
    description=(
        "A patient typing 'pediatric' does not know whether that is a service, "
        "a specialty, a doctor or a hospital. Results come back grouped, "
        "ordered by what gets somebody to care fastest. Empty groups are "
        "omitted rather than returned empty."
    ),
    parameters=[
        OpenApiParameter("q", str, required=True),
        OpenApiParameter("lat", float, description="Orders facilities by distance"),
        OpenApiParameter("lng", float),
    ],
    responses=SearchResponseSerializer,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def global_search(request):
    params = SearchQuerySerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    v = params.validated_data

    return Response(
        search(term=v["q"], lat=v.get("lat"), lng=v.get("lng"))
    )
