"""Executable versions of the Phase 0 checklist in docs/09.

Each test here corresponds to a line in "Definition of done" that was
previously only prose. Field-work items (on-site coordinates, patient
interviews) cannot be asserted in code and are tracked in
backend/fixtures/README.md instead.
"""

from datetime import time

import pytest
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.facilities import wait
from apps.facilities.models import Facility, OpeningHours
from apps.facilities.services import closes_at, find_nearby, is_open_now, opens_next
from apps.insurance.models import Insurer

from .conftest import KCC_LAT, KCC_LNG

pytestmark = pytest.mark.django_db


# --- "EXPLAIN ANALYZE shows an Index Scan, not a Seq Scan" -------------------

# Kigali is roughly 30.0-30.2 E, -2.05 to -1.87 S. The noise facilities are
# spread over the whole country so that a 5 km search is genuinely selective;
# with a handful of rows Postgres would correctly prefer a sequential scan and
# the assertion would prove nothing about the index.
NOISE_FACILITIES = 3000


@pytest.fixture
def a_country_full_of_facilities(db):
    """Enough rows, spread widely enough, for the planner to want the index."""
    import random

    rng = random.Random(20240501)
    Facility.objects.bulk_create(
        [
            Facility(
                name=f"Noise {n}",
                slug=f"noise-{n}",
                ownership="public",
                level="health_centre",
                district="Gasabo",
                location=Point(
                    rng.uniform(28.90, 30.85),  # lng first
                    rng.uniform(-2.80, -1.10),
                    srid=4326,
                ),
                verified_at=timezone.now(),
            )
            for n in range(NOISE_FACILITIES)
        ]
    )
    # The planner chooses on statistics, not on row count, so they must exist.
    with connection.cursor() as cursor:
        cursor.execute("ANALYZE facilities_facility")


def test_nearby_search_uses_the_gist_index(a_country_full_of_facilities):
    point = Point(KCC_LNG, KCC_LAT, srid=4326)
    plan = (
        Facility.objects.filter(
            verified_at__isnull=False,
            location__dwithin=(point, D(m=5000)),
        )
        .annotate(distance=Distance("location", point))
        .explain(analyze=True)
    )

    assert "facility_location_gist" in plan, (
        "The spatial index is not being used. Every nearby search is now a "
        f"full table scan. Plan was:\n{plan}"
    )
    assert "Seq Scan on facilities_facility" not in plan, (
        f"Sequential scan of the facility table. Plan was:\n{plan}"
    )


def test_find_nearby_filters_with_st_dwithin(a_country_full_of_facilities):
    """The radius filter must reach SQL as ST_DWithin.

    `distance_lte` returns exactly the same rows, so no behavioural test can
    tell the two apart - but on a geography column it compiles to
    `ST_Distance(...) <= n`, which no index can answer. This asserts the SQL
    that find_nearby itself produces, not a hand-built equivalent.
    """
    queries = []
    with CaptureQueriesContext(connection) as captured:
        find_nearby(lat=KCC_LAT, lng=KCC_LNG, radius_m=5000)
        queries = [q["sql"] for q in captured.captured_queries]

    radius_queries = [q for q in queries if "st_dwithin" in q.lower()]
    assert radius_queries, (
        "No query used ST_DWithin. The radius filter has fallen back to a "
        "scan. Queries were:\n" + "\n".join(queries)
    )


# --- "Nearby search returns correct distances" ------------------------------

# Two landmarks with an independently known separation. Kigali Convention
# Centre to Kigali International Airport is ~4.4 km in a straight line; a
# coordinate-order bug puts them in the Indian Ocean and the distance in the
# thousands of kilometres.
KIA_LAT, KIA_LNG = -1.9686, 30.1395
KCC_TO_KIA_M = 8_800


