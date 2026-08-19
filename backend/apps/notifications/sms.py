"""SMS delivery.

SMS is the PRIMARY notification channel, not a fallback. It reaches a patient
whose data has run out, and it reaches feature phones, which web push never
will.

Every message must fit 160 GSM-7 characters: a longer one is billed as two, and
non-GSM7 characters (accented Kinyarwanda or French) get mangled by the
network. `render()` enforces both.
"""

import logging
import unicodedata

from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)

MAX_SMS_CHARS = 160

GSM7 = set(
    "@£$¥èéùìòÇØøÅå"
    "Δ_ΦΓΛΩΠΨΣΘΞÆæ"
    "ßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿"
    "abcdefghijklmnopqrstuvwxyzäöñüà\n\r"
)


def to_gsm7(text: str) -> str:
    """Strip accents that the network would mangle into question marks."""
    out = []
    for char in text:
        if char in GSM7:
            out.append(char)
            continue
        folded = "".join(
            c
            for c in unicodedata.normalize("NFD", char)
            if unicodedata.category(c) != "Mn"
        )
        out.append("".join(c if c in GSM7 else "?" for c in folded))
    return "".join(out)


def render(text: str) -> str:
    """GSM-7 safe and within one message segment."""
    safe = to_gsm7(text)
    if len(safe) > MAX_SMS_CHARS:
        logger.warning("sms_truncated", extra={"length": len(safe)})
        safe = safe[: MAX_SMS_CHARS - 1].rstrip() + "."
    return safe


class SMSBackend:
    def send(self, phone: str, body: str) -> str:
        """Deliver one message. Returns a provider reference."""
        raise NotImplementedError


class ConsoleSMSBackend(SMSBackend):
    """Development default. Prints instead of sending, so nobody is charged
    and no real phone is messaged from a developer machine."""

    def send(self, phone: str, body: str) -> str:
        logger.info("SMS to %s: %s", phone, body)
        print(f"\n--- SMS -> {phone} ---\n{body}\n---\n")
        return f"console-{timezone.now().timestamp():.0f}"


class UnconfiguredSMSBackend(SMSBackend):
    """Production placeholder.

    Fails loudly rather than silently dropping messages: a patient who is never
    told to leave home is worse off than before MediLink existed.
    """

    def send(self, phone: str, body: str) -> str:
        raise RuntimeError(
            "No SMS backend configured. Set SMS_BACKEND to a real gateway "
            "before running in production."
        )


def get_backend() -> SMSBackend:
    path = getattr(
        settings, "SMS_BACKEND", "apps.notifications.sms.ConsoleSMSBackend"
    )
    return import_string(path)()
