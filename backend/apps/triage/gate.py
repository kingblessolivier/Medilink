"""The clinical gate.

Anything that routes patients toward or away from care carries clinical
liability. docs/08 section 8 lists eight conditions that must all hold before
this feature may be served to a patient. Six of them are human work - a
clinician reading the protocol, a regulator being consulted - and cannot be
satisfied by code.

So the code enforces the gate instead of trusting a checklist:

    **Every triage endpoint returns 503 until an approval is configured.**

Out of the box, and in every environment where nobody has recorded a clinician
sign-off, `/triage/*` is unavailable. That is the correct default. The
engineering is finished and waiting; the clinical content is not ours to write.

To enable, once a licensed clinician has reviewed and signed off a specific
protocol version, set all four:

    TRIAGE_PROTOCOL_VERSION=2026.1
    TRIAGE_APPROVED_BY="Dr <name>, <registration number>"
    TRIAGE_APPROVED_ON=2026-09-01
    TRIAGE_PROTOCOL_FILE=protocols/routing.2026.1.json

The approval is recorded against every session, so a later rule change stays
traceable to what a given patient actually saw.

Do not weaken this to "warn and continue". A symptom checker that silently
degrades is worse than one that is switched off: patients trust what they are
shown.
"""

import logging
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger(__name__)


class TriageUnavailable(Exception):
    """Raised when the clinical gate is not satisfied. Maps to HTTP 503."""


@dataclass(frozen=True)
class Approval:
    protocol_version: str
    approved_by: str
    approved_on: str
    protocol_file: str


def approval() -> Approval | None:
    """The recorded clinician sign-off, or None if the gate is shut."""
    version = getattr(settings, "TRIAGE_PROTOCOL_VERSION", "")
    approved_by = getattr(settings, "TRIAGE_APPROVED_BY", "")
    approved_on = getattr(settings, "TRIAGE_APPROVED_ON", "")
    protocol_file = getattr(settings, "TRIAGE_PROTOCOL_FILE", "")

    if not (version and approved_by and approved_on and protocol_file):
        return None

    return Approval(
        protocol_version=version,
        approved_by=approved_by,
        approved_on=approved_on,
        protocol_file=protocol_file,
    )


def require_approval() -> Approval:
    record = approval()
    if record is None:
        logger.info("triage_gate_closed")
        raise TriageUnavailable(
            "The symptom checker is not available. It requires review and "
            "sign-off by a licensed clinician before it can be used."
        )
    return record


def is_enabled() -> bool:
    return approval() is not None
