from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Insurer


@extend_schema(summary="Insurers")
@api_view(["GET"])
def insurers(request):
    """Reference list. Changes perhaps twice a year - cache for 24h client-side."""
    return Response(
        {
            "results": [
                {"code": i.code, "name": i.name, "is_public": i.is_public}
                for i in Insurer.objects.all()
            ]
        }
    )
