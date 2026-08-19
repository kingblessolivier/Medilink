"""Queue domain logic.

All three future channels (provider web, patient PWA, USSD) call these
functions rather than reimplementing rules in a view. If booking or queue rules
live in a view, a USSD user and an app user get different behaviour - and that
bug is found by a patient, at a hospital.
"""

import statistics
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.facilities.models import Facility, OpeningHours, ServiceType
from apps.facilities.wait import (
    STATUS_AVAILABLE,
    STATUS_CLOSED,
    STATUS_INSUFFICIENT_DATA,
    STATUS_NOT_REPORTED,
)
from apps.patients.models import Patient

from .models import QueueEntry, ServiceTimeStat

# Used only when a facility reports a queue but has no statistics yet. It never
# reaches a patient: the MIN sample-size gate returns insufficient_data first.
FALLBACK_SERVICE_MINUTES = 10.0

# Confidence bands, derived from sample size. The UI widens its wording as
# confidence falls: "about 35 min" at high, "roughly 30-50 min" at low.
CONFIDENCE_HIGH_SAMPLES = 100
CONFIDENCE_MEDIUM_SAMPLES = 40

STATS_WINDOW_DAYS = 30


class QueueError(Exception):
    """Domain rule violation - mapped to HTTP 409 by the view layer."""


# --------------------------------------------------------------------------
# Ticket codes
# --------------------------------------------------------------------------


def next_ticket_code(facility: Facility, service_type: ServiceType, now=None) -> str:
    """Sequential per facility, service and day: A-001, A-002, ...

    Printed on the paper slip a patient carries, so it must be short and
    readable aloud across a busy reception desk.
    """
    now = now or timezone.localtime()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    todays_count = QueueEntry.objects.filter(
        facility=facility, service_type=service_type, joined_at__gte=start_of_day
    ).count()
    letter = (service_type.code[:1] or "X").upper()
    return f"{letter}-{todays_count + 1:03d}"


# --------------------------------------------------------------------------
# Check-in
# --------------------------------------------------------------------------


@transaction.atomic
def check_in(
    *,
    facility: Facility,
    service_type: ServiceType,
    phone: str | None = None,
    walk_in_name: str = "",
    staff_user=None,
    idempotency_key: str = "",
    joined_at=None,
) -> tuple[QueueEntry, bool]:
    """Add a patient to the queue. Returns (entry, created).

    `joined_at` is accepted so that offline sync can replay the receptionist's
    own timestamp: someone offline for ten minutes must not push their patients
    behind everyone checked in since.
    """
    if idempotency_key:
        existing = QueueEntry.objects.filter(
            facility=facility, idempotency_key=idempotency_key
        ).first()
        if existing is not None:
            return existing, False

    patient = None
    if phone:
        patient, _ = Patient.get_or_create_by_phone(phone)
        Patient.objects.filter(pk=patient.pk).update(last_seen_at=timezone.now())

        # One open entry per patient per facility, or the queue fills with
        # duplicates every time someone taps twice.
        already_open = QueueEntry.objects.filter(
            facility=facility,
            patient=patient,
            status__in=QueueEntry.OPEN_STATUSES,
        ).first()
        if already_open is not None:
            raise QueueError(
                f"{patient} is already in the queue "
                f"({already_open.ticket_code}, {already_open.get_status_display()})."
            )

    if not patient and not walk_in_name:
        raise QueueError("Provide a phone number or a walk-in name.")

    joined_at = joined_at or timezone.now()

    entry = QueueEntry.objects.create(
        facility=facility,
        service_type=service_type,
        patient=patient,
        walk_in_name="" if patient else walk_in_name,
        joined_at=joined_at,
        checked_in_by=staff_user,
        ticket_code=next_ticket_code(facility, service_type),
        idempotency_key=idempotency_key,
    )

    # The first check-in is what makes a facility a queue reporter.
    if not facility.reports_queue:
        Facility.objects.filter(pk=facility.pk).update(reports_queue=True)
        facility.reports_queue = True

    return entry, True


# --------------------------------------------------------------------------
# Queue transitions
# --------------------------------------------------------------------------


