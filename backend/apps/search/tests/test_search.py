"""Global search.

The property that matters: somebody who types a word gets taken toward care,
whichever kind of thing that word names.
"""

from datetime import time

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient

from apps.facilities.models import Facility, FacilityService, OpeningHours, ServiceType
from apps.providers.models import Provider, ProviderFacility, Specialty

SEARCH = "/api/v1/search"
KCC_LAT, KCC_LNG = -1.9536, 30.0606


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def paeds_service(db):
    return ServiceType.objects.create(
        code="paediatrics", name_en="Paediatrics", name_rw="Abana", name_fr="Pediatrie"
    )


@pytest.fixture
def paeds_specialty(db, paeds_service):
    specialty = Specialty.objects.create(
        code="paediatrics",
        name_en="Paediatrics",
        name_rw="Ubuvuzi bw'abana",
        name_fr="Pediatrie",
    )
    specialty.service_types.add(paeds_service)
    return specialty


@pytest.fixture
def make_facility(db):
    counter = {"n": 0}

    def _make(*, name, offers=(), verified=True, lat=KCC_LAT, lng=KCC_LNG, district="Gasabo"):
        counter["n"] += 1
        facility = Facility.objects.create(
            name=name,
            slug=f"f-{counter['n']}",
            ownership="public",
            level="health_centre",
            district=district,
            location=Point(lng, lat, srid=4326),
            verified_at=timezone.now() if verified else None,
        )
        for weekday in range(7):
            OpeningHours.objects.create(
                facility=facility, weekday=weekday, opens_at=time(0, 0),
                closes_at=time(23, 59),
            )
        for service in offers:
            FacilityService.objects.create(
                facility=facility, service_type=service, available=True
            )
        return facility

    return _make


def groups(body):
    return {g["kind"]: g["results"] for g in body["groups"]}


# --------------------------------------------------------------------------
# Grouping and ordering
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_one_word_reaches_every_kind_of_thing(
    api_client, paeds_specialty, paeds_service, make_facility
):
    facility = make_facility(name="Paediatric Centre", offers=[paeds_service])
    provider = Provider.objects.create(slug="p1", full_name="Uwase Alice")
    provider.specialties.add(paeds_specialty)
    ProviderFacility.objects.create(provider=provider, facility=facility)

    body = api_client.get(SEARCH, {"q": "paediatric"}).json()
    found = groups(body)

    assert set(found) == {"specialty", "service", "provider", "facility"}


@pytest.mark.django_db
def test_specialties_and_services_rank_above_named_results(
    api_client, paeds_specialty, paeds_service, make_facility
):
    """Somebody typing 'paediatric' almost always wants paediatrics near them,
    not the one clinic whose name happens to contain the word."""
    make_facility(name="Paediatric Centre", offers=[paeds_service])

    body = api_client.get(SEARCH, {"q": "paediatric"}).json()
    kinds = [g["kind"] for g in body["groups"]]

    assert kinds.index("specialty") < kinds.index("facility")
    assert kinds.index("service") < kinds.index("facility")


@pytest.mark.django_db
def test_empty_groups_are_omitted_not_returned_empty(api_client, make_facility):
    make_facility(name="Kimironko Health Centre")

    body = api_client.get(SEARCH, {"q": "kimironko"}).json()

    assert [g["kind"] for g in body["groups"]] == ["facility"]
    assert all(g["results"] for g in body["groups"])


@pytest.mark.django_db
def test_a_short_query_returns_nothing_rather_than_everything(api_client, make_facility):
    make_facility(name="Kimironko Health Centre")

    assert api_client.get(SEARCH, {"q": "k"}).json()["groups"] == []
    assert api_client.get(SEARCH, {"q": ""}).json()["groups"] == []


@pytest.mark.django_db
def test_no_match_returns_an_empty_result_not_an_error(api_client, make_facility):
    make_facility(name="Kimironko Health Centre")

    response = api_client.get(SEARCH, {"q": "zzzznothing"})

    assert response.status_code == 200
    assert response.json()["groups"] == []


# --------------------------------------------------------------------------
# Location
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_facilities_are_ordered_nearest_first_when_location_is_known(
    api_client, make_facility
):
    """A hospital 30 km away is rarely the answer, however well it matches."""
    make_facility(name="Health Far", lat=-1.90, lng=30.20)
    make_facility(name="Health Near", lat=KCC_LAT, lng=KCC_LNG)

    body = api_client.get(
        SEARCH, {"q": "health", "lat": KCC_LAT, "lng": KCC_LNG}
    ).json()

    labels = [r["label"] for r in groups(body)["facility"]]
    assert labels == ["Health Near", "Health Far"]
    assert groups(body)["facility"][0]["distance_m"] is not None


@pytest.mark.django_db
def test_search_works_without_a_location(api_client, make_facility):
    """Location is optional everywhere - denied permission must never block."""
    make_facility(name="Kimironko Health Centre")

    body = api_client.get(SEARCH, {"q": "kimironko"}).json()

    assert groups(body)["facility"][0]["distance_m"] is None


@pytest.mark.django_db
def test_out_of_bounds_coordinates_are_rejected(api_client):
    response = api_client.get(SEARCH, {"q": "health", "lat": 51.5, "lng": -0.12})

    assert response.status_code == 400


# --------------------------------------------------------------------------
# What the client does with a result
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_every_result_carries_somewhere_to_go(
    api_client, paeds_specialty, paeds_service, make_facility
):
    make_facility(name="Paediatric Centre", offers=[paeds_service])

    body = api_client.get(SEARCH, {"q": "paediatric"}).json()

    for group in body["groups"]:
        for result in group["results"]:
            assert result["href"].startswith("/")


@pytest.mark.django_db
def test_an_unroutable_specialty_is_flagged(api_client, db):
    """A specialty mapping to no facility service is shown, but the client
    must not offer it as a way to find care."""
    Specialty.objects.create(
        code="unmapped", name_en="Unmapped care", name_rw="x", name_fr="x"
    )

    body = api_client.get(SEARCH, {"q": "unmapped"}).json()

    assert groups(body)["specialty"][0]["routable"] is False


@pytest.mark.django_db
def test_unverified_facilities_never_appear(api_client, make_facility):
    make_facility(name="Unverified Clinic", verified=False)

    assert api_client.get(SEARCH, {"q": "unverified"}).json()["groups"] == []


@pytest.mark.django_db
def test_a_district_name_finds_its_facilities(api_client, make_facility):
    make_facility(name="Some Clinic", district="Kicukiro")

    body = api_client.get(SEARCH, {"q": "kicukiro"}).json()

    assert groups(body)["facility"][0]["label"] == "Some Clinic"


@pytest.mark.django_db
def test_kinyarwanda_matches_too(api_client, paeds_specialty):
    """Kinyarwanda is the default language; searching in it must work."""
    body = api_client.get(SEARCH, {"q": "abana"}).json()

    assert "specialty" in groups(body)


@pytest.mark.django_db
def test_query_count_is_bounded(
    api_client, paeds_specialty, paeds_service, make_facility,
    django_assert_max_num_queries,
):
    for index in range(10):
        make_facility(name=f"Health {index}", offers=[paeds_service])

    with django_assert_max_num_queries(8):
        api_client.get(SEARCH, {"q": "health", "lat": KCC_LAT, "lng": KCC_LNG})
