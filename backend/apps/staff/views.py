from datetime import date, datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.patients.audit import record as log_access
from apps.patients.models import PatientAccessLog
from apps.scheduling.models import Appointment

from .permissions import IsFacilityStaff, IsQueueManager, active_staff
from .reports import facility_report
from .serializers import (
    AppointmentStatusSerializer,
    FacilityReportSerializer,
    StaffAppointmentListSerializer,
    StaffAppointmentSerializer,
    StaffMeSerializer,
)


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


class SlotConflict(APIException):
    status_code = 409
    default_detail = (
        "This patient already has an active appointment in that slot. "
        "Cancel the newer booking first."
    )


# --------------------------------------------------------------------------
# Workspace: appointments
# --------------------------------------------------------------------------


@extend_schema(
    summary="Appointments booked at the caller's facility",
    parameters=[
        OpenApiParameter(
            "date",
            OpenApiTypes.DATE,
            description="Defaults to today, in the facility's local time.",
        ),
        OpenApiParameter(
            "status",
            str,
            description="Filter by status. Defaults to everything not cancelled.",
        ),
    ],
    responses=StaffAppointmentListSerializer,
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsFacilityStaff])
def appointments(request):
    """Today's list, so reception knows who is expected.

    Scoped to the caller's facility through active_staff(), never through a
    facility id in the query string - see permissions.py for why.
    """
    staff = active_staff(request)

    raw = request.query_params.get("date")
    try:
        day = date.fromisoformat(raw) if raw else timezone.localdate()
    except ValueError:
        raise ValidationError({"date": "Expected YYYY-MM-DD."}) from None

    start = timezone.make_aware(datetime.combine(day, time.min))
    queryset = (
        Appointment.objects.filter(
            facility_id=staff.facility_id,
            slot_start__gte=start,
            slot_start__lt=start + timedelta(days=1),
        )
        .select_related("service_type", "provider", "patient")
        .order_by("slot_start")
    )

    status_filter = request.query_params.get("status")
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    else:
        # Cancelled appointments are noise on a working list; they are still
        # reachable with ?status=cancelled and still counted in the reports.
        queryset = queryset.exclude(status=Appointment.Status.CANCELLED)

    rows = [
        {
            "id": appointment.id,
            "reference": appointment.reference,
            "slot_start": appointment.slot_start,
            "slot_end": appointment.slot_end,
            "status": appointment.status,
            "booked_via": appointment.booked_via,
            "service": appointment.service_type.name_en,
            "service_code": appointment.service_type.code,
            "provider": (
                appointment.provider.full_name if appointment.provider_id else None
            ),
            # An anonymised patient leaves the appointment behind with a null
            # FK - the row still counts in the reports, but there is nobody to
            # name. See apps/patients/privacy.py.
            "patient_name": (
                (appointment.patient.full_name or "Unnamed")
                if appointment.patient_id
                else "Removed"
            ),
            "patient_phone": (
                appointment.patient.phone if appointment.patient_id else None
            ),
        }
        for appointment in queryset
    ]

    if rows:
        log_access(
            request,
            action=PatientAccessLog.Action.VIEW,
            facility=staff.facility,
            record_count=len(rows),
        )

    return Response({"date": day, "count": len(rows), "results": rows})


@extend_schema(
    summary="Mark an appointment arrived, served or a no-show",
    request=AppointmentStatusSerializer,
    responses=StaffAppointmentSerializer,
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsQueueManager])
def set_appointment_status(request, pk: int):
    """The three transitions reception actually performs.

    Cancellation is deliberately NOT here: a facility cancelling on a patient
    has to notify them, which is what the scheduling endpoint does.
    """
    staff = active_staff(request)
    serializer = AppointmentStatusSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        appointment = Appointment.objects.select_related(
            "service_type", "provider", "patient"
        ).get(pk=pk, facility_id=staff.facility_id)
    except Appointment.DoesNotExist:
        # 404, not 403: a facility should not be able to probe for the
        # existence of another facility's appointment ids.
        raise NotFound("No such appointment at this facility.") from None

    if appointment.status == Appointment.Status.CANCELLED:
        raise ValidationError(
            {"status": "This appointment was cancelled."}
        )

    appointment.status = serializer.validated_data["status"]
    try:
        # A savepoint, so a constraint violation does not poison the request's
        # transaction and turn a 409 into a 500 on the next query.
        with transaction.atomic():
            appointment.save(update_fields=["status"])
    except IntegrityError:
        # one_active_appointment_per_slot. Reachable when reviving a no-show
        # whose patient has since rebooked the identical slot: two active rows
        # for the same person at the same time is exactly what that constraint
        # exists to prevent, so say so rather than 500.
        raise SlotConflict() from None

    return Response(
        {
            "id": appointment.id,
            "reference": appointment.reference,
            "slot_start": appointment.slot_start,
            "slot_end": appointment.slot_end,
            "status": appointment.status,
            "booked_via": appointment.booked_via,
            "service": appointment.service_type.name_en,
            "service_code": appointment.service_type.code,
            "provider": (
                appointment.provider.full_name if appointment.provider_id else None
            ),
            "patient_name": (
                (appointment.patient.full_name or "Unnamed")
                if appointment.patient_id
                else "Removed"
            ),
            "patient_phone": (
                appointment.patient.phone if appointment.patient_id else None
            ),
        }
    )


# --------------------------------------------------------------------------
# Workspace: reports
# --------------------------------------------------------------------------


@extend_schema(
    summary="Operational report for the caller's facility",
    parameters=[
        OpenApiParameter(
            "days", int, description="Window length, 1-90. Defaults to 30."
        )
    ],
    responses=FacilityReportSerializer,
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsFacilityStaff])
def reports(request):
    staff = active_staff(request)
    try:
        days = int(request.query_params.get("days", 30))
    except ValueError:
        raise ValidationError({"days": "Expected a number."}) from None
    if not 1 <= days <= 90:
        raise ValidationError({"days": "Expected 1 to 90."})

    return Response(facility_report(staff.facility, days=days))