def _transition(entry: QueueEntry, *, to_status: str, allowed_from, stamp=None):
    if entry.status not in allowed_from:
        raise QueueError(
            f"Cannot move an entry from {entry.get_status_display()} to {to_status}."
        )
    now = timezone.now()
    entry.status = to_status
    if stamp:
        setattr(entry, stamp, now)
    if to_status in {
        QueueEntry.Status.SERVED,
        QueueEntry.Status.LEFT,
        QueueEntry.Status.CANCELLED,
    }:
        entry.closed_at = now
    entry.save()
    return entry


def call(entry: QueueEntry) -> QueueEntry:
    return _transition(
        entry,
        to_status=QueueEntry.Status.CALLED,
        allowed_from={QueueEntry.Status.WAITING},
        stamp="called_at",
    )


def serve(entry: QueueEntry) -> QueueEntry:
    """Mark served. This is what feeds ServiceTimeStat, and therefore ETAs."""
    return _transition(
        entry,
        to_status=QueueEntry.Status.SERVED,
        allowed_from={QueueEntry.Status.WAITING, QueueEntry.Status.CALLED},
        stamp="served_at",
    )


def skip(entry: QueueEntry) -> QueueEntry:
    """Called but did not answer."""
    return _transition(
        entry,
        to_status=QueueEntry.Status.LEFT,
        allowed_from={QueueEntry.Status.WAITING, QueueEntry.Status.CALLED},
    )


def cancel(entry: QueueEntry) -> QueueEntry:
    return _transition(
        entry,
        to_status=QueueEntry.Status.CANCELLED,
        allowed_from={QueueEntry.Status.WAITING, QueueEntry.Status.CALLED},
    )


TRANSITIONS = {"call": call, "serve": serve, "skip": skip, "cancel": cancel}


# --------------------------------------------------------------------------
# Statistics and ETA
# --------------------------------------------------------------------------


def median_service_minutes(facility_id, service_type_id, hour, stats=None):
    """Median minutes per patient, with the sample size behind it."""
    if stats is None:
        stat = ServiceTimeStat.objects.filter(
            facility_id=facility_id,
            service_type_id=service_type_id,
            hour_of_day=hour,
        ).first()
    else:
        stat = stats.get((facility_id, service_type_id, hour))

    if stat is None:
        return FALLBACK_SERVICE_MINUTES, 0
    return stat.median_minutes, stat.sample_size


def confidence_for(sample_size: int) -> str:
    if sample_size >= CONFIDENCE_HIGH_SAMPLES:
        return "high"
    if sample_size >= CONFIDENCE_MEDIUM_SAMPLES:
        return "medium"
    return "low"


def eta_for(entry: QueueEntry, now=None) -> dict:
    """Minutes until this entry is likely to be called."""
    now = now or timezone.localtime()
    position = entry.position()
    minutes, samples = median_service_minutes(
        entry.facility_id, entry.service_type_id, now.hour
    )

    if samples < settings.MIN_SERVICE_TIME_SAMPLES:
        return {
            "eta_minutes": None,
            "eta_confidence": None,
            "position": position,
            "people_ahead": max(0, position - 1),
        }

    return {
        # People ahead, not position: the person being served right now is
        # partway through, so counting them in full overstates the wait.
        "eta_minutes": round(max(0, position - 1) * minutes),
        "eta_confidence": confidence_for(samples),
        "position": position,
        "people_ahead": max(0, position - 1),
    }


