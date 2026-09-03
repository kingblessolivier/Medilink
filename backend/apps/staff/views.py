import secrets
from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import (
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.patients.audit import record as log_access
from apps.patients.models import PatientAccessLog
from apps.scheduling.models import Appointment, ScheduleTemplate

from .models import StaffMember
from .permissions import (
    IsFacilityAdmin,
    IsFacilityStaff,
    IsQueueManager,
    active_staff,
)
from .reports import facility_report
from .serializers import (
    AppointmentStatusSerializer,
    FacilityContactWriteSerializer,
    FacilityInsuranceSerializer,
    FacilityInsurerSerializer,
    FacilityInsurerWriteSerializer,
    FacilityReportSerializer,
    FacilitySettingsSerializer,
    OpeningHoursWriteSerializer,
    PatientLookupSerializer,
    ScheduleTemplateListSerializer,
    ScheduleTemplateSerializer,
    ScheduleTemplateWriteSerializer,
    StaffAppointmentListSerializer,
    StaffAppointmentSerializer,
    StaffMeSerializer,
    StaffServiceCoverageSerializer,
    StaffServiceCoverageWriteSerializer,
    TeamMemberCreatedSerializer,
    TeamMemberSerializer,
    TeamMemberUpdateSerializer,
    TeamMemberWriteSerializer,
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

    # The instance goes in so the cross-field checks can resolve what the
    # request omitted: a PATCH that changes only the slot length still has to
    # be measured against the times already stored.
    payload = ScheduleTemplateWriteSerializer(
        instance=template, data=request.data, partial=True
    )
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


# --------------------------------------------------------------------------
# Insurance
# --------------------------------------------------------------------------
#
# A facility maintains its own accepted insurers and per-service coverage, and
# its save counts as confirmation.
#
# This screen used to be read-only, on the reasoning that a facility editing
# its own coverage would be publishing an unchecked claim. The decision was
# reversed deliberately: the facility runs the counter that takes the card, so
# nobody is better placed to say what it accepts, and routing every change
# through MediLink is the bottleneck that stops a second pilot site.
#
# Rule 6 of docs/11 section 7 still holds and is unaffected by this. It governs
# the WORDS - "Accepts Mutuelle", never "You are covered" - not who edits them.
# What is stored is still facility-declared acceptance, not a patient's
# eligibility, and no screen anywhere claims otherwise.


def _coverage_rows(facility):
    """Per-service coverage for this facility, keyed by (insurer, service)."""
    from apps.insurance.models import FacilityServiceInsurer

    rows = FacilityServiceInsurer.objects.filter(
        facility_service__facility=facility
    ).select_related("insurer", "facility_service__service_type")
    return {
        (row.insurer.code, row.facility_service.service_type.code): row
        for row in rows
    }


@extend_schema(
    summary="What this facility accepts, and what each insurer covers",
    responses=FacilityInsuranceSerializer,
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsFacilityStaff])
def insurance(request):
    """Every insurer on the platform, with this facility's position on each.

    Insurers this facility does NOT accept are returned too, with
    `accepted: false`. A list of only the accepted ones would give somebody no
    way to add one, and the set is small enough to show in full.
    """
    from apps.insurance.models import FacilityInsurer, Insurer

    staff = active_staff(request)
    facility = staff.facility

    accepted = {
        row.insurer_id: row
        for row in FacilityInsurer.objects.filter(facility=facility)
    }
    coverage = _coverage_rows(facility)
    services = [
        fs.service_type
        for fs in facility.services.select_related("service_type")
        if fs.available
    ]

    results = []
    for insurer in Insurer.objects.all():
        link = accepted.get(insurer.id)
        results.append(
            {
                "code": insurer.code,
                "name": insurer.name,
                "accepted": link is not None,
                "note": link.note if link else "",
                "confirmed_at": (
                    link.confirmed_at.isoformat()
                    if link and link.confirmed_at
                    else None
                ),
                "services": [
                    {
                        "code": service.code,
                        "name_en": service.name_en,
                        "coverage": (
                            coverage[(insurer.code, service.code)].coverage
                            if (insurer.code, service.code) in coverage
                            else "unknown"
                        ),
                        "note": (
                            coverage[(insurer.code, service.code)].note
                            if (insurer.code, service.code) in coverage
                            else ""
                        ),
                    }
                    for service in services
                ],
            }
        )

    return Response({"count": len(results), "results": results})


@extend_schema(
    summary="Accept or stop accepting an insurer",
    request=FacilityInsurerWriteSerializer,
    responses=FacilityInsurerSerializer,
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsQueueManager])
def set_insurer(request, code):
    from apps.insurance.models import FacilityInsurer, Insurer

    staff = active_staff(request)
    insurer = Insurer.objects.filter(code=code).first()
    if insurer is None:
        raise NotFound("No such insurer.")

    payload = FacilityInsurerWriteSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    data = payload.validated_data

    if data["accepted"]:
        link, _ = FacilityInsurer.objects.update_or_create(
            facility=staff.facility,
            insurer=insurer,
            defaults={
                "note": data.get("note", ""),
                # The facility saying so IS the confirmation. See the module
                # note above for why that changed.
                "confirmed_at": timezone.now(),
            },
        )
        confirmed = link.confirmed_at
    else:
        # Stopping acceptance takes the per-service coverage with it. Leaving
        # "Mutuelle covers dental here" behind after "we no longer take
        # Mutuelle" is a contradiction a patient would act on.
        from apps.insurance.models import FacilityServiceInsurer

        FacilityServiceInsurer.objects.filter(
            facility_service__facility=staff.facility, insurer=insurer
        ).delete()
        FacilityInsurer.objects.filter(
            facility=staff.facility, insurer=insurer
        ).delete()
        confirmed = None

    return Response(
        {
            "code": insurer.code,
            "name": insurer.name,
            "accepted": data["accepted"],
            "note": data.get("note", ""),
            "confirmed_at": confirmed.isoformat() if confirmed else None,
        }
    )


