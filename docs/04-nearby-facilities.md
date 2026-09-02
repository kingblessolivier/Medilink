# 04 - Nearby Facilities (Geo Search)

This is the feature a patient meets first, and the only one that works with zero
hospital partnerships on day one. It must be excellent.

## 1. The user need

A patient in Kimironko with Mutuelle cover and a sick child opens MediLink. They
need, in one screen and under three seconds:

> **Which health facilities near me are open now, accept my insurance, and how
> long is the wait?**

Everything in this document serves that sentence.

## 2. Ranking - distance is not enough

Sorting purely by distance produces a bad list: the closest facility may be
closed, may not take the patient's insurance, or may be a pharmacy when they need
a doctor. Sort in **tiers**, and within a tier by distance:

| Tier | Contents |
|---|---|
| 1 | Open now + accepts insurer + offers requested service |
| 2 | Open now + accepts insurer |
| 3 | Open now, insurance unknown or not accepted |
| 4 | Closed now (shown last, with opening time) |

Implement the tier as an annotated integer and sort `(tier, distance_m)`. Never
hide tier 3 and 4 results entirely - a patient in an emergency needs to know a
facility exists even if it will cost them cash.

**Do not rank by wait time.** It is tempting and it is wrong: only a minority of
facilities report queue data in early phases, so ranking by wait would push every
non-reporting facility to the bottom regardless of how close or suitable it is.
Wait time is displayed, not ranked on.

## 3. The PostGIS query

```python
# backend/apps/facilities/services.py
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Q, Value, IntegerField, Case, When, Exists, OuterRef
from django.utils import timezone

from .models import Facility, OpeningHours

RWANDA_BOUNDS = {"lat": (-2.92, -1.02), "lng": (28.80, 30.95)}
DEFAULT_RADIUS_M = 5_000
MAX_RADIUS_M = 50_000
EXPANSION_STEPS_M = (5_000, 10_000, 25_000, 50_000)
MIN_RESULTS_BEFORE_EXPANDING = 3


def find_nearby(*, lat, lng, radius_m=DEFAULT_RADIUS_M, insurer=None,
                service=None, levels=None, open_now=False, limit=20):
    """Ranked nearby facilities. Returns (results, effective_radius, expanded)."""
    point = Point(lng, lat, srid=4326)          # NOTE: Point takes (x=lng, y=lat)
    now = timezone.localtime()
    weekday = now.weekday()                     # 0 = Monday

    open_subquery = OpeningHours.objects.filter(
        facility_id=OuterRef("pk"),
        weekday=weekday,
        opens_at__lte=now.time(),
        closes_at__gte=now.time(),
    )

    base = (
        Facility.objects
        .filter(verified_at__isnull=False)
        .annotate(is_open=Exists(open_subquery))
        .prefetch_related("insurers__insurer", "services__service_type",
                          "opening_hours")
    )

    if insurer:
        base = base.annotate(
            accepts_insurer=Exists(
                FacilityInsurer.objects.filter(
                    facility_id=OuterRef("pk"), insurer__code=insurer
                )
            )
        )
    else:
        base = base.annotate(accepts_insurer=Value(True, IntegerField()))

    if service:
        base = base.filter(services__service_type__code=service,
                           services__available=True)
    if levels:
        base = base.filter(level__in=levels)
    if open_now:
        base = base.filter(is_open=True)

    # Tiering
    base = base.annotate(
        tier=Case(
            When(is_open=True, accepts_insurer=True, then=Value(1)),
            When(is_open=True, accepts_insurer=False, then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        )
    )

    expanded = False
    for step in EXPANSION_STEPS_M:
        if step < radius_m:
            continue
        qs = (base
              .filter(location__distance_lte=(point, D(m=step)))
              .annotate(distance=Distance("location", point))
              .order_by("tier", "distance")[:limit])
        results = list(qs)
        if len(results) >= MIN_RESULTS_BEFORE_EXPANDING or step >= MAX_RADIUS_M:
            return results, step, expanded
        expanded = True

    return [], MAX_RADIUS_M, expanded
```

### 3.1 Three details that are easy to get wrong

**`Point(lng, lat)`, not `Point(lat, lng).`** PostGIS takes x then y - longitude
before latitude. This bug is silent: coordinates that look plausible put every
Kigali facility in the Indian Ocean. Write a test that asserts a known distance.

