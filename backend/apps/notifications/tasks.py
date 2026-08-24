"""Scheduled notification work.

Runs under Celery beat in production. Every task is also reachable as a
management command (`send_due_notifications`) so Phase 2 can pilot on plain
cron before Celery is deployed - one fewer moving part at the pilot facility.

Every task is idempotent by construction: `dispatch()` creates the Notification
row first and the database unique constraint rejects the duplicate. Two
overlapping runs are safe.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import dispatch
from apps.queueing.models import QueueEntry
from apps.queueing.services import eta_for
from apps.queueing.travel import leave_by, travel_minutes
from apps.scheduling.models import Appointment

logger = logging.getLogger(__name__)

# How close to departure time we start telling people to go.
LEAVE_NOW_WINDOW_MINUTES = 5


def short_name(name: str, limit: int = 22) -> str:
    """'Kimironko Health Centre' -> 'Kimironko HC', to fit one SMS segment."""
    for long, short in (
        ("Health Centre", "HC"),
        ("Health Center", "HC"),
        ("District Hospital", "DH"),
        ("Referral Hospital", "RH"),
        ("Polyclinic", "PC"),
        ("Health Post", "HP"),
    ):
        name = name.replace(long, short)
    return name[:limit]


def send_leave_now_notifications() -> int:
    """Tell waiting patients when to set off."""
    now = timezone.localtime()
    sent = 0

    entries = QueueEntry.objects.filter(
        status=QueueEntry.Status.WAITING, patient__isnull=False
    ).select_related("patient", "facility", "service_type")

    for entry in entries:
        estimate = eta_for(entry, now=now)
        if estimate["eta_minutes"] is None:
            continue  # no reliable statistics - say nothing rather than guess

        travel = travel_minutes(entry.patient.home_location, entry.facility.location)
        depart = leave_by(
            now=now, eta_minutes=estimate["eta_minutes"], travel=travel
        )
        if depart is None:
            continue
        if depart > now + timedelta(minutes=LEAVE_NOW_WINDOW_MINUTES):
            continue  # not yet time

        if dispatch(
            kind=Notification.Kind.LEAVE_NOW,
            phone=entry.patient.phone,
            language=entry.patient.language,
            patient=entry.patient,
            queue_entry=entry,
            position=estimate["position"],
            facility=short_name(entry.facility.name),
        ):
            sent += 1

    return sent


def send_called_notification(entry: QueueEntry) -> bool:
    """Fired when a receptionist presses Call."""
    if not entry.patient_id or not entry.patient:
        return False
    return bool(
        dispatch(
            kind=Notification.Kind.CALLED,
            phone=entry.patient.phone,
            language=entry.patient.language,
            patient=entry.patient,
            queue_entry=entry,
            ticket=entry.ticket_code,
            facility=short_name(entry.facility.name),
        )
    )


def send_appointment_reminders() -> int:
    """24-hour and 2-hour reminders.

    A booking nobody honours is worse than no booking: it teaches patients that
    the system does not work.
    """
    now = timezone.localtime()
    sent = 0

    windows = (
        (Notification.Kind.APPT_REMINDER_24H, timedelta(hours=24), timedelta(hours=1)),
        (Notification.Kind.APPT_REMINDER_2H, timedelta(hours=2), timedelta(minutes=30)),
    )

    for kind, lead, tolerance in windows:
        target = now + lead
        due = Appointment.objects.filter(
            status=Appointment.Status.BOOKED,
            slot_start__gte=target - tolerance,
            slot_start__lte=target + tolerance,
        ).select_related("patient", "facility")

        for appointment in due:
            if dispatch(
                kind=kind,
                phone=appointment.patient.phone,
                language=appointment.patient.language,
                patient=appointment.patient,
                appointment=appointment,
                time=timezone.localtime(appointment.slot_start).strftime("%H:%M"),
                facility=short_name(appointment.facility.name),
                reference=appointment.reference,
            ):
                sent += 1

    return sent


def mark_no_shows() -> int:
    """Close out bookings nobody arrived for.

    Without this the no-show rate is invisible, and the no-show rate is what a
    facility uses to judge whether MediLink is worth keeping.
    """
    cutoff = timezone.now() - timedelta(minutes=60)
    return Appointment.objects.filter(
        status=Appointment.Status.BOOKED, slot_end__lt=cutoff
    ).update(status=Appointment.Status.NO_SHOW)


def close_unrecorded() -> int:
    """Close out appointments where the patient arrived and nothing followed.

    `ARRIVED` is in OPEN_STATUSES, and only BOOKED was ever swept - so an
    appointment where reception pressed "arrived" and never pressed "served"
    stayed open indefinitely. Two things went wrong quietly.

    It counted forever against MAX_OPEN_APPOINTMENTS_PER_PATIENT, so after
    three such visits a patient was locked out of booking, told to cancel
    appointments that were months past. And it was neither served nor a
    no-show, so it sat outside every number on the reports screen.

    UNRECORDED rather than NO_SHOW: the patient came. Counting a facility's
    own record-keeping as its patients' failure would corrupt the one metric
    that facility uses to judge the product.
    """
    cutoff = timezone.now() - timedelta(hours=12)
    return Appointment.objects.filter(
        status=Appointment.Status.ARRIVED, slot_end__lt=cutoff
    ).update(status=Appointment.Status.UNRECORDED)


def run_all() -> dict:
    return {
        "leave_now": send_leave_now_notifications(),
        "reminders": send_appointment_reminders(),
        "no_shows": mark_no_shows(),
        "unrecorded": close_unrecorded(),
    }


# --------------------------------------------------------------------------
# Celery bindings, registered only when Celery is installed and configured.
# --------------------------------------------------------------------------

try:
    from celery import shared_task
except ImportError:  # pragma: no cover - Celery is optional in Phase 2
    shared_task = None

if shared_task is not None:

    @shared_task(name="notifications.run_due")
    def run_due_task():
        return run_all()

    @shared_task(name="notifications.send_called")
    def send_called_task(queue_entry_id: int):
        entry = QueueEntry.objects.select_related("patient", "facility").get(
            pk=queue_entry_id
        )
        return send_called_notification(entry)
