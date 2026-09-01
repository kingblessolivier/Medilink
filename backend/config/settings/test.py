"""Settings for the test suite.

Two pieces of shared state must not leak into tests:

* **The cache.** dev and prod point `default` at Redis. A test run should not
  need a live Redis to pass, and must not carry state from one run to the next.

* **The anon throttle.** `AnonRateThrottle` counts requests in that same shared
  cache, keyed by client IP. Every API test hits the same IP, so with Redis the
  counter survives the run: the fifth `pytest` inside a minute starts returning
  429 and the API tests fail for a reason unrelated to the code under test.

Throttling is therefore off by default here, and asserted explicitly by
test_throttling.py, which installs its own rate.
"""

from .dev import *  # noqa: F403

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}

REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {"anon": None},
}

# Tests assert on log output nowhere, and a DEBUG-level root logger makes a
# failure report unreadable.
LOGGING["root"]["level"] = "WARNING"  # noqa: F405
