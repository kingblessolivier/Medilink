"""Keeping patient identifiers out of the logs.

docs/08 section 6 requires that no PII reaches application logs, asserted by a
test. This is the mechanism.

**Why a filter rather than discipline.** "Do not log phone numbers" is a rule
somebody breaks at 2am while debugging a check-in that will not sync, and the
number then sits in a log aggregator with a different retention policy and a
different access list from the database. The redaction has to happen on the
way out, not rely on every call site remembering.

**Why phone numbers specifically.** In MediLink the phone number IS the
identity - it is what USSD, WhatsApp, SMS and now sign-in all key on, and it
is the one field that re-identifies a person on its own. Names are redacted
where they arrive in a known field; free-text names cannot be caught
generically without mangling every log line that contains a capital letter,
and pretending otherwise would be worse than being clear about the limit.

**What this does NOT do.** It is not a guarantee that nothing sensitive is
ever logged. It removes the identifiers we can recognise. Reviewing what gets
logged remains part of code review.
"""

import logging
import re

# +250788123456, 250788123456, 0788123456 - and the same with spaces or
# dashes, which is how somebody types one into a form.
PHONE_PATTERN = re.compile(
    r"(?:\+?250[\s-]?|0)(?:7\d{2})[\s-]?\d{3}[\s-]?\d{3}\b"
)

# Any run of 9+ digits that is not obviously a timestamp. Catches a phone
# written in a format the pattern above misses, and national ID numbers.
LONG_DIGITS_PATTERN = re.compile(r"\b\d{9,}\b")

REDACTED = "[redacted]"


def scrub(text: str) -> str:
    """Remove recognisable patient identifiers from a string."""
    text = PHONE_PATTERN.sub(REDACTED, text)
    return LONG_DIGITS_PATTERN.sub(REDACTED, text)


class RedactPatientIdentifiers(logging.Filter):
    """Scrubs the message and the arguments of every record passing through.

    Returns True always - this filters CONTENT, not records. Dropping a log
    line because it contained a phone number would lose the operational
    signal that the line existed for.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = scrub(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    key: scrub(value) if isinstance(value, str) else value
                    for key, value in record.args.items()
                }
            else:
                record.args = tuple(
                    scrub(value) if isinstance(value, str) else value
                    for value in record.args
                )

        # Structured extras travel here. `exc_text` is the rendered traceback,
        # which is exactly where a phone number ends up when a check-in raises.
        if getattr(record, "exc_text", None):
            record.exc_text = scrub(record.exc_text)

        return True


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_pii": {"()": "config.logging.RedactPatientIdentifiers"},
    },
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            # On the handler, so it applies to everything reaching it -
            # including third-party loggers nobody here wrote.
            "filters": ["redact_pii"],
            "formatter": "standard",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