@extend_schema(
    summary="Set what an insurer covers for one service here",
    request=StaffServiceCoverageWriteSerializer,
    responses=StaffServiceCoverageSerializer,
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsQueueManager])
def set_coverage(request, code, service):
    from apps.facilities.models import FacilityService
    from apps.insurance.models import (
        FacilityInsurer,
        FacilityServiceInsurer,
        Insurer,
    )

    staff = active_staff(request)

    insurer = Insurer.objects.filter(code=code).first()
    if insurer is None:
        raise NotFound("No such insurer.")

    # Coverage only means something for an insurer the facility takes at all.
    # Without this a facility could publish "Mutuelle covers dental" while
    # telling patients at the door that it does not accept Mutuelle.
    if not FacilityInsurer.objects.filter(
        facility=staff.facility, insurer=insurer
    ).exists():
        raise ValidationError(
            {"insurer": "Accept this insurer before setting what it covers."}
        )

    facility_service = (
        FacilityService.objects.filter(
            facility=staff.facility, service_type__code=service, available=True
        )
        .select_related("service_type")
        .first()
    )
    if facility_service is None:
        raise NotFound("This facility does not offer that service.")

    payload = StaffServiceCoverageWriteSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    data = payload.validated_data

    row, _ = FacilityServiceInsurer.objects.update_or_create(
        facility_service=facility_service,
        insurer=insurer,
        defaults={
            "coverage": data["coverage"],
            "note": data.get("note", ""),
            # `unknown` is the absence of an answer, not an answer - leaving it
            # confirmed would publish "we checked, and we do not know", which
            # is not what anybody means by selecting it.
            "confirmed_at": (
                None if data["coverage"] == "unknown" else timezone.now()
            ),
        },
    )

    return Response(
        {
            "code": facility_service.service_type.code,
            "name_en": facility_service.service_type.name_en,
            "coverage": row.coverage,
            "note": row.note,
        }
    )


