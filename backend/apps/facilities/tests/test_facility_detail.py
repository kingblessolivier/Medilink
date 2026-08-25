"""The facility profile payload.

Two things it must get right, both of them about not overclaiming:

  - a per-service wait, honouring the same four statuses and the same
    sample-size gate as everywhere else
  - insurance coverage that says "not confirmed" until a human confirmed it
"""

from datetime import time

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient

from apps.facilities.models import Facility, FacilityService, OpeningHours, ServiceType
from apps.insurance.models import FacilityServiceInsurer, Insurer
from apps.queueing.models import QueueEntry
from apps.queueing.services import facility_service_waits
from apps.queueing.testing import make_service_time_stat

KCC_LAT, KCC_LNG = -1.9536, 30.0606


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def general(db):
    return ServiceType.objects.create(
        code="general_consultation", name_en="General", name_rw="x", name_fr="x"
    )


@pytest.fixture
def dental(db):
    return ServiceType.objects.create(
        code="dental", name_en="Dental", name_rw="x", name_fr="x"
    )


@pytest.fixture
def mutuelle(db):
    return Insurer.objects.create(code="mutuelle", name="Mutuelle de Sante")


@pytest.fixture
def facility(db, general, dental):
    facility = Facility.objects.create(
        name="Kimironko HC",
        slug="kimironko-hc",
        ownership="public",
        level="health_centre",
        district="Gasabo",
        location=Point(KCC_LNG, KCC_LAT, srid=4326),
        verified_at=timezone.now(),
        reports_queue=True,
    )
    for weekday in range(7):
        OpeningHours.objects.create(
            facility=facility, weekday=weekday, opens_at=time(0, 0),
            closes_at=time(23, 59),
        )
    for service in (general, dental):
        FacilityService.objects.create(
            facility=facility, service_type=service, available=True
        )
    return facility


def services(body):
    return {s["code"]: s for s in body["services"]}


# --------------------------------------------------------------------------
# Per-service wait
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_each_service_carries_its_own_wait(facility, general, dental):
    """A patient asks "how busy is the thing I need", not "how busy is this
    hospital"."""
    make_service_time_stat(facility, general, median=8.0)
    make_service_time_stat(facility, dental, median=20.0)
    for index in range(3):
        QueueEntry.objects.create(
            facility=facility, service_type=general,
            walk_in_name=f"G{index}", ticket_code=f"G-{index}",
        )
    QueueEntry.objects.create(
        facility=facility, service_type=dental, walk_in_name="D", ticket_code="D-1"
    )

    waits = facility_service_waits(facility)

    assert waits["general_consultation"]["minutes"] == 24  # 3 x 8
    assert waits["dental"]["minutes"] == 20  # 1 x 20


@pytest.mark.django_db
def test_a_service_with_no_statistics_is_listed_not_dropped(facility, general):
    """Dropping it would silently shorten the service list."""
    waits = facility_service_waits(facility)

    assert set(waits) == {"general_consultation", "dental"}
    assert waits["dental"]["status"] == "insufficient_data"
    assert waits["dental"]["minutes"] is None


@pytest.mark.django_db
def test_the_sample_gate_applies_per_service(facility, general):
    make_service_time_stat(
        facility, general, median=8.0, samples=19  # one below the gate
    )
    QueueEntry.objects.create(
        facility=facility, service_type=general, walk_in_name="G", ticket_code="G-1"
    )

    waits = facility_service_waits(facility)

    assert waits["general_consultation"]["status"] == "insufficient_data"
    assert waits["general_consultation"]["minutes"] is None


@pytest.mark.django_db
def test_a_facility_without_the_reception_tool_reports_nothing(facility):
    facility.reports_queue = False
    facility.save()

    waits = facility_service_waits(facility)

    assert all(w["status"] == "not_reported" for w in waits.values())


@pytest.mark.django_db
def test_a_closed_facility_reports_closed_for_every_service(db, general):
    facility = Facility.objects.create(
        name="Closed", slug="closed", ownership="public", level="health_centre",
        district="Gasabo", location=Point(KCC_LNG, KCC_LAT, srid=4326),
        verified_at=timezone.now(), reports_queue=True,
    )
    FacilityService.objects.create(
        facility=facility, service_type=general, available=True
    )

    waits = facility_service_waits(facility)

    assert waits["general_consultation"]["status"] == "closed"


