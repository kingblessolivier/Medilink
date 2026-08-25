"""Platform configuration an administrator may change without a deploy.

**Not everything in `settings.py` belongs here, and the split is the point.**

`DEFAULT_SEARCH_RADIUS_M` is a tuning knob. Kigali is dense and a rural
district is not, and somebody watching real searches is better placed to pick
the number than whoever wrote the default. It changes here.

`MIN_SERVICE_TIME_SAMPLES` does NOT. It is the honesty rule made executable -
the gate that stops a wait estimate being published from four data points.
A field on an admin form is an invitation to lower it when a facility
complains its waits show as unavailable, and the whole value of the rule is
that it cannot be argued down in the moment. It stays a deploy-time decision,
for the same reason the four TRIAGE_* settings do.

`PRIVACY_NOTICE_VERSION` does not either. It is only meaningful alongside the
notice text it names, which ships with the code. Letting somebody bump the
version without changing the notice would produce consent records pointing at
a revision that never existed.

So this holds one value today. That is not an oversight - it is the list of
things that are safe to change while the system is running.
"""

from django.core.cache import cache
from django.db import models

CACHE_KEY = "platform:settings"
CACHE_SECONDS = 300


class PlatformSettings(models.Model):
    """A single row. `pk=1` always.

    A singleton rather than a key-value table: the values are few, typed
    differently, and each needs its own validation. A generic settings bag
    would turn every read into a string parse and lose that.
    """

    # Metres. The starting radius for a nearby search before the staged
    # expansion takes over.
    default_search_radius_m = models.PositiveIntegerField(default=5000)

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name_plural = "platform settings"

    def __str__(self) -> str:
        return f"Platform settings (radius {self.default_search_radius_m} m)"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(CACHE_KEY)
