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
    lat: float | None = None,
    lng: float | None = None,
    district: str | None = None,
    radius_m: int | None = None,
    insurer: str | None = None,
    service: str | None = None,
    specialty: str | None = None,
    levels: list[str] | None = None,
    open_now: bool = False,
    limit: int = 20,
):
    """Return (facilities, effective_radius_m, radius_was_expanded).

    Each returned Facility carries the annotations `distance`, `is_open`,
    `accepts_insurer` and `tier`.
    """
    # The starting radius is administrable - Kigali is dense and a rural
    # district is not, and somebody watching real searches is better placed to
    # pick the number than whoever wrote the default. Falls back to the
    # deployed setting if the row is unreachable.
    from apps.platform_admin.settings_store import search_radius_m

    radius_m = radius_m or search_radius_m()

    # PostGIS takes x then y: longitude BEFORE latitude. Getting this backwards
    # is silent - every Kigali facility lands in the Indian Ocean and distances
    # look merely "wrong" rather than obviously broken.
    point = Point(lng, lat, srid=4326) if lat is not None and lng is not None else None
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
    elif specialty:
        # The Care Guide recommends a SPECIALTY; the directory understands
        # SERVICES. Translate, and narrow to facilities that offer any of them.
        #
        # A specialty with no mapped services yields an empty list rather than
        # silently widening to every facility - sending a patient anywhere is
        # worse than telling them we found nothing.
        from apps.providers.services import service_codes_for_specialty

        codes = service_codes_for_specialty(specialty)
        # distinct() matters here and not in the `service` branch above: a
        # specialty maps to SEVERAL service codes, so a facility offering more
        # than one of them (paediatrics AND vaccination) joins once per match
        # and appears twice in the results.
        qs = (
            qs.filter(
                services__service_type__code__in=codes, services__available=True
            ).distinct()
            if codes
            else qs.none()
        )
    if district:
        qs = qs.filter(district__iexact=district)
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

    # ---------------------------------------------------------- no origin
    #
    # A district search knows the patient is in Gasabo and nothing more. There
    # is no point to measure from, so there is no radius to expand and no
    # distance to report - `distance` stays unannotated and the serializer
    # sends null. Ordering falls back to the tiering, then level and name.
    #
    # Guessing a district centroid was the alternative and was rejected: it
    # would put a number on the screen that a patient would act on, computed
    # from a location nobody gave us.
    if point is None:
        results = list(qs.order_by("tier", "level", "name")[:limit])
        return results, radius_m, False

    expanded = False
    steps = [s for s in settings.SEARCH_EXPANSION_STEPS_M if s >= radius_m]
    if not steps:
        steps = [min(radius_m, settings.MAX_SEARCH_RADIUS_M)]

    for step in steps:
        # `dwithin`, NOT `distance_lte`. This comment used to claim they were
        # the same thing. They are not:
        #
        #   distance_lte -> ST_Distance(location, point) <= 5000
        #   dwithin      -> ST_DWithin(location, point, 5000)
        #
        # Only the second can use the GIST index. The first computes a real
        # distance for every row in the table and then throws most of them
        # away, which is a sequential scan by another name. With 25 seeded
        # facilities the difference is invisible - which is exactly why it
        # survived - but the target is national coverage.
        #
        # Filter FIRST, annotate distance SECOND, so Distance() is computed
        # only for the rows that survived the index lookup.
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
