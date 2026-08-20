"""Providers, specialties, and the join that connects them to facilities.

The test that matters most is `test_specialty_narrows_the_facility_search`.
That join is what makes the brief's central journey possible - a Care Guide
recommendation of "Paediatrics" has to reach the facility search, which only
understands ServiceType.
"""

from datetime import time

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient

from apps.facilities.models import Facility, FacilityService, OpeningHours, ServiceType
from apps.facilities.services import find_nearby
from apps.providers.models import Provider, ProviderFacility, Specialty
from apps.providers.services import (
    facilities_offering_specialty,
    service_codes_for_specialty,
)

KCC_LAT, KCC_LNG = -1.9536, 30.0606


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def services(db):
    return {
        code: ServiceType.objects.create(
            code=code, name_en=code, name_rw=code, name_fr=code
        )
        for code in ("general_consultation", "paediatrics", "dental")
    }


@pytest.fixture
def paediatrics(db, services):
    specialty = Specialty.objects.create(
        code="paediatrics",
        name_en="Paediatrics",
        name_rw="Ubuvuzi bw'abana",
        name_fr="Pediatrie",
    )
    specialty.service_types.add(services["paediatrics"])
    return specialty


@pytest.fixture
def dentistry(db, services):
    specialty = Specialty.objects.create(
        code="dentistry", name_en="Dentistry", name_rw="Amenyo", name_fr="Dentisterie"
    )
    specialty.service_types.add(services["dental"])
    return specialty


@pytest.fixture
def make_facility(db):
    counter = {"n": 0}

    def _make(*, name=None, offers=(), verified=True, lat=KCC_LAT, lng=KCC_LNG):
        counter["n"] += 1
        facility = Facility.objects.create(
            name=name or f"Facility {counter['n']}",
            slug=f"facility-{counter['n']}",
            ownership="public",
            level="health_centre",
            district="Gasabo",
            location=Point(lng, lat, srid=4326),
            verified_at=timezone.now() if verified else None,
        )
        for weekday in range(7):
            OpeningHours.objects.create(
                facility=facility,
                weekday=weekday,
                opens_at=time(0, 0),
                closes_at=time(23, 59),
            )
        for service in offers:
            FacilityService.objects.create(
                facility=facility, service_type=service, available=True
            )
        return facility

    return _make


@pytest.fixture
def make_provider(db):
    counter = {"n": 0}

    def _make(*, name=None, specialties=(), facility=None, services=(), active=True):
        counter["n"] += 1
        provider = Provider.objects.create(
            slug=f"provider-{counter['n']}",
            full_name=name or f"Doctor {counter['n']}",
            active=active,
            languages=["rw", "en"],
        )
        provider.specialties.set(specialties)
        if facility is not None:
            placement = ProviderFacility.objects.create(
                provider=provider, facility=facility, active=active
            )
            placement.service_types.set(services)
        return provider

    return _make


# --------------------------------------------------------------------------
# Specialty -> service -> facility: the join the whole journey rests on
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_specialty_resolves_to_facility_services(paediatrics):
    assert service_codes_for_specialty("paediatrics") == ["paediatrics"]


@pytest.mark.django_db
def test_an_unknown_specialty_resolves_to_nothing(db):
    assert service_codes_for_specialty("astrology") == []


@pytest.mark.django_db
def test_specialty_narrows_the_facility_search(
    paediatrics, services, make_facility
):
    """A Care Guide recommendation must reach real facilities."""
    with_paeds = make_facility(name="Has paediatrics", offers=[services["paediatrics"]])
    make_facility(name="General only", offers=[services["general_consultation"]])

    results, _, _ = find_nearby(
        lat=KCC_LAT, lng=KCC_LNG, radius_m=10000, specialty="paediatrics"
    )

    assert [f.id for f in results] == [with_paeds.id]


@pytest.mark.django_db
def test_an_unmapped_specialty_returns_nothing_not_everything(
    db, services, make_facility
):
    """Silently widening to every facility would send a patient anywhere.
    Returning nothing is the honest failure."""
    Specialty.objects.create(
        code="unmapped", name_en="Unmapped", name_rw="x", name_fr="x"
    )
    make_facility(offers=[services["general_consultation"]])

    results, _, _ = find_nearby(
        lat=KCC_LAT, lng=KCC_LNG, radius_m=10000, specialty="unmapped"
    )

    assert results == []


@pytest.mark.django_db
def test_an_explicit_service_choice_beats_an_inferred_specialty(
    paediatrics, services, make_facility
):
    """The patient picking a service always wins over a recommendation."""
    dental_only = make_facility(offers=[services["dental"]])
    make_facility(offers=[services["paediatrics"]])

    results, _, _ = find_nearby(
        lat=KCC_LAT,
        lng=KCC_LNG,
        radius_m=10000,
        service="dental",
        specialty="paediatrics",
    )

    assert [f.id for f in results] == [dental_only.id]


@pytest.mark.django_db
def test_unverified_facilities_never_surface_via_specialty(
    paediatrics, services, make_facility
):
    make_facility(offers=[services["paediatrics"]], verified=False)

    assert facilities_offering_specialty("paediatrics").count() == 0


# --------------------------------------------------------------------------
# Doctors directory
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_doctor_with_no_placement_is_not_listed(
    api_client, paediatrics, make_provider
):
    """A clinician who practises nowhere cannot be booked. Listing them sends
    a patient looking for an appointment that does not exist."""
    make_provider(name="Nowhere", specialties=[paediatrics])

    assert api_client.get("/api/v1/providers").json()["count"] == 0