**Use `geography=True` on the field.** With `geography`, `distance_lte` and
`Distance` return true metres over the ellipsoid. With `geometry` in SRID 4326
they return *degrees*, and a "5000" radius silently means the whole planet.

**`distance_lte` compiles to `ST_DWithin`**, which uses the GIST index. Filtering
with `.annotate(distance=...).filter(distance__lte=...)` instead does **not** use
the index and will sequentially scan the table. Always filter first, annotate
second.

## 4. Attaching wait times

Never do this per facility in a loop - it is an N+1 query on the hottest endpoint
in the system. Fetch one aggregate for all result IDs:

```python
# backend/apps/queueing/services.py
from django.db.models import Count
from .models import QueueEntry, ServiceTimeStat

MIN_SAMPLE_SIZE = 20


def wait_snapshot(facility_ids, service_code=None, now=None):
    """{facility_id: {"status": ..., "minutes": ..., "people_waiting": ...}}"""
    now = now or timezone.localtime()

    counts = dict(
        QueueEntry.objects
        .filter(facility_id__in=facility_ids, status=QueueEntry.Status.WAITING)
        .values_list("facility_id")
        .annotate(n=Count("id"))
    )

    stats = {
        (s.facility_id, s.service_type_id): s
        for s in ServiceTimeStat.objects.filter(
            facility_id__in=facility_ids, hour_of_day=now.hour
        )
    }

    out = {}
    for fid in facility_ids:
        facility = facility_map[fid]
        if not facility.reports_queue:
            out[fid] = {"status": "not_reported", "minutes": None}
            continue
        if not facility.is_open:
            out[fid] = {"status": "closed", "minutes": None}
            continue

        stat = stats.get((fid, service_id))
        if stat is None or stat.sample_size < MIN_SAMPLE_SIZE:
            out[fid] = {"status": "insufficient_data", "minutes": None,
                        "people_waiting": counts.get(fid, 0)}
            continue

        waiting = counts.get(fid, 0)
        out[fid] = {
            "status": "available",
            "minutes": round(waiting * stat.median_minutes),
            "people_waiting": waiting,
            "as_of": now.isoformat(),
        }
    return out
```

**The `MIN_SAMPLE_SIZE` gate is the honesty rule made executable.** A facility
that joined yesterday reports `insufficient_data`, not a confident-looking number
derived from four data points.

Cache `wait_snapshot` in Redis for **30 seconds**, keyed by facility ID set. The
nearby endpoint is read enormously and a queue does not change meaningfully
within 30 seconds.

## 5. Edge cases - and there are many

| Situation | Behaviour |
|---|---|
| Browser denies geolocation | Fall back to a district picker: "Choose your district". Never a blank screen. |
| GPS returns a point outside Rwanda | Reject with `400`, prompt for district. Common on desktop and with VPNs. |
| GPS accuracy worse than 1000 m | Still search, but show "Approximate location - tap to correct". |
| Fewer than 3 results in radius | Auto-expand 5 -> 10 -> 25 -> 50 km. Tell the user: "No facilities within 5 km. Showing results within 10 km." |
| Zero results at 50 km | Show the nearest facility regardless of distance, plus the emergency number. |
| Patient has no insurer set | Do not filter. Show all, with each facility's insurer list, and a prompt to set cover. |
| Facility is open but closes in under 30 min | Badge: "Closing soon - 17:00". A patient must not travel to a door that shuts on arrival. |
| Offline | Serve the last cached result with a banner and the cache timestamp. |
| Two facilities at the same distance | Break ties by `level` (hospital above health post), then name, so ordering is stable between refreshes. |

## 6. The API layer

```python
# backend/apps/facilities/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def nearby(request):
    params = NearbyQuerySerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    v = params.validated_data

    facilities, effective_radius, expanded = find_nearby(
        lat=v["lat"], lng=v["lng"], radius_m=v["radius"],
        insurer=v.get("insurer"), service=v.get("service"),
        levels=v.get("level"), open_now=v["open_now"], limit=v["limit"],
    )

    waits = wait_snapshot([f.id for f in facilities], v.get("service"))

    return Response({
        "as_of": timezone.localtime().isoformat(),
        "query": {**v, "radius": effective_radius, "radius_expanded": expanded},
        "count": len(facilities),
        "results": FacilityNearbySerializer(
            facilities, many=True, context={"waits": waits}
        ).data,
    })
```