# --------------------------------------------------------------------------
# Facility settings
# --------------------------------------------------------------------------
#
# What a facility may change about itself, and - just as importantly - what it
# may not.
#
# Editable: how to reach it and when it is open. Those change often, the
# facility is the only one who knows, and a wrong phone number is a patient
# who cannot ring ahead.
#
# NOT editable here: name, level, ownership, district and coordinates. Those
# are what `verified_at` attests to. A facility that could rename itself or
# move its own pin would be editing the thing MediLink verified, and the
# verification would no longer mean anything. They change through the platform
# verification flow, with a human on the other side.


def _settings_payload(facility) -> dict:
    """Plain dict, so the write views can return the new state without one
    DRF view calling another - which loses the request context and breaks the
    moment either signature changes."""
    return (
        {
            "name": facility.name,
            "level": facility.get_level_display(),
            "ownership": facility.get_ownership_display(),
            "district": facility.district,
            "verified": facility.verified_at is not None,
            "phone": facility.phone,
            "email": facility.email,
            "address": facility.address,
            "sector": facility.sector,
            "hours": [
                {
                    "weekday": row.weekday,
                    "opens_at": row.opens_at.strftime("%H:%M"),
                    "closes_at": row.closes_at.strftime("%H:%M"),
                }
                for row in facility.opening_hours.all()
            ],
        }
    )


@extend_schema(
    summary="The facility's own contact details and opening hours",
    responses=FacilitySettingsSerializer,
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsFacilityStaff])
def facility_settings(request):
    staff = active_staff(request)
    return Response(_settings_payload(staff.facility))


@extend_schema(
    summary="Update contact details",
    request=FacilityContactWriteSerializer,
    responses=FacilitySettingsSerializer,
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsQueueManager])
def update_facility_contact(request):
    staff = active_staff(request)
    payload = FacilityContactWriteSerializer(data=request.data, partial=True)
    payload.is_valid(raise_exception=True)

    facility = staff.facility
    for field in ("phone", "email", "address", "sector"):
        if field in payload.validated_data:
            setattr(facility, field, payload.validated_data[field])
    facility.save(update_fields=["phone", "email", "address", "sector"])

    return Response(_settings_payload(facility))


@extend_schema(
    summary="Replace the facility's opening hours",
    request=OpeningHoursWriteSerializer,
    responses=FacilitySettingsSerializer,
)
@api_view(["PUT"])
@permission_classes([IsAuthenticated, IsQueueManager])
def replace_opening_hours(request):
    """The whole week at once, not row by row.

    A weekday can hold two rows - that is how a lunch break is modelled, and it
    is how a Rwandan health centre actually runs - so there is no stable "the
    Tuesday row" to PATCH. Replacing the set keeps the client simple and makes
    a half-applied edit impossible.

    Opening hours decide whether a facility reads as open, which decides
    whether it appears in "open now" and whether its wait shows as `closed`.
    Getting this wrong makes a facility invisible, so the whole replacement is
    one transaction.
    """
    from apps.facilities.models import OpeningHours

    staff = active_staff(request)
    payload = OpeningHoursWriteSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    rows = payload.validated_data["hours"]

    with transaction.atomic():
        OpeningHours.objects.filter(facility=staff.facility).delete()
        OpeningHours.objects.bulk_create(
            [
                OpeningHours(
                    facility=staff.facility,
                    weekday=row["weekday"],
                    opens_at=row["opens_at"],
                    closes_at=row["closes_at"],
                )
                for row in rows
            ]
        )

    staff.facility.refresh_from_db()
    return Response(_settings_payload(staff.facility))


