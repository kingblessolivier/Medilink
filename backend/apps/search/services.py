"""One search box over four kinds of thing.

A patient typing "pediatric" does not know whether that is a service, a
specialty, a doctor or a hospital, and should not have to. The results come
back grouped, in the order that gets somebody to care fastest:

    specialty  ->  leads to many facilities and many doctors
    service    ->  leads to many facilities
    provider   ->  leads to one doctor at one or more facilities
    facility   ->  leads to one place

Specialties and services rank above named results deliberately. Somebody who
types "dental" almost always wants dentistry near them, not the one dentist
whose name happens to contain those letters.
"""

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.db.models import Q

from apps.facilities.models import Facility, ServiceType
from apps.providers.models import Specialty

# Below this, a query matches almost everything and the results are noise.
MIN_QUERY_LENGTH = 2
PER_GROUP = 5


def _facilities(term: str, point: Point | None, limit: int):
    queryset = Facility.objects.filter(verified_at__isnull=False).filter(
        Q(name__icontains=term)
        | Q(district__icontains=term)
        | Q(sector__icontains=term)
    )
    if point is not None:
        # Nearest first when we know where the patient is - a hospital 30 km
        # away is rarely the answer, however well its name matches.
        queryset = queryset.annotate(distance=Distance("location", point)).order_by(
            "distance"
        )
    return queryset[:limit]


def _providers(term: str, limit: int):
    from apps.providers.services import providers_queryset

    return providers_queryset(search=term)[:limit]


def search(*, term: str, lat: float | None = None, lng: float | None = None):
    """Grouped results. Empty groups are omitted rather than shown empty."""
    term = (term or "").strip()
    if len(term) < MIN_QUERY_LENGTH:
        return {"query": term, "groups": []}

    point = Point(lng, lat, srid=4326) if lat is not None and lng is not None else None

    specialties = Specialty.objects.filter(
        Q(name_en__icontains=term)
        | Q(name_rw__icontains=term)
        | Q(name_fr__icontains=term)
        | Q(code__icontains=term)
    ).prefetch_related("service_types")[:PER_GROUP]

    services = ServiceType.objects.filter(
        Q(name_en__icontains=term)
        | Q(name_rw__icontains=term)
        | Q(name_fr__icontains=term)
        | Q(code__icontains=term)
    )[:PER_GROUP]

    groups = []

    if specialties:
        groups.append(
            {
                "kind": "specialty",
                "results": [
                    {
                        "code": s.code,
                        "label": s.name_en,
                        "label_rw": s.name_rw,
                        "label_fr": s.name_fr,
                        # What the client should navigate to. A specialty is
                        # only useful if it reaches facilities.
                        "href": f"/search?specialty={s.code}",
                        "routable": s.service_types.exists(),
                    }
                    for s in specialties
                ],
            }
        )

    if services:
        groups.append(
            {
                "kind": "service",
                "results": [
                    {
                        "code": s.code,
                        "label": s.name_en,
                        "label_rw": s.name_rw,
                        "label_fr": s.name_fr,
                        "href": f"/search?service={s.code}",
                        "routable": True,
                    }
                    for s in services
                ],
            }
        )

    providers = list(_providers(term, PER_GROUP))
    if providers:
        groups.append(
            {
                "kind": "provider",
                "results": [
                    {
                        "code": p.slug,
                        "label": p.display_name,
                        "sublabel": ", ".join(s.name_en for s in p.specialties.all()),
                        "href": f"/doctor/{p.slug}",
                        "routable": True,
                    }
                    for p in providers
                ],
            }
        )

    facilities = list(_facilities(term, point, PER_GROUP))
    if facilities:
        groups.append(
            {
                "kind": "facility",
                "results": [
                    {
                        "code": f.slug,
                        "label": f.name,
                        "sublabel": f.district,
                        "distance_m": (
                            round(f.distance.m) if hasattr(f, "distance") else None
                        ),
                        "href": f"/facility/{f.slug}",
                        "routable": True,
                    }
                    for f in facilities
                ],
            }
        )

    return {"query": term, "groups": groups}
