"""Geo tests - the highest-value tests in the project.

Every failure guarded here is silent in production: distances merely look
"a bit wrong" rather than obviously broken.
"""

import pytest

from apps.facilities.services import find_nearby

from .conftest import KCC_LAT, KCC_LNG

# Kimironko, roughly 5.8 km east-north-east of the Convention Centre.
KIMIRONKO_LAT = -1.9481
KIMIRONKO_LNG = 30.1122

# Muhanga, roughly 40 km south-west - well outside any Kigali radius.
MUHANGA_LAT = -2.0736
MUHANGA_LNG = 29.7370


@pytest.mark.django_db
def test_point_argument_order_is_lng_lat(make_facility):
    """Guards the silent bug that would break the entire product.

    PostGIS takes x then y. Swapping them puts every Kigali facility in the
    Indian Ocean, and no error is ever raised.
    """
    facility = make_facility(KIMIRONKO_LAT, KIMIRONKO_LNG)

    results, _, _ = find_nearby(lat=KCC_LAT, lng=KCC_LNG, radius_m=10000)

    assert [f.id for f in results] == [facility.id]
    assert 5000 < results[0].distance.m < 6500


@pytest.mark.django_db
def test_radius_is_metres_not_degrees(make_facility):
    """Fails loudly if `location` is a geometry field rather than geography.

    With geometry in SRID 4326, distance_lte is measured in degrees, so a
    radius of 10000 silently means the whole planet.

    The three nearby facilities are here on purpose: they keep the result count
    above MIN_RESULTS_BEFORE_EXPANDING so that the sparse-result expansion never
    fires and the radius under test really is 10 km.
    """
    for _ in range(3):
        make_facility(KIMIRONKO_LAT, KIMIRONKO_LNG)
    far = make_facility(MUHANGA_LAT, MUHANGA_LNG)  # roughly 40 km away

    results, radius, expanded = find_nearby(
        lat=KCC_LAT, lng=KCC_LNG, radius_m=10000
    )

    assert expanded is False
    assert radius == 10000
    assert far.id not in [f.id for f in results]
    assert len(results) == 3


@pytest.mark.django_db
def test_unverified_facilities_never_appear(make_facility):
    make_facility(KCC_LAT, KCC_LNG, verified=False)

    results, _, _ = find_nearby(lat=KCC_LAT, lng=KCC_LNG, radius_m=5000)

    assert results == []


@pytest.mark.django_db
def test_radius_expands_when_results_are_sparse(make_facility):
    """One facility ~12 km out: the 5 km search must widen rather than return
    an empty list."""
    facility = make_facility(-1.9000, 30.2000)

    results, radius, expanded = find_nearby(lat=KCC_LAT, lng=KCC_LNG, radius_m=5000)

    assert expanded is True
    assert radius >= 10000
    assert [f.id for f in results] == [facility.id]


@pytest.mark.django_db
def test_nearest_facility_returned_when_nothing_within_max_radius(make_facility):
    """A rural patient must never get an empty screen.

    Nothing within 50 km, so fall back to the single nearest facility at any
    distance. Knowing care is 80 km away is information; a blank list is not.
    """
    facility = make_facility(-1.5000, 29.6000)  # far north-west of Kigali

    results, radius, expanded = find_nearby(
        lat=-2.6000, lng=29.7400, radius_m=5000
    )

    assert expanded is True
    assert radius == 50000
    assert [f.id for f in results] == [facility.id]
    assert results[0].distance.m > 50000


@pytest.mark.django_db
def test_no_expansion_when_enough_results(make_facility):
    for _ in range(3):
        make_facility(KIMIRONKO_LAT, KIMIRONKO_LNG)

    results, radius, expanded = find_nearby(lat=KCC_LAT, lng=KCC_LNG, radius_m=10000)

    assert expanded is False
    assert radius == 10000
    assert len(results) == 3


@pytest.mark.django_db
def test_closed_facilities_rank_below_open_ones(make_facility):
    """A closed facility must never outrank an open one merely by being nearer."""
    closed_near = make_facility(KCC_LAT, KCC_LNG, name="Closed Near", open_now=False)
    open_far = make_facility(KIMIRONKO_LAT, KIMIRONKO_LNG, name="Open Far")

    results, _, _ = find_nearby(lat=KCC_LAT, lng=KCC_LNG, radius_m=10000)

    assert [f.id for f in results] == [open_far.id, closed_near.id]


@pytest.mark.django_db
def test_insurance_filter_tiers_rather_than_hides(make_facility, mutuelle):
    """A facility that does not take your cover still appears - lower down.

    A patient in an emergency needs to know it exists even if it costs cash.
    """
    accepts = make_facility(KIMIRONKO_LAT, KIMIRONKO_LNG, insurers=[mutuelle])
    does_not = make_facility(KCC_LAT, KCC_LNG)

    results, _, _ = find_nearby(
        lat=KCC_LAT, lng=KCC_LNG, radius_m=10000, insurer="mutuelle"
    )

    assert [f.id for f in results] == [accepts.id, does_not.id]
    assert results[0].accepts_insurer is True
    assert results[1].accepts_insurer is False


@pytest.mark.django_db
def test_service_filter_excludes_facilities_without_it(
    make_facility, general, maternity
):
    has_maternity = make_facility(KCC_LAT, KCC_LNG, services=[general, maternity])
    make_facility(KIMIRONKO_LAT, KIMIRONKO_LNG, services=[general])

    results, _, _ = find_nearby(
        lat=KCC_LAT, lng=KCC_LNG, radius_m=10000, service="maternity"
    )

    assert [f.id for f in results] == [has_maternity.id]


@pytest.mark.django_db
def test_open_now_filter(make_facility):
    open_facility = make_facility(KCC_LAT, KCC_LNG)
    make_facility(KIMIRONKO_LAT, KIMIRONKO_LNG, open_now=False)

    results, _, _ = find_nearby(
        lat=KCC_LAT, lng=KCC_LNG, radius_m=10000, open_now=True
    )

    assert [f.id for f in results] == [open_facility.id]


@pytest.mark.django_db
def test_limit_is_respected(make_facility):
    for _ in range(5):
        make_facility(KIMIRONKO_LAT, KIMIRONKO_LNG)

    results, _, _ = find_nearby(lat=KCC_LAT, lng=KCC_LNG, radius_m=10000, limit=2)

    assert len(results) == 2


@pytest.mark.django_db
def test_no_n_plus_one_queries(make_facility, django_assert_max_num_queries, mutuelle):
    """Guards against a serializer loop turning 20 results into 60 queries."""
    for _ in range(20):
        make_facility(KIMIRONKO_LAT, KIMIRONKO_LNG, insurers=[mutuelle])

    with django_assert_max_num_queries(4):
        results, _, _ = find_nearby(lat=KCC_LAT, lng=KCC_LNG, radius_m=10000)
        # Touch the prefetched relations the serializer will read.
        for facility in results:
            list(facility.insurers.all())
            list(facility.services.all())
            list(facility.opening_hours.all())
