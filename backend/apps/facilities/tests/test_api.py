import pytest

from apps.facilities.wait import ALL_STATUSES, STATUS_NOT_REPORTED

from .conftest import KCC_LAT, KCC_LNG

NEARBY = "/api/v1/facilities/nearby"


@pytest.mark.django_db
def test_nearby_returns_expected_shape(api_client, make_facility, mutuelle, general):
    make_facility(
        KCC_LAT, KCC_LNG, name="Kimironko HC", insurers=[mutuelle], services=[general]
    )

    response = api_client.get(NEARBY, {"lat": KCC_LAT, "lng": KCC_LNG})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert "as_of" in body

    result = body["results"][0]
    assert result["name"] == "Kimironko HC"
    assert result["distance_m"] < 50
    assert result["location"] == {"lat": KCC_LAT, "lng": KCC_LNG}
    assert result["is_open"] is True
    assert result["insurers"] == ["mutuelle"]
    assert result["services"] == ["general_consultation"]
    assert result["wait"]["status"] in ALL_STATUSES


@pytest.mark.django_db
def test_phase_0_never_invents_a_wait_time(api_client, make_facility):
    """No facility runs the reception tool yet, so no number may be shown."""
    make_facility(KCC_LAT, KCC_LNG)

    response = api_client.get(NEARBY, {"lat": KCC_LAT, "lng": KCC_LNG})

    wait = response.json()["results"][0]["wait"]
    assert wait["status"] == STATUS_NOT_REPORTED
    assert wait["minutes"] is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "lat,lng",
    [
        (51.5074, -0.1278),  # London - desktop IP geolocation
        (0.0, 0.0),  # Null Island - a failed GPS fix
        (-1.9536, 130.0606),  # transposed digits
    ],
)
def test_out_of_bounds_coordinates_are_rejected(api_client, lat, lng):
    response = api_client.get(NEARBY, {"lat": lat, "lng": lng})

    assert response.status_code == 400
    assert response.json()["type"] == "validation_error"
    assert response.json()["field"] in {"lat", "lng"}


@pytest.mark.django_db
def test_missing_coordinates_are_rejected(api_client):
    assert api_client.get(NEARBY).status_code == 400


@pytest.mark.django_db
def test_radius_above_maximum_is_rejected(api_client):
    response = api_client.get(
        NEARBY, {"lat": KCC_LAT, "lng": KCC_LNG, "radius": 500000}
    )

    assert response.status_code == 400
    assert response.json()["field"] == "radius"


@pytest.mark.django_db
def test_expansion_is_reported_to_the_client(api_client, make_facility):
    """The UI must be able to say 'no facilities within 5 km, showing 10 km'."""
    make_facility(-1.9000, 30.2000)

    response = api_client.get(
        NEARBY, {"lat": KCC_LAT, "lng": KCC_LNG, "radius": 5000}
    )

    query = response.json()["query"]
    assert query["radius_expanded"] is True
    assert query["radius"] >= 10000


@pytest.mark.django_db
def test_facility_detail(api_client, make_facility, mutuelle, general):
    facility = make_facility(
        KCC_LAT, KCC_LNG, insurers=[mutuelle], services=[general]
    )

    response = api_client.get(f"/api/v1/facilities/{facility.slug}")

    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == facility.slug
    assert body["insurers"][0]["code"] == "mutuelle"
    assert body["services"][0]["name_rw"] == "Kwivuza rusange"
    assert body["directions_url"].endswith(f"{KCC_LAT},{KCC_LNG}")
    assert len(body["opening_hours"]) == 7


@pytest.mark.django_db
def test_unverified_facility_detail_is_404(api_client, make_facility):
    facility = make_facility(KCC_LAT, KCC_LNG, verified=False)

    response = api_client.get(f"/api/v1/facilities/{facility.slug}")

    assert response.status_code == 404


@pytest.mark.django_db
def test_districts_lists_only_verified(api_client, make_facility):
    make_facility(KCC_LAT, KCC_LNG, district="Gasabo")
    make_facility(KCC_LAT, KCC_LNG, district="Kicukiro", verified=False)

    response = api_client.get("/api/v1/districts")

    assert response.json()["results"] == ["Gasabo"]


@pytest.mark.django_db
def test_reference_lists(api_client, mutuelle, general):
    insurers = api_client.get("/api/v1/insurers").json()["results"]
    services = api_client.get("/api/v1/service-types").json()["results"]

    assert insurers[0]["code"] == "mutuelle"
    assert services[0]["name_fr"] == "Consultation generale"
