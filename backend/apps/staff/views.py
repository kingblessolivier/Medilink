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
from apps.scheduling.models import Appointment, ScheduleTemplate

from .permissions import IsFacilityStaff, IsQueueManager, active_staff
from .reports import facility_report
from .serializers import (
    AppointmentStatusSerializer,
    FacilityReportSerializer,
    ScheduleTemplateListSerializer,
    ScheduleTemplateSerializer,
    ScheduleTemplateWriteSerializer,
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


# --------------------------------------------------------------------------
# Schedule templates
# --------------------------------------------------------------------------
#
# The whole booking system rests on ScheduleTemplate - slots are expanded from
# it on read, capacity is locked on it, and `available_slots` returns nothing
# without one. It was fully modelled, migrated and tested, with no way for a
# facility to create one. Until this existed, opening a clinic's booking hours
# meant somebody editing the database on their behalf, which works for one
# pilot site and not for two.


def _slots_per_week(template) -> int:
    """How many bookable slots this session produces in a week.

    Shown because "08:00-12:00, 15 minutes, 2 per slot" is not a number anybody
    holds in their head, and it is the number that decides whether a facility
    has opened too much capacity or too little.
    """
    span = (
        datetime.combine(date.min, template.end_time)
        - datetime.combine(date.min, template.start_time)
    ).total_seconds() / 60
    return int(span // template.slot_minutes) * template.capacity_per_slot


def _template_payload(template, upcoming: int) -> dict:
    return {
        "id": template.id,
        "weekday": template.weekday,
        "service": template.service_type.code,
        "service_name_en": template.service_type.name_en,
        "service_name_rw": template.service_type.name_rw,
        "provider": template.provider.slug if template.provider_id else None,
        "provider_name": (
            template.provider.display_name if template.provider_id else None
        ),
        "start_time": template.start_time.strftime("%H:%M"),
        "end_time": template.end_time.strftime("%H:%M"),
        "slot_minutes": template.slot_minutes,
        "capacity_per_slot": template.capacity_per_slot,
        "active": template.active,
        "slots_per_week": _slots_per_week(template),
        "upcoming": upcoming,
    }


def _upcoming_counts(facility) -> dict:
    """Future appointments per (service, provider, weekday).

    One query for the whole screen. A facility with a dozen sessions would
    otherwise run a dozen counts to render one table.

    This is the number that matters when somebody closes a session: it stops
    NEW bookings and does not cancel the patients who already hold one, so the
    facility still has to see them.
    """
    counts: dict[tuple, int] = {}
    rows = Appointment.objects.filter(
        facility=facility,
        slot_start__gte=timezone.now(),
        status__in=Appointment.OPEN_STATUSES,
    ).values_list("service_type_id", "provider_id", "slot_start")
    for service_id, provider_id, slot_start in rows:
        local = timezone.localtime(slot_start)
        key = (service_id, provider_id, local.weekday())
        counts[key] = counts.get(key, 0) + 1
    return counts


def _resolve_write(staff, data):
    """Turn slugs into the facility's own rows, refusing anything else."""
    from apps.facilities.models import FacilityService
    from apps.providers.models import Provider

    offered = (
        FacilityService.objects.filter(
            facility=staff.facility,
            service_type__code=data["service"],
            available=True,
        )
        .select_related("service_type")
        .first()
    )
    if offered is None:
        raise ValidationError(
            {"service": "This facility does not offer that service."}
        )

    provider = None
    slug = (data.get("provider") or "").strip()
    if slug:
        # Scoped to this facility's own clinicians. A staff member must not be
        # able to open a session in another facility's doctor's name.
        provider = Provider.objects.filter(
            slug=slug, placements__facility=staff.facility
        ).first()
        if provider is None:
            raise ValidationError(
                {"provider": "That clinician does not work at this facility."}
            )

    return offered.service_type, provider


@extend_schema(
    summary="The facility's recurring bookable sessions",
    responses=ScheduleTemplateListSerializer,
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsFacilityStaff])
def schedule(request):
    staff = active_staff(request)
    templates = (
        ScheduleTemplate.objects.filter(facility=staff.facility)
        .select_related("service_type", "provider")
        .order_by("weekday", "start_time")
    )
    counts = _upcoming_counts(staff.facility)
    results = [
        _template_payload(
            template,
            counts.get(
                (template.service_type_id, template.provider_id, template.weekday), 0
            ),
        )
        for template in templates
    ]
    return Response({"count": len(results), "results": results})


@extend_schema(
    summary="Open a new bookable session",
    request=ScheduleTemplateWriteSerializer,
    responses=ScheduleTemplateSerializer,
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsQueueManager])
def create_schedule(request):
    staff = active_staff(request)
    payload = ScheduleTemplateWriteSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    data = payload.validated_data

    service_type, provider = _resolve_write(staff, data)

    try:
        template = ScheduleTemplate.objects.create(
            facility=staff.facility,
            service_type=service_type,
            provider=provider,
            weekday=data["weekday"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            slot_minutes=data["slot_minutes"],
            capacity_per_slot=data["capacity_per_slot"],
            active=data.get("active", True),
        )
    except IntegrityError as exc:
        # unique_together on (facility, service, provider, weekday, start_time)
        raise ValidationError(
            {
                "start_time": (
                    "A session for that service already starts at that time "
                    "on that day."
                )
            }
        ) from exc

    return Response(_template_payload(template, 0), status=201)


@extend_schema(
    summary="Change or close a bookable session",
    request=ScheduleTemplateWriteSerializer,
    responses=ScheduleTemplateSerializer,
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsQueueManager])
def update_schedule(request, pk):
    staff = active_staff(request)
    template = (
        ScheduleTemplate.objects.filter(pk=pk, facility=staff.facility)
        .select_related("service_type", "provider")
        .first()
    )
    if template is None:
        # 404 rather than 403 for another facility's session: the response
        # must not confirm that the id exists.
        raise NotFound("No such session at this facility.")

    payload = ScheduleTemplateWriteSerializer(data=request.data, partial=True)
    payload.is_valid(raise_exception=True)
    data = payload.validated_data

    if "service" in data or "provider" in data:
        service_type, provider = _resolve_write(
            staff,
            {
                "service": data.get("service", template.service_type.code),
                "provider": data.get(
                    "provider",
                    template.provider.slug if template.provider_id else "",
                ),
            },
        )
        template.service_type = service_type
        template.provider = provider

    for field in (
        "weekday",
        "start_time",
        "end_time",
        "slot_minutes",
        "capacity_per_slot",
        "active",
    ):
        if field in data:
            setattr(template, field, data[field])

    try:
        template.save()
    except IntegrityError as exc:
        raise ValidationError(
            {"start_time": "That would collide with another session."}
        ) from exc

    counts = _upcoming_counts(staff.facility)
    upcoming = counts.get(
        (template.service_type_id, template.provider_id, template.weekday), 0
    )
    return Response(_template_payload(template, upcoming))
