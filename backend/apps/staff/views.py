from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .permissions import IsFacilityStaff, active_staff
from .serializers import StaffMeSerializer


@extend_schema(
    summary="The signed-in staff member and their facility",
    responses=StaffMeSerializer,
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsFacilityStaff])
def me(request):
    """The reception client calls this on load to learn which facility it is
    operating, and which services that facility offers."""
    staff = active_staff(request)
    facility = staff.facility
    return Response(
        {
            "username": request.user.username,
            "role": staff.role,
            "can_manage_queue": staff.can_manage_queue,
            "facility": {
                "id": facility.id,
                "slug": facility.slug,
                "name": facility.name,
                "district": facility.district,
                "reports_queue": facility.reports_queue,
            },
            "services": [
                {
                    "code": fs.service_type.code,
                    "name_rw": fs.service_type.name_rw,
                    "name_en": fs.service_type.name_en,
                }
                for fs in facility.services.select_related("service_type")
                if fs.available
            ],
        }
    )