@pytest.mark.django_db
def test_per_service_waits_do_not_scale_with_service_count(
    facility, django_assert_num_queries
):
    """A referral hospital offers a dozen services. One query pair per service
    would be a dozen round trips on the profile page.

    Asserts the shape rather than a ceiling: whatever it costs for two
    services, it must cost exactly the same for twelve.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as ctx:
        facility_service_waits(facility)
    baseline = len(ctx.captured_queries)

    for index in range(10):
        extra = ServiceType.objects.create(
            code=f"extra-{index}", name_en=f"Extra {index}", name_rw="x", name_fr="x"
        )
        FacilityService.objects.create(
            facility=facility, service_type=extra, available=True
        )
    facility.refresh_from_db()

    with django_assert_num_queries(baseline):
        facility_service_waits(facility)


# --------------------------------------------------------------------------
# Insurance coverage: unknown until confirmed
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_coverage_defaults_to_not_confirmed(api_client, facility, mutuelle, general):
    """Absence of data is not evidence of coverage. A patient turned away at a
    counter because we implied coverage is a real harm."""
    facility_service = facility.services.get(service_type=general)
    FacilityServiceInsurer.objects.create(
        facility_service=facility_service, insurer=mutuelle
    )

    body = api_client.get(f"/api/v1/facilities/{facility.slug}").json()
    coverage = services(body)["general_consultation"]["coverage"]

    assert coverage[0]["coverage"] == "unknown"


@pytest.mark.django_db
def test_an_unconfirmed_row_publishes_as_unknown_whatever_was_entered(
    api_client, facility, mutuelle, general
):
    """Somebody part-way through entering data must not publish a claim."""
    facility_service = facility.services.get(service_type=general)
    FacilityServiceInsurer.objects.create(
        facility_service=facility_service,
        insurer=mutuelle,
        coverage=FacilityServiceInsurer.Coverage.FULL,
        confirmed_at=None,
    )

    body = api_client.get(f"/api/v1/facilities/{facility.slug}").json()

    assert services(body)["general_consultation"]["coverage"][0]["coverage"] == "unknown"


@pytest.mark.django_db
def test_a_confirmed_row_publishes_what_was_entered(
    api_client, facility, mutuelle, general, dental
):
    for service, coverage in (
        (general, FacilityServiceInsurer.Coverage.FULL),
        (dental, FacilityServiceInsurer.Coverage.PARTIAL),
    ):
        FacilityServiceInsurer.objects.create(
            facility_service=facility.services.get(service_type=service),
            insurer=mutuelle,
            coverage=coverage,
            confirmed_at=timezone.now(),
        )

    body = api_client.get(f"/api/v1/facilities/{facility.slug}").json()
    found = services(body)

    assert found["general_consultation"]["coverage"][0]["coverage"] == "full"
    assert found["dental"]["coverage"][0]["coverage"] == "partial"


@pytest.mark.django_db
def test_a_service_with_no_coverage_rows_reports_an_empty_list(
    api_client, facility, general
):
    """Not an implied 'covered'. The client renders 'not confirmed'."""
    body = api_client.get(f"/api/v1/facilities/{facility.slug}").json()

    assert services(body)["general_consultation"]["coverage"] == []


@pytest.mark.django_db
def test_coverage_carries_any_stated_condition(
    api_client, facility, mutuelle, general
):
    FacilityServiceInsurer.objects.create(
        facility_service=facility.services.get(service_type=general),
        insurer=mutuelle,
        coverage=FacilityServiceInsurer.Coverage.PARTIAL,
        note="Referral required",
        confirmed_at=timezone.now(),
    )

    body = api_client.get(f"/api/v1/facilities/{facility.slug}").json()

    assert services(body)["general_consultation"]["coverage"][0]["note"] == (
        "Referral required"
    )


@pytest.mark.django_db
def test_no_price_is_ever_returned(api_client, facility, mutuelle, general):
    """We hold no verified cost data, and a wrong number is worse than none."""
    FacilityServiceInsurer.objects.create(
        facility_service=facility.services.get(service_type=general),
        insurer=mutuelle,
        confirmed_at=timezone.now(),
    )

    response = api_client.get(f"/api/v1/facilities/{facility.slug}")
    body = response.content.decode().lower()

    for word in ("price", "cost", "amount", "rwf", "fee"):
        assert word not in body


@pytest.mark.django_db
def test_query_count_does_not_grow_with_the_number_of_services(
    api_client, facility, mutuelle, general, dental, django_assert_num_queries
):
    """The property that matters is the SHAPE, not a magic number.

    A referral hospital offers a dozen services; if the page costs one query
    pair per service it is a dozen round trips. Asserting an exact ceiling
    just breaks whenever a prefetch is added, so instead: count the queries
    for two services, add ten more, and require the count to be identical.
    """
    for service in (general, dental):
        FacilityServiceInsurer.objects.create(
            facility_service=facility.services.get(service_type=service),
            insurer=mutuelle,
            confirmed_at=timezone.now(),
        )

    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as ctx:
        api_client.get(f"/api/v1/facilities/{facility.slug}")
    baseline = len(ctx.captured_queries)

    for index in range(10):
        extra = ServiceType.objects.create(
            code=f"extra-{index}", name_en=f"Extra {index}", name_rw="x", name_fr="x"
        )
        FacilityService.objects.create(
            facility=facility, service_type=extra, available=True
        )

    with django_assert_num_queries(baseline):
        api_client.get(f"/api/v1/facilities/{facility.slug}")


@pytest.mark.django_db
def test_a_facility_with_an_open_session_is_bookable(api_client, facility, general):
    """`bookable` was a hardcoded False with a note saying booking arrived in
    Phase 2 - which it did, and the note was never revisited. The Book action
    therefore never rendered anywhere in the product."""
    from apps.scheduling.models import ScheduleTemplate

    ScheduleTemplate.objects.create(
        facility=facility,
        service_type=general,
        weekday=1,
        start_time=time(8, 0),
        end_time=time(12, 0),
    )

    body = api_client.get(f"/api/v1/facilities/{facility.slug}").json()

    assert body["bookable"] is True


@pytest.mark.django_db
def test_a_facility_with_no_sessions_is_not_bookable(api_client, facility):
    body = api_client.get(f"/api/v1/facilities/{facility.slug}").json()

    assert body["bookable"] is False


@pytest.mark.django_db
def test_a_closed_session_does_not_make_a_facility_bookable(
    api_client, facility, general
):
    """Closing a session stops new bookings, so it must stop advertising them
    too."""
    from apps.scheduling.models import ScheduleTemplate

    ScheduleTemplate.objects.create(
        facility=facility,
        service_type=general,
        weekday=1,
        start_time=time(8, 0),
        end_time=time(12, 0),
        active=False,
    )

    body = api_client.get(f"/api/v1/facilities/{facility.slug}").json()

    assert body["bookable"] is False
