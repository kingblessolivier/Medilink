"""Operational reporting for one facility.

docs/09 is blunt about why this exists: the reports screen is how a facility
decides to keep using MediLink. So it answers the questions a facility manager
actually has, and nothing else:

    How many people did we see?
    How long did they wait?
    Who did not turn up?
    Which services are under pressure?

Every number is measured, never modelled. Where there is not enough data to
answer honestly, the field is null and the UI says so - the same rule the
patient-facing wait times follow.
"""

import statistics
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from apps.queueing.models import QueueEntry
from apps.scheduling.models import Appointment

# Below this, a median is noise. Same reasoning as the wait-time gate: a
# "median wait" over three visits tells a manager nothing and invites them to
# act on it anyway.
MIN_SAMPLE = 10


def _median_wait_minutes(entries) -> tuple[float | None, int]:
    """Median arrival-to-called minutes, and the sample behind it."""
    waits = [
        (entry.called_at - entry.joined_at).total_seconds() / 60
        for entry in entries
        if entry.called_at and entry.joined_at
    ]
    # Guard against a receptionist clearing yesterday's queue this morning.
    waits = [w for w in waits if 0 <= w <= 8 * 60]
    if len(waits) < MIN_SAMPLE:
        return None, len(waits)
    return round(statistics.median(waits), 1), len(waits)


def facility_report(facility, days: int = 30) -> dict:
    """Everything the reports screen shows, in three queries."""
    now = timezone.localtime()
    since = now - timedelta(days=days)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    entries = list(
        QueueEntry.objects.filter(facility=facility, joined_at__gte=since)
        .select_related("service_type")
        .only("joined_at", "called_at", "served_at", "status", "service_type__code")
    )

    served = [e for e in entries if e.status == QueueEntry.Status.SERVED]
    today = [e for e in entries if e.joined_at >= today_start]

    median, sample = _median_wait_minutes(entries)
    # This week against the week before - the comparison a manager actually
    # makes, and the one docs/09 says to put in front of them.
    week_ago = now - timedelta(days=7)
    fortnight_ago = now - timedelta(days=14)
    this_week, _ = _median_wait_minutes(
        [e for e in entries if e.joined_at >= week_ago]
    )
    last_week, _ = _median_wait_minutes(
        [e for e in entries if fortnight_ago <= e.joined_at < week_ago]
    )

    appointments = Appointment.objects.filter(
        facility=facility, slot_start__gte=since
    )
    total_appointments = appointments.count()
    no_shows = appointments.filter(status=Appointment.Status.NO_SHOW).count()

    by_service = (
        QueueEntry.objects.filter(facility=facility, joined_at__gte=since)
        .values("service_type__code")
        .annotate(n=Count("id"))
        .order_by("-n")[:8]
    )

    return {
        "facility": facility.name,
        "days": days,
        "as_of": now.isoformat(),
        "today": {
            "checked_in": len(today),
            "waiting": sum(
                1 for e in today if e.status == QueueEntry.Status.WAITING
            ),
            "served": sum(1 for e in today if e.status == QueueEntry.Status.SERVED),
        },
        "period": {
            "checked_in": len(entries),
            "served": len(served),
            "left_without_being_seen": sum(
                1 for e in entries if e.status == QueueEntry.Status.LEFT
            ),
        },
        "wait": {
            # null, not zero, when the sample is too small to mean anything.
            "median_minutes": median,
            "sample_size": sample,
            "this_week_minutes": this_week,
            "last_week_minutes": last_week,
            "enough_data": median is not None,
        },
        "appointments": {
            "total": total_appointments,
            "no_shows": no_shows,
            "no_show_rate": (
                round(no_shows / total_appointments, 3)
                if total_appointments
                else None
            ),
        },
        "demand": [
            {"service": row["service_type__code"], "count": row["n"]}
            for row in by_service
        ],
    }
