"""Provider and specialty queries.

The function that matters here is `facility_ids_for_specialty`. It is the join
that makes the brief's central journey possible:

    specialty -> service types -> facilities offering them -> geo search

Without it, an AI recommendation of "Pediatrics" has nowhere to go, because the
facility search only understands ServiceType.
"""

from django.db.models import Prefetch, Q

from apps.facilities.models import Facility

from .models import Provider, ProviderFacility, Specialty


def service_codes_for_specialty(specialty_code: str) -> list[str]:
    """The facility services a clinician in this specialty delivers."""
    specialty = Specialty.objects.filter(code=specialty_code).first()
    if specialty is None:
        return []
    return list(specialty.service_types.values_list("code", flat=True))


def facilities_offering_specialty(specialty_code: str):
    """Verified facilities that offer any service mapped to this specialty.

    Used to narrow `/facilities/nearby` after a Care Guide recommendation. A
    specialty with no mapped services returns nothing rather than everything -
    silently widening to every facility would send a patient anywhere.
    """
    codes = service_codes_for_specialty(specialty_code)
    if not codes:
        return Facility.objects.none()

    return Facility.objects.filter(
        verified_at__isnull=False,
        services__service_type__code__in=codes,
        services__available=True,
    ).distinct()


def providers_queryset(
    *,
    specialty: str | None = None,
    facility_slug: str | None = None,
    service: str | None = None,
    language: str | None = None,
    search: str | None = None,
):
    """Active, verified providers, narrowed by the directory filters.

    Only providers with at least one active placement are returned: a
    clinician who practises nowhere cannot be booked, and listing them would
    send a patient looking for an appointment that does not exist.
    """
    placements = ProviderFacility.objects.filter(
        active=True, facility__verified_at__isnull=False
    ).select_related("facility")

    if facility_slug:
        placements = placements.filter(facility__slug=facility_slug)
    if service:
        placements = placements.filter(service_types__code=service)

    queryset = (
        Provider.objects.filter(active=True, placements__in=placements)
        .distinct()
        .prefetch_related(
            "specialties",
            Prefetch(
                "placements",
                queryset=placements.prefetch_related("service_types"),
                to_attr="visible_placements",
            ),
        )
    )

    if specialty:
        queryset = queryset.filter(specialties__code=specialty)
    if language:
        queryset = queryset.filter(languages__contains=[language])
    if search:
        queryset = queryset.filter(
            Q(full_name__icontains=search) | Q(specialties__name_en__icontains=search)
        ).distinct()

    return queryset