def test_distance_to_a_known_pair_is_correct(make_facility):
    make_facility(KIA_LAT, KIA_LNG, name="Kigali International Airport")

    results, _, _ = find_nearby(lat=KCC_LAT, lng=KCC_LNG, radius_m=20000)

    assert len(results) == 1
    metres = results[0].distance.m
    # 5% tolerance: geography distance on the spheroid, against a figure read
    # off a map.
    assert abs(metres - KCC_TO_KIA_M) < KCC_TO_KIA_M * 0.05, (
        f"Expected roughly {KCC_TO_KIA_M} m, got {metres:.0f} m. "
        "A wildly wrong figure usually means Point(lat, lng) instead of "
        "Point(lng, lat)."
    )


# --- "Insurance filter works for Mutuelle, RSSB and MMI" --------------------


@pytest.fixture
def three_insurers(db):
    return {
        code: Insurer.objects.create(code=code, name=code.upper())
        for code in ("mutuelle", "rssb", "mmi")
    }


@pytest.mark.parametrize("code", ["mutuelle", "rssb", "mmi"])
def test_insurance_filter_works_for_each_public_insurer(
    make_facility, three_insurers, code
):
    """A facility accepting the queried insurer outranks one that does not.

    The filter tiers rather than hides - a patient who can pay cash still
    needs to see the closer facility - so the assertion is on order, not on
    membership.
    """
    others = [c for c in three_insurers if c != code]

    # The non-accepting facility is nearer, so only tiering can put the
    # accepting one first.
    make_facility(
        KCC_LAT + 0.001,
        KCC_LNG,
        name="Nearer, wrong insurer",
        insurers=[three_insurers[c] for c in others],
    )
    make_facility(
        KCC_LAT + 0.010,
        KCC_LNG,
        name="Further, right insurer",
        insurers=[three_insurers[code]],
    )

    results, _, _ = find_nearby(lat=KCC_LAT, lng=KCC_LNG, insurer=code)

    assert [f.name for f in results] == [
        "Further, right insurer",
        "Nearer, wrong insurer",
    ]
    assert results[0].accepts_insurer is True
    assert results[1].accepts_insurer is False


def test_insurance_acceptance_is_reported_per_facility(
    api_client, make_facility, three_insurers
):
    make_facility(
        KCC_LAT,
        KCC_LNG,
        name="Accepts two",
        insurers=[three_insurers["mutuelle"], three_insurers["rssb"]],
    )

    response = api_client.get(
        "/api/v1/facilities/nearby", {"lat": KCC_LAT, "lng": KCC_LNG}
    )

    codes = set(response.json()["results"][0]["insurers"])
    assert codes == {"mutuelle", "rssb"}
    assert "mmi" not in codes


def test_an_unrecognised_insurer_code_does_not_hide_every_facility(
    api_client, make_facility, three_insurers
):
    """A typo in the client must degrade to "no tiering", never to an empty list.

    A patient who sees nothing concludes there is no care nearby. Tiering means
    an unknown code simply ranks every facility as not-accepting, and they
    still get the directory.
    """
    make_facility(KCC_LAT, KCC_LNG, insurers=[three_insurers["mutuelle"]])

    response = api_client.get(
        "/api/v1/facilities/nearby",
        {"lat": KCC_LAT, "lng": KCC_LNG, "insurer": "not-an-insurer"},
    )

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["accepts_insurer"] is False


# --- "Opening hours correct, including lunch breaks" ------------------------


@pytest.fixture
def facility_with_lunch_break(make_facility):
    """07:00-12:00, closed for lunch, 13:00-17:00. Monday to Friday."""
    facility = make_facility(KCC_LAT, KCC_LNG, name="Lunch Break HC", open_now=False)
    for weekday in range(5):
        OpeningHours.objects.create(
            facility=facility, weekday=weekday, opens_at=time(7), closes_at=time(12)
        )
        OpeningHours.objects.create(
            facility=facility, weekday=weekday, opens_at=time(13), closes_at=time(17)
        )
    return facility


