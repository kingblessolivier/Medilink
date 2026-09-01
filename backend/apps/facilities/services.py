"""Nearby-facility search.

See docs/04-nearby-facilities.md for the design rationale behind the tiering,
the radius expansion, and the three silent bugs guarded against here.
"""

from django.conf import settings
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import (
    BooleanField,
    Case,
    Exists,
    IntegerField,
    OuterRef,
    Prefetch,
    Value,
    When,
)
from django.utils import timezone

from apps.insurance.models import FacilityInsurer

from .models import Facility, FacilityService, OpeningHours

# Ranking tiers. Sorted by (tier, distance) so that a closed facility never
# outranks an open one just because it happens to be nearer.
TIER_OPEN_INSURED_SERVICE = 1
TIER_OPEN_INSURED = 2
TIER_OPEN = 3
TIER_CLOSED = 4


def _open_now_subquery(now):
    return OpeningHours.objects.filter(
        facility_id=OuterRef("pk"),
        weekday=now.weekday(),
        opens_at__lte=now.time(),
        closes_at__gte=now.time(),
    )


def find_nearby(
    *,
    lat: float,
    lng: float,
    radius_m: int | None = None,
    insurer: str | None = None,
    service: str | None = None,
    levels: list[str] | None = None,
    open_now: bool = False,
    limit: int = 20,
):
    """Return (facilities, effective_radius_m, radius_was_expanded).

    Each returned Facility carries the annotations `distance`, `is_open`,
    `accepts_insurer` and `tier`.
    """
    radius_m = radius_m or settings.DEFAULT_SEARCH_RADIUS_M

    # PostGIS takes x then y: longitude BEFORE latitude. Getting this backwards
    # is silent - every Kigali facility lands in the Indian Ocean and distances
    # look merely "wrong" rather than obviously broken.
    point = Point(lng, lat, srid=4326)
    now = timezone.localtime()

    qs = (
        Facility.objects.filter(verified_at__isnull=False)
        .annotate(is_open=Exists(_open_now_subquery(now)))
        # select_related inside each Prefetch collapses what would otherwise be
        # two queries per relation into one: 4 queries total rather than 6.
        .prefetch_related(
            Prefetch(
                "insurers",
                queryset=FacilityInsurer.objects.select_related("insurer"),
            ),
            Prefetch(
                "services",
                queryset=FacilityService.objects.select_related("service_type"),
            ),
            "opening_hours",
        )
    )

    if insurer:
        qs = qs.annotate(
            accepts_insurer=Exists(
                FacilityInsurer.objects.filter(
                    facility_id=OuterRef("pk"), insurer__code=insurer
                )
            )
        )
    else:
        # No filter requested: treat every facility as acceptable so that the
        # tiering below still works without a second code path.
        qs = qs.annotate(accepts_insurer=Value(True, output_field=BooleanField()))

    if service:
        qs = qs.filter(
            services__service_type__code=service, services__available=True
        )
    if levels:
        qs = qs.filter(level__in=levels)
    if open_now:
        qs = qs.filter(is_open=True)

    has_service = bool(service)
    qs = qs.annotate(
        tier=Case(
            When(
                is_open=True,
                accepts_insurer=True,
                then=Value(
                    TIER_OPEN_INSURED_SERVICE if has_service else TIER_OPEN_INSURED
                ),
            ),
            When(is_open=True, accepts_insurer=False, then=Value(TIER_OPEN)),
            default=Value(TIER_CLOSED),
            output_field=IntegerField(),
        )
    )

    expanded = False
    steps = [s for s in settings.SEARCH_EXPANSION_STEPS_M if s >= radius_m]
    if not steps:
        steps = [min(radius_m, settings.MAX_SEARCH_RADIUS_M)]

    for step in steps:
        # Filter FIRST, annotate distance SECOND, and filter with `dwithin`.
        #
        # The lookup matters as much as the ordering. `dwithin` compiles to
        # ST_DWithin, which the GIST index answers. `distance_lte` looks
        # equivalent and returns the same rows, but on a geography column it
        # compiles to `ST_Distance(...) <= n` - a spheroid distance computed
        # for every row in the table, and a sequential scan every time.
        # Filtering on an annotated Distance() has the same effect.
        #
        # test_definition_of_done.py asserts the plan, because the difference
        # is invisible in the response: same results, 100x the cost.
        results = list(
            qs.filter(location__dwithin=(point, D(m=step)))
            .annotate(distance=Distance("location", point))
            # level and name break distance ties so ordering is stable
            # between refreshes.
            .order_by("tier", "distance", "level", "name")[:limit]
        )
        enough = len(results) >= settings.MIN_RESULTS_BEFORE_EXPANDING
        if enough or step >= settings.MAX_SEARCH_RADIUS_M:
            if results:
                return results, step, expanded
            break
        expanded = True

    # Nothing even at the maximum radius. Rather than an empty screen, return
    # the single nearest facility at any distance - a patient in a rural area
    # needs to know where the nearest care is, even if it is 80 km away.
    # The client shows the distance prominently and adds emergency guidance.
    nearest = list(
        qs.annotate(distance=Distance("location", point)).order_by("distance")[:1]
    )
    return nearest, settings.MAX_SEARCH_RADIUS_M, True


def is_open_now(facility, now=None) -> bool:
    """Used on the detail endpoint, where there is no queryset annotation."""
    now = now or timezone.localtime()
    return any(
        oh.weekday == now.weekday() and oh.opens_at <= now.time() <= oh.closes_at
        for oh in facility.opening_hours.all()
    )


def closes_at(facility, now=None):
    """Closing time of the period currently in progress, or None if closed."""
    now = now or timezone.localtime()
    for oh in facility.opening_hours.all():
        if oh.weekday == now.weekday() and oh.opens_at <= now.time() <= oh.closes_at:
            return oh.closes_at
    return None


def opens_next(facility, now=None):
    """Next opening time today, or None. Drives the 'Closed - opens 07:00' copy."""
    now = now or timezone.localtime()
    upcoming = [
        oh.opens_at
        for oh in facility.opening_hours.all()
        if oh.weekday == now.weekday() and oh.opens_at > now.time()
    ]
    return min(upcoming) if upcoming else None
