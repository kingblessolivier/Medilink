"""Settings for the test suite.

Identical to development, with two differences that exist because a test run is
not a user.

**Throttling is off.** DRF counts requests per client IP in the cache, and the
whole suite shares one IP and one cache. As the suite grew, later tests started
receiving 429 from a budget spent by earlier ones - so a test could pass alone,
pass in its own module, and fail in the full run purely because of how many
tests ran before it in the same minute. That is worse than a plain failure: it
is intermittent, and it moves whenever a module is added or renamed.

Rate limits are a production behaviour and belong in tests that assert them
explicitly, with the limit re-enabled via the `settings` fixture.

**The cache is local-memory.** No Redis dependency for a unit test, and each
run starts clean rather than inheriting a previous run's keys.
"""

from .dev import *  # noqa: F403

REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {},
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "medilink-tests",
    }
}

# Fail fast rather than retrying against a gateway that is not there.
SMS_BACKEND = "apps.notifications.sms.ConsoleSMSBackend"


# **The clinical gate is shut for tests, whatever the developer's .env says.**
#
# test.py inherits dev.py, which reads backend/.env - so a developer who has
# opened the gate locally (to demo the Care Guide, say) turns four gate tests
# red, including `test_the_gate_is_shut_out_of_the_box`. Those tests assert a
# SAFETY DEFAULT, and a safety default that any ambient config can flip is not
# being tested at all.
#
# Tests that need the gate open set these explicitly with the `settings`
# fixture, which is also what makes it obvious in the test which state it is
# asserting.
TRIAGE_PROTOCOL_VERSION = ""
TRIAGE_APPROVED_BY = ""
TRIAGE_APPROVED_ON = ""
TRIAGE_PROTOCOL_FILE = ""