def at(hour, minute=0):
    """A Wednesday at the given local time - a weekday in every timezone."""
    return timezone.localtime().replace(
        year=2025, month=1, day=8, hour=hour, minute=minute, second=0, microsecond=0
    )


@pytest.mark.parametrize(
    "hour,minute,expected_open",
    [
        (6, 30, False),  # before opening
        (7, 0, True),  # opening minute
        (11, 59, True),  # last minute of the morning
        (12, 30, False),  # THE LUNCH BREAK
        (13, 0, True),  # reopening minute
        (16, 59, True),  # last minute of the afternoon
        (18, 0, False),  # after closing
    ],
)
def test_lunch_break_is_closed(facility_with_lunch_break, hour, minute, expected_open):
    assert is_open_now(facility_with_lunch_break, at(hour, minute)) is expected_open


def test_closes_at_returns_the_period_in_progress_not_the_last_of_the_day(
    facility_with_lunch_break,
):
    # 10:00 is inside the morning period: the patient must be told 12:00, not
    # 17:00, or they will arrive to a locked door at 12:15.
    assert closes_at(facility_with_lunch_break, at(10)) == time(12)
    assert closes_at(facility_with_lunch_break, at(14)) == time(17)
    assert closes_at(facility_with_lunch_break, at(12, 30)) is None


def test_opens_next_during_lunch_is_the_afternoon_period(facility_with_lunch_break):
    assert opens_next(facility_with_lunch_break, at(12, 30)) == time(13)
    # Before opening, the next period is the morning one.
    assert opens_next(facility_with_lunch_break, at(6)) == time(7)
    # After the last period there is nothing left today.
    assert opens_next(facility_with_lunch_break, at(18)) is None


def test_a_facility_on_lunch_break_reports_closed_not_a_wait(
    facility_with_lunch_break,
):
    snapshot = wait.wait_snapshot([facility_with_lunch_break], now=at(12, 30))
    assert snapshot[facility_with_lunch_break.id]["status"] == wait.STATUS_CLOSED


# --- "All four wait.status values render" -----------------------------------


def test_the_status_vocabulary_is_exactly_the_four_documented_values():
    """The frontend switch in WaitLine.tsx is exhaustive over this tuple.

    Adding a fifth status without updating the client makes it render nothing
    at all for that facility, so the vocabulary is pinned here.
    """
    assert set(wait.ALL_STATUSES) == {
        "available",
        "not_reported",
        "insufficient_data",
        "closed",
    }


def test_phase_0_emits_only_the_statuses_it_can_honestly_produce(make_facility):
    """No facility runs the reception tool yet, so a number is never possible.

    When Phase 1 fills in wait_snapshot(), `available` joins this set - that is
    the point at which this test is expected to change.
    """
    closed = make_facility(KCC_LAT, KCC_LNG, name="Closed", open_now=False)
    silent = make_facility(KCC_LAT, KCC_LNG, name="Silent", reports_queue=False)
    reporting = make_facility(KCC_LAT, KCC_LNG, name="Reports", reports_queue=True)

    snapshot = wait.wait_snapshot([closed, silent, reporting])
    statuses = {f.id: snapshot[f.id]["status"] for f in (closed, silent, reporting)}

    assert statuses[closed.id] == wait.STATUS_CLOSED
    assert statuses[silent.id] == wait.STATUS_NOT_REPORTED
    assert statuses[reporting.id] == wait.STATUS_INSUFFICIENT_DATA
    assert wait.STATUS_AVAILABLE not in statuses.values()

    # And the honesty rule itself: never a number, whatever the status.
    for entry in snapshot.values():
        assert entry["minutes"] is None
        assert entry["people_waiting"] is None


def test_insufficient_data_is_gated_on_the_configured_sample_floor(settings):
    """MIN_SERVICE_TIME_SAMPLES is the executable form of the honesty rule.

    Phase 1 reads it in wait_snapshot(); it must stay configured and sane so
    that the gate cannot be silently removed.
    """
    assert settings.MIN_SERVICE_TIME_SAMPLES >= 20
