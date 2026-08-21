"""Slot generation and booking.

Slots are expanded from ScheduleTemplate on read rather than materialised as
rows. A facility open six days a week for a year is roughly 15,000 mostly-empty
slot rows, and materialised slots drift from the template the moment opening
hours change.
"""

from datetime import date, datetime, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from apps.facilities.models import Facility, ServiceType
from apps.patients.models import Patient

from .models import Appointment, ScheduleTemplate

MAX_DAYS_AHEAD = 30
DEFAULT_DAYS_AHEAD = 14

# A patient may not hold more than this many open bookings at once. Without a
# cap, one person can silently exhaust a small facility's whole week.
MAX_OPEN_APPOINTMENTS_PER_PATIENT = 3


class BookingError(Exception):
    """Domain rule violation - mapped to HTTP 409 by the view layer."""


class SlotUnavailable(BookingError):
    """The slot filled between the read and the write."""


def _slot_starts(template: ScheduleTemplate, day: date):
    """Every slot start time a template produces on one day."""
    current = datetime.combine(day, template.start_time)
    end = datetime.combine(day, template.end_time)
    step = timedelta(minutes=template.slot_minutes)
    while current + step <= end:
        yield current, current + step
        current += step


def available_slots(
    *,
    facility: Facility,
    service_type: ServiceType,
    provider=None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    """Bookable slots per day.

    `provider=None` means the facility's general clinic - the session where
    staff assign whoever is free, which is how most booking at a health centre
    actually works. Naming a provider returns that clinician's own list
    instead. The two are separate capacity pools: Dr A's 09:00 and the general
    clinic's 09:00 are different appointments.

    Slots with remaining == 0 are returned rather than omitted, so the UI can
    grey them out: a patient needs to see that a day is busy, not that it is
    empty.
    """
    now = timezone.localtime()
    date_from = date_from or now.date()
    date_to = date_to or (date_from + timedelta(days=DEFAULT_DAYS_AHEAD))
    date_to = min(date_to, date_from + timedelta(days=MAX_DAYS_AHEAD))

    templates = list(
        ScheduleTemplate.objects.filter(
            facility=facility,
            service_type=service_type,
            provider=provider,
            active=True,
        )
    )
    if not templates:
        return []

    window_start = timezone.make_aware(datetime.combine(date_from, datetime.min.time()))
    window_end = timezone.make_aware(
        datetime.combine(date_to + timedelta(days=1), datetime.min.time())
    )

    # One query for the whole window, not one per day.
    booked = {
        row["slot_start"]: row["n"]
        for row in Appointment.objects.filter(
            facility=facility,
            service_type=service_type,
            # Counted against the same pool the slots came from.
            provider=provider,
            slot_start__gte=window_start,
            slot_start__lt=window_end,
            status__in=Appointment.OPEN_STATUSES,
        )
        .values("slot_start")
        .annotate(n=Count("id"))
    }

    by_weekday: dict[int, list[ScheduleTemplate]] = {}
    for template in templates:
        by_weekday.setdefault(template.weekday, []).append(template)

    days = []
    day = date_from
    while day <= date_to:
        slots = []
        for template in by_weekday.get(day.weekday(), []):
            for start, end in _slot_starts(template, day):
                aware_start = timezone.make_aware(start)
                # Never offer a slot in the past.
                if aware_start <= now:
                    continue
                taken = booked.get(aware_start, 0)
                slots.append(
                    {
                        "start": aware_start,
                        "end": timezone.make_aware(end),
                        "remaining": max(0, template.capacity_per_slot - taken),
                        "capacity": template.capacity_per_slot,
                    }
                )
        if slots:
            slots.sort(key=lambda s: s["start"])
            days.append({"date": day, "slots": slots})
        day += timedelta(days=1)

    return days


@transaction.atomic
def book(
    *,
    facility: Facility,
    service_type: ServiceType,
    patient: Patient,
    slot_start,
    provider=None,
    booked_via: str = Appointment.BookedVia.APP,
) -> Appointment:
    """Reserve one slot.

    Capacity is re-checked inside the transaction with the existing rows locked,
    so two patients tapping the last slot at the same moment cannot both
    succeed.
    """
    if slot_start <= timezone.now():
        raise BookingError("That appointment time has already passed.")

    template = _template_for(facility, service_type, slot_start, provider)
    if template is None:
        raise BookingError("That facility does not offer that time.")

    open_count = Appointment.objects.filter(
        patient=patient, status__in=Appointment.OPEN_STATUSES
    ).count()
    if open_count >= MAX_OPEN_APPOINTMENTS_PER_PATIENT:
        raise BookingError(
            f"You already have {open_count} upcoming appointments. "
            "Cancel one before booking another."
        )

    # Lock the rows that decide whether capacity remains.
    taken = (
        Appointment.objects.select_for_update()
        .filter(
            facility=facility,
            service_type=service_type,
            # Same pool: a named clinician's list is not the general clinic's.
            provider=provider,
            slot_start=slot_start,
            status__in=Appointment.OPEN_STATUSES,
        )
        .count()
    )
    if taken >= template.capacity_per_slot:
        raise SlotUnavailable("That time has just been taken. Please choose another.")

    try:
        return Appointment.objects.create(
            facility=facility,
            service_type=service_type,
            patient=patient,
            provider=provider,
            slot_start=slot_start,
            slot_end=slot_start + timedelta(minutes=template.slot_minutes),
            booked_via=booked_via,
        )
    except IntegrityError as exc:
        # The partial unique constraint caught a double-tap by the same patient.
        raise SlotUnavailable("You already have a booking at that time.") from exc


def _template_for(
    facility, service_type, slot_start, provider=None
) -> ScheduleTemplate | None:
    """The template a given slot start belongs to, or None if it is not on a
    slot boundary for that provider's list."""
    local = timezone.localtime(slot_start)
    for template in ScheduleTemplate.objects.filter(
        facility=facility,
        service_type=service_type,
        provider=provider,
        weekday=local.weekday(),
        active=True,
    ):
        for start, _end in _slot_starts(template, local.date()):
            if timezone.make_aware(start) == slot_start:
                return template
    return None


@transaction.atomic
def cancel(appointment: Appointment) -> Appointment:
    if appointment.status not in Appointment.OPEN_STATUSES:
        raise BookingError(
            f"This appointment is already {appointment.get_status_display().lower()}."
        )
    if appointment.slot_start <= timezone.now():
        raise BookingError(
            "This appointment time has passed. Contact the facility directly."
        )
    appointment.status = Appointment.Status.CANCELLED
    appointment.cancelled_at = timezone.now()
    appointment.save(update_fields=["status", "cancelled_at"])
    return appointment
