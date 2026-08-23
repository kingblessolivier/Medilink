from .base import *  # noqa: F403

DEBUG = False

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Never log request bodies on patient endpoints - see docs/08.
# Extends the base config rather than replacing it.
#
# This block used to define `handlers` from scratch, which silently dropped
# the redact_pii filter - so patient phone numbers would have been written
# unredacted to production logs, where they would sit in an aggregator with a
# different retention policy and a different access list from the database.
#
# `dev.py` had the identical bug and was fixed first; this one survived
# because nothing runs prod settings locally. `manage.py readiness` caught it,
# which is the entire reason that command reports on log redaction.
LOGGING = {
    **LOGGING,  # noqa: F405
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        **LOGGING["loggers"],  # noqa: F405
        "apps": {"level": "INFO", "propagate": True},
    },
}

# A console SMS backend in production means patients are never told to leave
# home - silently. Fail at startup instead.
if SMS_BACKEND.endswith("ConsoleSMSBackend"):  # noqa: F405
    SMS_BACKEND = "apps.notifications.sms.UnconfiguredSMSBackend"
