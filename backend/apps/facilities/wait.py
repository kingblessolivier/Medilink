"""Wait-time status vocabulary, and the entry point clients call.

The four statuses live here because `facilities` must not import `queueing` at
module level - `queueing` imports facility models, and a top-level import in
both directions is circular. The real computation lives in
apps.queueing.services.wait_snapshot and is reached through a function-level
import below.

The MIN_SERVICE_TIME_SAMPLES gate is the honesty rule made executable: a
facility with too few samples reports `insufficient_data`, not a
confident-looking number derived from four data points. There is deliberately
no status meaning "estimated" - we never guess.
"""

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
    """Map facility id -> wait dict for a whole result list at once."""
    from apps.queueing.services import wait_snapshot as _wait_snapshot

    return _wait_snapshot(facilities, service_code=service_code, now=now)