def refresh_service_time_stats(facility=None, window_days=STATS_WINDOW_DAYS) -> int:
    """Recompute medians from served entries. Returns rows written.

    Run this on a schedule (management command, then Celery beat in Phase 2).
    Computing it per request would put a full aggregation on the hottest
    endpoint in the system.
    """
    since = timezone.now() - timedelta(days=window_days)
    served = QueueEntry.objects.filter(
        status=QueueEntry.Status.SERVED,
        served_at__gte=since,
        served_at__isnull=False,
    ).select_related("facility", "service_type")
    if facility is not None:
        served = served.filter(facility=facility)

    buckets: dict[tuple, list[float]] = {}
    for entry in served.iterator():
        local_join = timezone.localtime(entry.joined_at)
        minutes = (entry.served_at - entry.joined_at).total_seconds() / 60
        if minutes <= 0 or minutes > 8 * 60:
            # Guard against a receptionist marking yesterday's queue served.
            continue
        key = (entry.facility_id, entry.service_type_id, local_join.hour)
        buckets.setdefault(key, []).append(minutes)

    written = 0
    for (facility_id, service_type_id, hour), samples in buckets.items():
        ServiceTimeStat.objects.update_or_create(
            facility_id=facility_id,
            service_type_id=service_type_id,
            hour_of_day=hour,
            defaults={
                "median_minutes": statistics.median(samples),
                "sample_size": len(samples),
            },
        )
        written += 1
    return written


# --------------------------------------------------------------------------
# Wait snapshot - the real implementation behind apps.facilities.wait
# --------------------------------------------------------------------------


def wait_snapshot(facilities, service_code=None, now=None) -> dict:
    """Map facility id -> wait dict, in a fixed number of queries.

    Never call this per facility in a loop: it is an N+1 on the hottest
    endpoint in the system.
    """
    now = now or timezone.localtime()
    facilities = list(facilities)
    ids = [f.id for f in facilities]
    stamp = now.isoformat()

    def unknown(status):
        return {
            "status": status,
            "minutes": None,
            "people_waiting": None,
            "as_of": stamp,
        }

    if not ids:
        return {}

    waiting_qs = QueueEntry.objects.filter(
        facility_id__in=ids, status=QueueEntry.Status.WAITING
    )
    if service_code:
        waiting_qs = waiting_qs.filter(service_type__code=service_code)

    counts = {
        row["facility_id"]: row["n"]
        for row in waiting_qs.values("facility_id").annotate(n=Count("id"))
    }

    stats = {
        (s.facility_id, s.service_type_id, s.hour_of_day): s
        for s in ServiceTimeStat.objects.filter(
            facility_id__in=ids, hour_of_day=now.hour
        )
    }

    # Which service each facility is being measured on.
    service_ids = {}
    if service_code:
        service_type = ServiceType.objects.filter(code=service_code).first()
        if service_type:
            service_ids = dict.fromkeys(ids, service_type.id)

    # find_nearby() annotates is_open. Anything else - the detail endpoint, a
    # plain list - does not, and asking each facility separately would be an
    # N+1 on the hottest endpoint in the system. Resolve them all in one query.
    unannotated = [f.id for f in facilities if getattr(f, "is_open", None) is None]
    open_ids = set()
    if unannotated:
        open_ids = set(
            OpeningHours.objects.filter(
                facility_id__in=unannotated,
                weekday=now.weekday(),
                opens_at__lte=now.time(),
                closes_at__gte=now.time(),
            ).values_list("facility_id", flat=True)
        )

    snapshot = {}
    for facility in facilities:
        is_open = getattr(facility, "is_open", None)
        if is_open is None:
            is_open = facility.id in open_ids

        if not is_open:
            snapshot[facility.id] = unknown(STATUS_CLOSED)
            continue

        if not facility.reports_queue:
            snapshot[facility.id] = unknown(STATUS_NOT_REPORTED)
            continue

        waiting = counts.get(facility.id, 0)
        service_type_id = service_ids.get(facility.id)

        if service_type_id is None:
            # No service filter: use the busiest service this facility has
            # statistics for, which is the honest worst case.
            candidates = [
                s
                for (fid, _sid, _h), s in stats.items()
                if fid == facility.id
            ]
            stat = max(candidates, key=lambda s: s.sample_size, default=None)
        else:
            stat = stats.get((facility.id, service_type_id, now.hour))

        if stat is None or stat.sample_size < settings.MIN_SERVICE_TIME_SAMPLES:
            entry = unknown(STATUS_INSUFFICIENT_DATA)
            entry["people_waiting"] = waiting
            snapshot[facility.id] = entry
            continue

        snapshot[facility.id] = {
            "status": STATUS_AVAILABLE,
            "minutes": round(waiting * stat.median_minutes),
            "people_waiting": waiting,
            "as_of": stamp,
        }

    return snapshot