Validation is where the Rwanda bounds check belongs:

```python
class NearbyQuerySerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-2.92, max_value=-1.02)
    lng = serializers.FloatField(min_value=28.80, max_value=30.95)
    radius = serializers.IntegerField(default=5000, min_value=100, max_value=50000)
    insurer = serializers.SlugField(required=False)
    service = serializers.SlugField(required=False)
    level = serializers.ListField(child=serializers.SlugField(), required=False)
    open_now = serializers.BooleanField(default=False)
    limit = serializers.IntegerField(default=20, min_value=1, max_value=50)
```

## 7. The React implementation

### 7.1 Getting location

```ts
// web/src/hooks/useGeolocation.ts
type GeoState =
  | { status: "idle" }
  | { status: "locating" }
  | { status: "ready"; lat: number; lng: number; accuracy: number }
  | { status: "denied" }
  | { status: "unavailable" }
  | { status: "out_of_bounds" }

const RW = { lat: [-2.92, -1.02], lng: [28.80, 30.95] }

export function useGeolocation() {
  const [state, setState] = useState<GeoState>({ status: "idle" })

  const locate = useCallback(() => {
    if (!("geolocation" in navigator)) {
      setState({ status: "unavailable" })
      return
    }
    setState({ status: "locating" })
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const { latitude: lat, longitude: lng, accuracy } = coords
        const inRW =
          lat >= RW.lat[0] && lat <= RW.lat[1] &&
          lng >= RW.lng[0] && lng <= RW.lng[1]
        setState(inRW
          ? { status: "ready", lat, lng, accuracy }
          : { status: "out_of_bounds" })
      },
      (err) => setState({
        status: err.code === err.PERMISSION_DENIED ? "denied" : "unavailable",
      }),
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 120_000 },
    )
  }, [])

  return { state, locate }
}
```

`maximumAge: 120_000` accepts a two-minute-old fix. On a low-end Android phone,
demanding a fresh high-accuracy fix every time costs battery and several seconds
for no benefit - the patient has not moved far.

### 7.2 Fetching

```ts
// web/src/hooks/useNearbyFacilities.ts
export function useNearbyFacilities(
  coords: { lat: number; lng: number } | null,
  filters: { insurer?: string; service?: string; openNow?: boolean },
) {
  return useQuery({
    queryKey: ["nearby", coords, filters],
    queryFn: () => api.getNearby({ ...coords!, ...filters }),
    enabled: coords !== null,
    staleTime: 60_000,          // a facility list does not change minute to minute
    gcTime: 24 * 60 * 60_000,   // keep for offline fallback
    retry: 2,
  })
}
```

### 7.3 The facility card

```tsx
// web/src/components/FacilityCard.tsx
export function FacilityCard({ facility }: { facility: Facility }) {
  const { t } = useTranslation()
  return (
    <article className="rounded-xl border p-4 mb-3">
      <header className="flex justify-between gap-2">
        <h3 className="font-semibold leading-tight">{facility.name}</h3>
        <span className="text-sm text-neutral-500 shrink-0">
          {formatDistance(facility.distance_m)}
        </span>
      </header>

      <OpenBadge facility={facility} />

      {facility.accepts_insurer && (
        <p className="text-sm text-green-700 mt-1">
          {t("accepts", { insurer: facility.matched_insurer_name })}
        </p>
      )}

      <WaitLine wait={facility.wait} />

      <div className="flex gap-2 mt-3">
        <a href={directionsUrl(facility)} className="btn-secondary">
          {t("directions")}
        </a>
        {facility.bookable && (
          <Link to={`/facility/${facility.slug}/book`} className="btn-primary">
            {t("book")}
          </Link>
        )}
      </div>
    </article>
  )
}
```

The wait line is where the honesty rule reaches the screen:

```tsx
function WaitLine({ wait }: { wait: Wait }) {
  const { t } = useTranslation()
  switch (wait.status) {
    case "available":
      return <p className="text-sm mt-1">
        {t("wait_about", { minutes: roundTo5(wait.minutes) })}
        <span className="text-neutral-400 ml-1">
          · {t("updated_ago", { ago: timeAgo(wait.as_of) })}
        </span>
      </p>
    case "closed":
      return <p className="text-sm mt-1 text-neutral-500">{t("closed")}</p>
    case "not_reported":
    case "insufficient_data":
      return <p className="text-sm mt-1 text-neutral-500">
        {t("wait_unavailable")}
      </p>
  }
}
```