# --------------------------------------------------------------------------
# Patient lookup
# --------------------------------------------------------------------------
#
# The first feature that lets a staff member search FOR a person rather than
# act on one standing in front of them. That difference is the whole reason
# for the three constraints below, and none of them is optional.
#
# **Scoped to this facility's own patients.** Not the platform table. A
# receptionist at one clinic must never be able to look up somebody who has
# only ever attended another - that is the breach that ends the project, and
# docs/08 is explicit about it. "Their own" means: has a queue entry or an
# appointment here.
#
# **Every hit is logged.** A search that returns a patient is a read of a
# patient record, and docs/08 s6 requires it to be attributable. Logged once
# per search with the count, not once per result, so a wide search does not
# drown the signal the log exists to carry.
#
# **Throttled.** Without a limit this is an oracle: type numbers until one
# comes back and you have learned who is registered. The `signin` scope is
# reused rather than inventing another - both are "guessing at an identifier"
# and deserve the same budget.


class PatientLookupThrottle(ScopedRateThrottle):
    scope = "signin"


@extend_schema(
    summary="Find a patient this facility has seen",
    parameters=[
        OpenApiParameter(
            "q",
            OpenApiTypes.STR,
            description=(
                "Phone number or name. At least 3 characters - a shorter "
                "query matches most of the register and is not a search."
            ),
        )
    ],
    responses=PatientLookupSerializer,
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsFacilityStaff])
@throttle_classes([PatientLookupThrottle])
def patient_lookup(request):
    from django.db.models import Max, Q

    from apps.patients.models import Patient, normalise_phone
    from apps.queueing.models import QueueEntry

    staff = active_staff(request)
    term = (request.query_params.get("q") or "").strip()

    # Below three characters this returns most of the register, which is a
    # list rather than a search - and a list of patients is precisely what
    # this endpoint must not hand out.
    if len(term) < 3:
        return Response({"count": 0, "results": [], "query": term})

    # A phone typed as 0788… and stored as +250788… must still match, so try
    # normalising before falling back to a substring.
    phone_match = ""
    try:
        phone_match = normalise_phone(term)
    except Exception:  # noqa: BLE001 - not a phone, which is fine
        phone_match = ""

    seen_here = Q(queue_entries__facility=staff.facility) | Q(
        appointments__facility=staff.facility
    )
    matches = Q(full_name__icontains=term) | Q(phone__icontains=term)
    if phone_match:
        matches |= Q(phone=phone_match)

    patients = (
        Patient.objects.filter(seen_here)
        .filter(matches)
        .annotate(last_here=Max("queue_entries__joined_at"))
        .distinct()
        .order_by("-last_here")[:10]
    )

    results = []
    for patient in patients:
        open_entry = (
            QueueEntry.objects.filter(
                patient=patient,
                facility=staff.facility,
                status__in=QueueEntry.OPEN_STATUSES,
            )
            .order_by("-joined_at")
            .first()
        )
        results.append(
            {
                "id": patient.id,
                "display_name": patient.full_name or "",
                # Masked, exactly as the queue board masks it. A lookup screen
                # is read across a reception desk like any other.
                "phone": _mask_phone(patient.phone),
                "visits_here": QueueEntry.objects.filter(
                    patient=patient, facility=staff.facility
                ).count(),
                "last_seen": (
                    timezone.localtime(patient.last_here).date().isoformat()
                    if patient.last_here
                    else None
                ),
                "in_queue_now": open_entry is not None,
                "ticket_code": open_entry.ticket_code if open_entry else None,
            }
        )

    # One row for the search, with the count - not one per result. Same
    # reasoning as the queue board: per-record rows would drown the signal.
    log_access(
        request,
        action=PatientAccessLog.Action.VIEW,
        facility=staff.facility,
        record_count=len(results),
    )

    return Response({"count": len(results), "results": results, "query": term})


def _mask_phone(phone: str) -> str:
    return f"{phone[:6]}...{phone[-3:]}" if len(phone) > 9 else phone


