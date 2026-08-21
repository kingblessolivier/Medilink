from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]
CORS_ALLOW_ALL_ORIGINS = True

# Loud in development: an unexpected 500 should be obvious, not swallowed.
# Extends the base config rather than replacing it. Replacing it silently
# dropped the redact_pii filter, so patient phone numbers were being written
# to the console in DEVELOPMENT - which is where people actually read logs,
# and where a number is most likely to be seen, copied into a ticket, or
# pasted into a chat. Caught by `manage.py readiness`.
LOGGING = {
    **LOGGING,  # noqa: F405
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        **LOGGING["loggers"],  # noqa: F405
        "django.db.backends": {"level": "WARNING"},
        "apps": {"level": "DEBUG", "propagate": True},
    },
}