`roundTo5` matters. Rendering "43 minutes" claims a precision we do not have;
"about 45 min" is honest and reads as an estimate.

### 7.4 Distance formatting

```ts
export function formatDistance(m: number): string {
  if (m < 100) return "nearby"
  if (m < 1000) return `${Math.round(m / 50) * 50} m`
  return `${(m / 1000).toFixed(1)} km`
}
```

## 8. Map or list?

**Ship the list first. Add the map in Phase 2.**

A list is faster to build, faster to load on 3G, works with a screen reader,
works on a small screen, and is what a patient actually needs - they want to pick
a facility, not explore a map. A map is a large JavaScript payload, tile requests
on a metered connection, and a significant accessibility problem.

When the map does arrive: use **MapLibre GL** with a free tile source (never a
key-metered commercial API on this budget), lazy-load it behind a "Show map"
toggle so it costs nothing to patients who do not open it, and keep the list as
the default view.

For directions, do not build routing. Link out:

```ts
const directionsUrl = (f: Facility) =>
  `https://www.google.com/maps/dir/?api=1&destination=${f.location.lat},${f.location.lng}`
```

Every Android phone already has a maps app that does this better than we will.

## 9. USSD version

The same feature, on a feature phone. Aim for three steps.

```
CON MediLink - Ahantu hafi
1. Gasabo
2. Kicukiro
3. Nyarugenge
0. Ahandi

  -> CON Hitamo serivisi
     1. Kwivuza (general)
     2. Kubyara (maternity)
     3. Amenyo (dental)

     -> END Hafi yawe:
        1. Kimironko HC - 1.2km - Mutuelle - iminota 40
        2. Remera PC - 2.8km - Mutuelle
        3. Kacyiru HC - 3.4km - Mutuelle - iminota 25
```

Constraints that shape this: no GPS on a feature phone, so **district and sector
replace coordinates**; roughly 160 characters per screen, so **three results
maximum**; and no scrolling, so the most useful result must be first.

Store the patient's district on their `Patient` row after the first USSD session,
so returning users skip step one entirely.

## 10. Performance targets and how to hit them

| Metric | Target |
|---|---|
| `GET /facilities/nearby` p50 | < 150 ms |
| `GET /facilities/nearby` p95 | < 400 ms |
| Payload, 20 results, gzipped | < 12 KB |
| Time to first card on 3G | < 3 s |

To hold these:

1. **GIST index on `location`** - without it nothing else matters.
2. **`prefetch_related`** for insurers, services and opening hours. Without it,
   20 results become 60 extra queries.
3. **Redis-cache `wait_snapshot`** for 30 s.
4. **Cache `/insurers` and `/service-types`** in the client for 24 h. They change
   perhaps twice a year.
5. **`Cache-Control: public, max-age=60`** on nearby responses when no `insurer`
   is supplied, so the anonymous first load can be served from a CDN edge.

## 11. Verification checklist before this feature ships

- [x] `Point(lng, lat)` ordering asserted by a test against a known distance
- [x] `EXPLAIN ANALYZE` on the nearby query confirms an **Index Scan**, not a
      Seq Scan - it did NOT, until 2026-08-23. `distance_lte` compiles to
      `ST_Distance(...) <= x`, which cannot use the GIST index; `dwithin`
      compiles to `ST_DWithin(...)`, which can. Measured on 20,000 rows:
      **215 ms sequential versus 0.2 ms indexed.** Two tests now assert on the
      emitted SQL, because at 25 seeded facilities the difference is invisible
- [x] Query count per request asserted (`assertNumQueries`) to catch N+1 regressions
- [x] All four `wait.status` values render correctly in the UI
- [x] Denied-geolocation path reaches the district picker
- [x] Radius auto-expansion tested with a deliberately empty rural coordinate
- [x] Out-of-bounds coordinate returns `400`, not a crash
- [x] Offline mode shows cached results with a visible timestamp - the banner
      says the connection is gone, and `CachedNotice` sits with the results
      themselves saying how old they are. A banner at the top of the page
      cannot say how old the card three screens down is.
- [ ] Tested on a real low-end Android phone on a real 3G connection, not on the emulator
- [ ] At least 50 real Kigali facilities loaded and field-verified
