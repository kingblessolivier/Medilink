"""District search: the fallback when a browser gives no location.

This path existed in the UI and did nothing - the district buttons rendered
with no click handler, so the component built to prevent a dead end WAS one,
for exactly the patients least able to work around it.

The property that matters most here is honesty about distance. A district
search knows the patient is in Gasabo and nothing more, so `distance_m` comes
back null rather than zero or a district-centroid guess: a number on the
screen is a number somebody acts on.
"""

import pytest

from .conftest import KCC_LAT, KCC_LNG

NEARBY = "/api/v1/facilities/nearby"


@pytest.mark.django_db
def test_a_district_search_returns_that_districts_facilities(
    api_client, make_facility
):
    make_facility(KCC_LAT, KCC_LNG, name="Kimironko HC", district="Gasabo")
    make_facility(-1.9829, 30.1289, name="Kicukiro HC", district="Kicukiro")

    body = api_client.get(NEARBY, {"district": "Gasabo"}).json()

    assert [f["name"] for f in body["results"]] == ["Kimironko HC"]


@pytest.mark.django_db
def test_a_district_search_reports_no_distance(api_client, make_facility):
    """Null, not zero and not a centroid guess - there is no origin."""
    make_facility(KCC_LAT, KCC_LNG, district="Gasabo")

    body = api_client.get(NEARBY, {"district": "Gasabo"}).json()

    assert body["results"][0]["distance_m"] is None
    assert body["query"]["lat"] is None
    assert body["query"]["lng"] is None
    assert body["query"]["district"] == "Gasabo"


@pytest.mark.django_db
def test_a_district_search_still_filters(api_client, make_facility):
    """The other filters are not a coordinate feature. They have to keep
    working on the path a patient without a location actually takes."""
    make_facility(KCC_LAT, KCC_LNG, name="Open", district="Gasabo", open_now=True)
    make_facility(KCC_LAT, KCC_LNG, name="Shut", district="Gasabo", open_now=False)

    body = api_client.get(
        NEARBY, {"district": "Gasabo", "open_now": "true"}
    ).json()

    assert [f["name"] for f in body["results"]] == ["Open"]


@pytest.mark.django_db
def test_a_district_search_hides_unverified_facilities(
    api_client, make_facility
):
    """The same rule as a coordinate search. An unverified facility is not
    something to put in front of a patient by another route."""
    make_facility(KCC_LAT, KCC_LNG, name="Checked", district="Gasabo")
    make_facility(
        KCC_LAT, KCC_LNG, name="Unchecked", district="Gasabo", verified=False
    )

    body = api_client.get(NEARBY, {"district": "Gasabo"}).json()

    assert [f["name"] for f in body["results"]] == ["Checked"]


@pytest.mark.django_db
def test_district_matching_ignores_case(api_client, make_facility):
    make_facility(KCC_LAT, KCC_LNG, district="Gasabo")

    lower = api_client.get(NEARBY, {"district": "gasabo"}).json()["count"]
    upper = api_client.get(NEARBY, {"district": "GASABO"}).json()["count"]

    assert lower == upper == 1


@pytest.mark.django_db
def test_coordinates_win_over_a_district(api_client, make_facility):
    """A real location gives distances, which a district cannot. When both
    arrive, the better signal has to be the one used."""
    make_facility(KCC_LAT, KCC_LNG, district="Gasabo")

    body = api_client.get(
        NEARBY, {"lat": KCC_LAT, "lng": KCC_LNG, "district": "Gasabo"}
    ).json()

    assert body["query"]["lat"] == KCC_LAT
    assert body["results"][0]["distance_m"] is not None


@pytest.mark.django_db
def test_neither_coordinates_nor_a_district_is_a_400(api_client):
    """Rather than an empty list the client cannot explain."""
    response = api_client.get(NEARBY)

    assert response.status_code == 400
    assert response.json()["field"] == "district"


@pytest.mark.django_db
def test_half_a_coordinate_pair_is_refused(api_client):
    """A lone lat is a client bug. Ignoring it silently would search the wrong
    place and look like it worked."""
    assert api_client.get(NEARBY, {"lat": KCC_LAT}).status_code == 400
    assert api_client.get(NEARBY, {"lng": KCC_LNG}).status_code == 400


@pytest.mark.django_db
def test_an_unknown_district_returns_nothing_rather_than_everything(
    api_client, make_facility
):
    """Widening to the whole country would send somebody across Rwanda."""
    make_facility(KCC_LAT, KCC_LNG, district="Gasabo")

    assert api_client.get(NEARBY, {"district": "Atlantis"}).json()["count"] == 0


@pytest.mark.django_db
def test_a_district_search_respects_the_limit(api_client, make_facility):
    for n in range(8):
        make_facility(KCC_LAT, KCC_LNG, name=f"F{n}", district="Gasabo")

    body = api_client.get(NEARBY, {"district": "Gasabo", "limit": 3}).json()

    assert body["count"] == 3