# --------------------------------------------------------------------------
# FA-10: staff accounts
#
# The one staff surface that GRANTS access rather than using it, which is why
# it is gated on IsFacilityAdmin rather than IsQueueManager - a receptionist
# works the queue all day and must not be able to mint accounts.
#
# Facility comes from the caller's own StaffMember and is never accepted from
# the payload, so there is no shape of request that creates or edits an
# account at another clinic.
# --------------------------------------------------------------------------


def _team_row(member, *, me):
    return {
        "id": member.id,
        "username": member.user.username,
        "full_name": member.user.first_name or "",
        "role": member.role,
        "role_label": member.get_role_display(),
        "active": member.active,
        "is_self": member.id == me.id,
    }


# One decorator per method: spectacular cannot guess a serializer for a
# function view that both lists and creates, and it reports that as an error
# rather than a warning.
@extend_schema(
    methods=["GET"],
    summary="Staff accounts at this facility",
    responses={200: TeamMemberSerializer(many=True)},
    tags=["Workspace"],
)
@extend_schema(
    methods=["POST"],
    summary="Create a staff account at this facility",
    request=TeamMemberWriteSerializer,
    responses={201: TeamMemberCreatedSerializer},
    tags=["Workspace"],
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsFacilityAdmin])
def team(request):
    me = active_staff(request)

    if request.method == "GET":
        members = (
            StaffMember.objects.filter(facility_id=me.facility_id)
            .select_related("user")
            .order_by("user__username")
        )
        return Response([_team_row(m, me=me) for m in members])

    payload = TeamMemberWriteSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    data = payload.validated_data

    if User.objects.filter(username__iexact=data["username"]).exists():
        raise ValidationError({"username": "That username is already taken."})

    # 16 characters from a URL-safe alphabet. Generated, not chosen: an
    # administrator inventing passwords for colleagues picks the clinic name
    # and a digit.
    temporary_password = secrets.token_urlsafe(12)

    with transaction.atomic():
        user = User.objects.create_user(
            username=data["username"],
            password=temporary_password,
            first_name=data["full_name"],
        )
        member = StaffMember.objects.create(
            user=user,
            facility_id=me.facility_id,
            role=data["role"],
            active=True,
        )

    row = _team_row(member, me=me)
    row["temporary_password"] = temporary_password
    return Response(row, status=201)


@extend_schema(
    summary="Change a colleague's role, or switch their access off",
    request=TeamMemberUpdateSerializer,
    responses={200: TeamMemberSerializer},
    tags=["Workspace"],
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsFacilityAdmin])
def team_member(request, pk):
    me = active_staff(request)

    # Scoped by facility in the lookup itself. 404 rather than 403 so an
    # enumerated id does not confirm that an account exists elsewhere.
    try:
        member = StaffMember.objects.select_related("user").get(
            pk=pk, facility_id=me.facility_id
        )
    except StaffMember.DoesNotExist as exc:
        raise NotFound("No such staff account at this facility.") from exc

    payload = TeamMemberUpdateSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    data = payload.validated_data

    # An administrator must not be able to lock themselves out, nor demote
    # themselves out of the only role that can undo it. Both are one careless
    # tap, and both leave a facility with no way back in but a developer.
    if member.id == me.id:
        if data.get("active") is False:
            raise ValidationError(
                {"active": "You cannot switch off your own account."}
            )
        if "role" in data and data["role"] != StaffMember.Role.ADMIN:
            raise ValidationError(
                {"role": "You cannot remove your own administrator role."}
            )

    # The last active administrator is the same lockout by a slower route.
    if data.get("active") is False and member.role == StaffMember.Role.ADMIN:
        remaining = (
            StaffMember.objects.filter(
                facility_id=me.facility_id,
                role=StaffMember.Role.ADMIN,
                active=True,
            )
            .exclude(pk=member.pk)
            .count()
        )
        if remaining == 0:
            raise ValidationError(
                {"active": "This is the only active administrator at this facility."}
            )

    for field, value in data.items():
        setattr(member, field, value)
    member.save(update_fields=list(data.keys()))

    return Response(_team_row(member, me=me))
