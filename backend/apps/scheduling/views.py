from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.facilities.models import Facility, ServiceType
from apps.notifications.models import Notification
from apps.notifications.services import dispatch
from apps.notifications.tasks import short_name
from apps.patients.auth import IsPatient, current_patient

from .models import Appointment
from .serializers import (
    AppointmentSerializer,
    BookingSerializer,
    SlotDaysSerializer,
    SlotQuerySerializer,
)
from .services import BookingError, SlotUnavailable, available_slots, book, cancel


def _conflict(message):
    return Response(
        {"type": "conflict", "detail": str(message)},
        status=status.HTTP_409_CONFLICT,
    )


@extend_schema(
    summary="Bookable slots for a facility and service",
    parameters=[
        OpenApiParameter("service", str, required=True),
        OpenApiParameter("date_from", str),
        OpenApiParameter("date_to", str),
    ],
    responses=SlotDaysSerializer,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def slots(request, slug):
    facility = get_object_or_404(
        Facility.objects.filter(verified_at__isnull=False), slug=slug
    )
    params = SlotQuerySerializer(data=request.query_params)
    params.is_valid(raise_exception=True)

    service_type = get_object_or_404(
        ServiceType, code=params.validated_data["service"]
    )

    days = available_slots(
        facility=facility,
        service_type=service_type,
        date_from=params.validated_data.get("date_from"),
        date_to=params.validated_data.get("date_to"),
    )

    return Response(
        {
            "facility": facility.slug,
            "service": service_type.code,
            "as_of": timezone.localtime().isoformat(),
            "days": [
                {
                    "date": day["date"],
                    "slots": [
                        {
                            "start": slot["start"],
                            "end": slot["end"],
                            "remaining": slot["remaining"],
                            "capacity": slot["capacity"],
                        }
                        for slot in day["slots"]
                    ],
                }
                for day in days
            ],
        }
    )


@extend_schema(
    summary="List your appointments",
    parameters=[OpenApiParameter("status", str, description="upcoming | past | all")],
    responses=AppointmentSerializer(many=True),
    methods=["GET"],
)
@extend_schema(
    summary="Book an appointment",
    request=BookingSerializer,
    responses=AppointmentSerializer,
    methods=["POST"],
)
@api_view(["GET", "POST"])
@permission_classes([IsPatient])
def appointments(request):
    """One path, dispatched on method - the conventional shape, and the one
    docs/03 specifies."""
    if request.method == "GET":
        return _list_appointments(request)
    return _create_appointment(request)


def _create_appointment(request):
    patient = current_patient(request)
    payload = BookingSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    data = payload.validated_data

    facility = get_object_or_404(
        Facility.objects.filter(verified_at__isnull=False), slug=data["facility"]
    )
    service_type = get_object_or_404(ServiceType, code=data["service"])

    try:
        appointment = book(
            facility=facility,
            service_type=service_type,
            patient=patient,
            slot_start=data["slot_start"],
        )
    except SlotUnavailable as exc:
        return _conflict(exc)
    except BookingError as exc:
        return _conflict(exc)

    return Response(
        AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED
    )


def _list_appointments(request):
    patient = current_patient(request)
    which = request.query_params.get("status", "upcoming")

    queryset = Appointment.objects.filter(patient=patient).select_related(
        "facility", "service_type"
    )
    if which == "upcoming":
        queryset = queryset.filter(
            slot_start__gte=timezone.now(), status__in=Appointment.OPEN_STATUSES
        )
    elif which == "past":
        queryset = queryset.exclude(
            slot_start__gte=timezone.now(), status__in=Appointment.OPEN_STATUSES
        ).order_by("-slot_start")

    return Response(AppointmentSerializer(queryset, many=True).data)


@extend_schema(
    summary="Cancel an appointment",
    request=None,  # the id is in the path; there is no body
    responses=AppointmentSerializer,
)
@api_view(["POST"])
@permission_classes([IsPatient])
def cancel_appointment(request, pk):
    patient = current_patient(request)
    appointment = get_object_or_404(
        Appointment.objects.select_related("facility"), pk=pk, patient=patient
    )

    try:
        cancel(appointment)
    except BookingError as exc:
        return _conflict(exc)

    dispatch(
        kind=Notification.Kind.APPT_CANCELLED,
        phone=patient.phone,
        language=patient.language,
        patient=patient,
        appointment=appointment,
        facility=short_name(appointment.facility.name),
    )
    return Response(AppointmentSerializer(appointment).data)
