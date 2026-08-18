"""Wait-time snapshots.

PHASE 0: no facility runs the reception tool yet, so no live queue data exists.
Every facility therefore reports `not_reported` or `closed` - never a number.

PHASE 1 replaces the body of wait_snapshot() with the real implementation from
docs/04-nearby-facilities.md, which reads QueueEntry counts and ServiceTimeStat
medians. The four status values and the MIN_SERVICE_TIME_SAMPLES gate stay
exactly as they are here, so the frontend never has to change.

The gate is the honesty rule made executable: a facility with fewer than
MIN_SERVICE_TIME_SAMPLES samples reports `insufficient_data`, not a
confident-looking number derived from four data points.
"""

from django.utils import timezone

STATUS_AVAILABLE = "available"
STATUS_NOT_REPORTED = "not_reported"
STATUS_INSUFFICIENT_DATA = "insufficient_data"
STATUS_CLOSED = "closed"

ALL_STATUSES = (
    STATUS_AVAILABLE,
    STATUS_NOT_REPORTED,
    STATUS_INSUFFICIENT_DATA,
    STATUS_CLOSED,
)


def wait_snapshot(facilities, service_code=None, now=None) -> dict:
    """Map facility id -> wait dict, in a single pass.

    Never call this per facility inside a loop: it is an N+1 on the hottest
    endpoint in the system. Pass the whole result list at once.
    """
    now = now or timezone.localtime()
    snapshot = {}

    for facility in facilities:
        # `is_open` is annotated by find_nearby(); fall back for detail views.
        is_open = getattr(facility, "is_open", None)
        if is_open is None:
            from .services import is_open_now

            is_open = is_open_now(facility, now)

        if not is_open:
            snapshot[facility.id] = {
                "status": STATUS_CLOSED,
                "minutes": None,
                "people_waiting": None,
                "as_of": now.isoformat(),
            }
            continue

        if not facility.reports_queue:
            snapshot[facility.id] = {
                "status": STATUS_NOT_REPORTED,
                "minutes": None,
                "people_waiting": None,
                "as_of": now.isoformat(),
            }
            continue

        # Phase 1 lands here: read live counts and ServiceTimeStat medians,
        # apply the MIN_SERVICE_TIME_SAMPLES gate, then return either
        # STATUS_AVAILABLE with minutes or STATUS_INSUFFICIENT_DATA.
        snapshot[facility.id] = {
            "status": STATUS_INSUFFICIENT_DATA,
            "minutes": None,
            "people_waiting": None,
            "as_of": now.isoformat(),
        }

    return snapshot
