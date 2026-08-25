"""Reading platform configuration.

The model itself lives in models.py, because Django only auto-discovers
models there. This module is the read path, and it is separate because
the caching is the interesting part: `current()` is called on the nearby
search, which is the hottest endpoint in the system.
"""

from django.core.cache import cache

from .models import CACHE_KEY, CACHE_SECONDS, PlatformSettings


def current() -> PlatformSettings:
    """The live settings row, cached.

    Read on the nearby search, which is the hottest endpoint in the system, so
    it must not become a database round trip per request. Five minutes is
    generous for a value somebody changes a handful of times a year, and the
    save() above clears the key so a change is visible immediately anyway.
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    row, _ = PlatformSettings.objects.get_or_create(pk=1)
    cache.set(CACHE_KEY, row, CACHE_SECONDS)
    return row


def search_radius_m() -> int:
    """The configured starting radius, falling back to the deployed default.

    Falls back rather than raising: a discovery search that fails because a
    settings row is missing would take the whole product down for a
    configuration detail.
    """
    from django.conf import settings as django_settings

    try:
        return current().default_search_radius_m
    except Exception:  # noqa: BLE001 - configuration must never break search
        return getattr(django_settings, "DEFAULT_SEARCH_RADIUS_M", 5000)
