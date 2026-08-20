"""Recording access to patient records.

Kept to one helper so that every call site looks the same and none of them can
half-record. Failures here are swallowed deliberately: an audit write must
never break a receptionist's check-in. A missing log line is a problem to fix;
a reception desk that stops working because logging failed is a worse one.
"""

import logging

from .models import PatientAccessLog

logger = logging.getLogger(__name__)


def client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def record(
    request,
    *,
    action: str,
    patient=None,
    facility=None,
    record_count: int = 1,
) -> None:
    """Log one access. Never raises."""
    try:
        user = getattr(request, "user", None)
        actor = user if getattr(user, "is_authenticated", False) else None
        # A patient principal is not a Django user; it carries `.patient`.
        acting_patient = getattr(user, "patient", None)
        if acting_patient is not None:
            actor = None

        PatientAccessLog.objects.create(
            actor=actor if actor and hasattr(actor, "pk") and not acting_patient else None,
            acting_patient=acting_patient,
            patient=patient,
            facility=facility,
            action=action,
            record_count=record_count,
            ip_address=client_ip(request),
        )
    except Exception:  # noqa: BLE001
        logger.exception("audit_write_failed", extra={"action": action})
