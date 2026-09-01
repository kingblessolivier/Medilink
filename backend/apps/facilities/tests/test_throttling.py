"""The anon throttle, asserted in the one place that wants it.

config/settings/test.py switches throttling off for the rest of the suite -
otherwise the shared rate counter makes every other API test order-dependent.
That trade is only safe if the throttle itself is still covered, which is what
this file is for.

DRF binds THROTTLE_RATES onto the throttle class at import time, so
override_settings does not reach it. The rate is installed on the class.
"""

import pytest
from django.core.cache import cache
from rest_framework.throttling import AnonRateThrottle

pytestmark = pytest.mark.django_db

NEARBY = "/api/v1/facilities/nearby"
KIGALI = {"lat": -1.9536, "lng": 30.0606}


@pytest.fixture
def rate_limited(monkeypatch):
    """Install a 3/min anon rate and start from an empty counter."""
    monkeypatch.setattr(AnonRateThrottle, "THROTTLE_RATES", {"anon": "3/min"})
    cache.clear()
    yield
    cache.clear()


def test_anonymous_requests_are_throttled(api_client, rate_limited):
    for _ in range(3):
        assert api_client.get(NEARBY, KIGALI).status_code == 200

    response = api_client.get(NEARBY, KIGALI)
    assert response.status_code == 429


def test_throttled_response_is_rfc7807_like_every_other_error(
    api_client, rate_limited
):
    for _ in range(4):
        response = api_client.get(NEARBY, KIGALI)

    assert response.status_code == 429
    body = response.json()
    # config/exceptions.py shapes every error the same way; a 429 that broke
    # that contract would crash the client's error handler.
    assert "type" in body
    assert "detail" in body