@pytest.mark.django_db
def test_directory_filters_by_specialty(
    api_client, paediatrics, dentistry, services, make_facility, make_provider
):
    facility = make_facility(offers=[services["paediatrics"], services["dental"]])
    make_provider(
        name="Uwase Alice",
        specialties=[paediatrics],
        facility=facility,
        services=[services["paediatrics"]],
    )
    make_provider(
        name="Mugisha Jean",
        specialties=[dentistry],
        facility=facility,
        services=[services["dental"]],
    )

    body = api_client.get("/api/v1/providers?specialty=paediatrics").json()

    assert body["count"] == 1
    assert body["results"][0]["full_name"] == "Uwase Alice"


@pytest.mark.django_db
def test_directory_filters_by_facility_and_service(
    api_client, paediatrics, services, make_facility, make_provider
):
    here = make_facility(offers=[services["paediatrics"]])
    elsewhere = make_facility(offers=[services["paediatrics"]])
    make_provider(
        name="Here", specialties=[paediatrics], facility=here,
        services=[services["paediatrics"]],
    )
    make_provider(
        name="Elsewhere", specialties=[paediatrics], facility=elsewhere,
        services=[services["paediatrics"]],
    )

    body = api_client.get(f"/api/v1/facilities/{here.slug}/providers").json()

    assert [r["full_name"] for r in body["results"]] == ["Here"]


@pytest.mark.django_db
def test_inactive_doctors_are_hidden(
    api_client, paediatrics, services, make_facility, make_provider
):
    facility = make_facility(offers=[services["paediatrics"]])
    make_provider(
        name="Retired", specialties=[paediatrics], facility=facility,
        services=[services["paediatrics"]], active=False,
    )

    assert api_client.get("/api/v1/providers").json()["count"] == 0


@pytest.mark.django_db
def test_language_filter(
    api_client, paediatrics, services, make_facility, make_provider
):
    facility = make_facility(offers=[services["paediatrics"]])
    provider = make_provider(
        specialties=[paediatrics], facility=facility,
        services=[services["paediatrics"]],
    )
    provider.languages = ["rw", "fr"]
    provider.save()

    assert api_client.get("/api/v1/providers?language=fr").json()["count"] == 1
    assert api_client.get("/api/v1/providers?language=sw").json()["count"] == 0


@pytest.mark.django_db
def test_count_reflects_the_filter_not_the_page(
    api_client, paediatrics, services, make_facility, make_provider
):
    """A client needs to know a filter matched more than it is being shown."""
    facility = make_facility(offers=[services["paediatrics"]])
    for _ in range(5):
        make_provider(
            specialties=[paediatrics], facility=facility,
            services=[services["paediatrics"]],
        )

    body = api_client.get("/api/v1/providers?limit=2").json()

    assert body["count"] == 5
    assert len(body["results"]) == 2


# --------------------------------------------------------------------------
# Profile shape
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_initials_are_always_available_as_an_avatar_fallback(db):
    """A doctor card must never render blank because there is no photo."""
    assert Provider(full_name="Uwase Alice").initials == "UA"
    assert Provider(full_name="Jean").initials == "J"
    assert Provider(full_name="").initials == "?"


@pytest.mark.django_db
def test_display_name_carries_the_title(db):
    assert Provider(full_name="Uwase Alice", title="dr").display_name == "Dr Uwase Alice"
    assert Provider(full_name="Uwase Alice", title="").display_name == "Uwase Alice"


@pytest.mark.django_db
def test_profile_reports_verification_honestly(
    api_client, paediatrics, services, make_facility, make_provider
):
    facility = make_facility(offers=[services["paediatrics"]])
    provider = make_provider(
        specialties=[paediatrics], facility=facility,
        services=[services["paediatrics"]],
    )

    body = api_client.get(f"/api/v1/providers/{provider.slug}").json()
    assert body["verified"] is False

    provider.verified_at = timezone.now()
    provider.save()

    body = api_client.get(f"/api/v1/providers/{provider.slug}").json()
    assert body["verified"] is True


@pytest.mark.django_db
def test_a_doctor_practising_at_two_facilities_lists_both(
    api_client, paediatrics, services, make_facility, make_provider
):
    """Clinicians commonly hold a public post and consult privately. A single
    FK would hide one of them from search."""
    first = make_facility(name="Public hospital", offers=[services["paediatrics"]])
    second = make_facility(name="Private clinic", offers=[services["paediatrics"]])

    provider = make_provider(
        specialties=[paediatrics], facility=first, services=[services["paediatrics"]]
    )
    placement = ProviderFacility.objects.create(provider=provider, facility=second)
    placement.service_types.set([services["paediatrics"]])

    body = api_client.get(f"/api/v1/providers/{provider.slug}").json()

    assert {p["facility_name"] for p in body["placements"]} == {
        "Public hospital",
        "Private clinic",
    }


@pytest.mark.django_db
def test_specialties_endpoint_exposes_the_service_mapping(api_client, paediatrics):
    body = api_client.get("/api/v1/specialties").json()

    entry = next(s for s in body["results"] if s["code"] == "paediatrics")
    assert entry["service_types"] == ["paediatrics"]
    assert entry["name_rw"]


@pytest.mark.django_db
def test_directory_query_count_is_bounded(
    api_client, paediatrics, services, make_facility, make_provider,
    django_assert_max_num_queries,
):
    """Guards against a serializer loop turning 20 doctors into 60 queries."""
    facility = make_facility(offers=[services["paediatrics"]])
    for _ in range(20):
        make_provider(
            specialties=[paediatrics], facility=facility,
            services=[services["paediatrics"]],
        )

    with django_assert_max_num_queries(6):
        api_client.get("/api/v1/providers")
