import pytest
from django.utils import timezone

from apps.facilities.wait import (
    STATUS_AVAILABLE,
    STATUS_CLOSED,
    STATUS_INSUFFICIENT_DATA,
    STATUS_NOT_REPORTED,
)
from apps.patients.models import Patient
from apps.queueing.models import QueueEntry
from apps.queueing.services import (
    QueueError,
    call,
    check_in,
    eta_for,
    refresh_service_time_stats,
    serve,
    wait_snapshot,
)

# --------------------------------------------------------------------------
# Position
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_position_counts_only_waiting_entries_ahead(facility, general, make_entry):
    a = make_entry(facility, general, minutes_ago=30)
    make_entry(facility, general, minutes_ago=20)
    c = make_entry(facility, general, minutes_ago=10)

    assert c.position() == 3

    serve(a)

    assert c.position() == 2


@pytest.mark.django_db
def test_position_is_scoped_per_service(facility, general, maternity, make_entry):
    make_entry(facility, general, minutes_ago=30)
    make_entry(facility, general, minutes_ago=20)
    entry = make_entry(facility, maternity, minutes_ago=10)

    assert entry.position() == 1


@pytest.mark.django_db
def test_position_is_scoped_per_facility(
    facility, other_facility, general, make_entry
):
    make_entry(other_facility, general, minutes_ago=30)
    entry = make_entry(facility, general, minutes_ago=10)

    assert entry.position() == 1


@pytest.mark.django_db
def test_served_entry_has_no_position(facility, general, make_entry):
    entry = make_entry(facility, general)
    serve(entry)
    assert entry.position() == 0


# --------------------------------------------------------------------------
# Check-in
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_check_in_creates_patient_from_phone(facility, general):
    entry, created = check_in(
        facility=facility, service_type=general, phone="0788123456"
    )

    assert created is True
    assert entry.patient.phone == "+250788123456"  # normalised to E.164
    assert entry.ticket_code == "G-001"


@pytest.mark.django_db
def test_check_in_reuses_an_existing_patient(facility, general, maternity):
    check_in(facility=facility, service_type=general, phone="+250788123456")
    serve(QueueEntry.objects.first())
    check_in(facility=facility, service_type=maternity, phone="0788123456")

    assert Patient.objects.count() == 1


@pytest.mark.django_db
def test_check_in_rejects_a_patient_already_in_the_queue(facility, general):
    check_in(facility=facility, service_type=general, phone="0788123456")

    with pytest.raises(QueueError, match="already in the queue"):
        check_in(facility=facility, service_type=general, phone="0788123456")


@pytest.mark.django_db
def test_check_in_is_idempotent(facility, general):
    """Reception networks drop constantly; a retry must not duplicate."""
    first, created_first = check_in(
        facility=facility,
        service_type=general,
        walk_in_name="Uwase",
        idempotency_key="abc-123",
    )
    second, created_second = check_in(
        facility=facility,
        service_type=general,
        walk_in_name="Uwase",
        idempotency_key="abc-123",
    )

    assert created_first is True
    assert created_second is False
    assert first.id == second.id
    assert QueueEntry.objects.count() == 1


@pytest.mark.django_db
def test_walk_in_needs_no_phone(facility, general):
    entry, _ = check_in(
        facility=facility, service_type=general, walk_in_name="Uwase Alice"
    )

    assert entry.patient is None
    assert entry.display_name == "Uwase Alice"


@pytest.mark.django_db
def test_check_in_requires_a_phone_or_a_name(facility, general):
    with pytest.raises(QueueError, match="phone number or a walk-in name"):
        check_in(facility=facility, service_type=general)


@pytest.mark.django_db
def test_first_check_in_marks_the_facility_a_queue_reporter(facility, general):
    assert facility.reports_queue is False

    check_in(facility=facility, service_type=general, walk_in_name="Uwase")

    facility.refresh_from_db()
    assert facility.reports_queue is True


@pytest.mark.django_db
def test_ticket_codes_increment_per_service_per_day(facility, general, maternity):
    a, _ = check_in(facility=facility, service_type=general, walk_in_name="One")
    b, _ = check_in(facility=facility, service_type=general, walk_in_name="Two")
    c, _ = check_in(facility=facility, service_type=maternity, walk_in_name="Three")

    assert [a.ticket_code, b.ticket_code, c.ticket_code] == ["G-001", "G-002", "M-001"]


# --------------------------------------------------------------------------
# Transitions
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_transitions_stamp_their_times(facility, general, make_entry):
    entry = make_entry(facility, general)

    call(entry)
    assert entry.status == QueueEntry.Status.CALLED
    assert entry.called_at is not None

    serve(entry)
    assert entry.status == QueueEntry.Status.SERVED
    assert entry.served_at is not None
    assert entry.closed_at is not None


@pytest.mark.django_db
def test_cannot_serve_an_already_served_entry(facility, general, make_entry):
    entry = make_entry(facility, general)
    serve(entry)

    with pytest.raises(QueueError, match="Cannot move an entry"):
        serve(entry)


# --------------------------------------------------------------------------
# ETA and statistics
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_eta_is_withheld_below_the_minimum_sample_size(
    facility, general, make_entry, make_stat
):
    make_stat(facility, general, median=6.0, samples=19)  # one below the gate
    make_entry(facility, general, minutes_ago=30)
    entry = make_entry(facility, general, minutes_ago=10)

    result = eta_for(entry)

    assert result["eta_minutes"] is None
    assert result["eta_confidence"] is None
    assert result["position"] == 2


@pytest.mark.django_db
def test_eta_uses_people_ahead_not_position(
    facility, general, make_entry, make_stat
):
    """The person being served is partway through; counting them in full
    would overstate every wait behind them."""
    make_stat(facility, general, median=10.0, samples=100)
    make_entry(facility, general, minutes_ago=30)
    make_entry(facility, general, minutes_ago=20)
    entry = make_entry(facility, general, minutes_ago=10)

    result = eta_for(entry)

    assert result["position"] == 3
    assert result["people_ahead"] == 2
    assert result["eta_minutes"] == 20


@pytest.mark.django_db
def test_confidence_falls_with_sample_size(facility, general, make_entry, make_stat):
    make_stat(facility, general, median=6.0, samples=45)
    make_entry(facility, general, minutes_ago=30)
    entry = make_entry(facility, general, minutes_ago=10)

    assert eta_for(entry)["eta_confidence"] == "medium"


@pytest.mark.django_db
def test_refresh_stats_uses_median_not_mean(facility, general):
    """One ninety-minute patient must not drag the estimate for everyone."""
    from datetime import timedelta

    # All five join within the same clock hour, so they land in one bucket
    # regardless of when the suite happens to run.
    joined = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
    for index, minutes in enumerate((5, 6, 7, 6, 90)):
        QueueEntry.objects.create(
            facility=facility,
            service_type=general,
            walk_in_name=f"Patient {index}",
            joined_at=joined,
            served_at=joined + timedelta(minutes=minutes),
            status=QueueEntry.Status.SERVED,
            ticket_code=f"G-{index:03d}",
        )

    refresh_service_time_stats()

    from apps.queueing.models import ServiceTimeStat

    stat = ServiceTimeStat.objects.get(hour_of_day=10)
    assert stat.sample_size == 5
    assert 5 <= stat.median_minutes <= 8  # a mean would be about 23


# --------------------------------------------------------------------------
# Wait snapshot - the honesty rule
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_wait_is_not_reported_without_the_reception_tool(make_facility):
    facility = make_facility(reports_queue=False)

    snapshot = wait_snapshot([facility])

    assert snapshot[facility.id]["status"] == STATUS_NOT_REPORTED
    assert snapshot[facility.id]["minutes"] is None


@pytest.mark.django_db
def test_wait_is_withheld_below_the_minimum_sample_size(
    facility, general, make_entry, make_stat
):
    facility.reports_queue = True
    facility.save()
    make_stat(facility, general, median=6.0, samples=19)
    make_entry(facility, general)

    snapshot = wait_snapshot([facility], service_code="general_consultation")

    assert snapshot[facility.id]["status"] == STATUS_INSUFFICIENT_DATA
    assert snapshot[facility.id]["minutes"] is None
    assert snapshot[facility.id]["people_waiting"] == 1


@pytest.mark.django_db
def test_wait_is_published_once_there_is_enough_data(
    facility, general, make_entry, make_stat
):
    facility.reports_queue = True
    facility.save()
    make_stat(facility, general, median=8.0, samples=120)
    for offset in (30, 20, 10):
        make_entry(facility, general, minutes_ago=offset)

    snapshot = wait_snapshot([facility], service_code="general_consultation")

    assert snapshot[facility.id]["status"] == STATUS_AVAILABLE
    assert snapshot[facility.id]["minutes"] == 24  # 3 waiting x 8 min
    assert snapshot[facility.id]["people_waiting"] == 3


@pytest.mark.django_db
def test_closed_facility_reports_closed_not_a_number(
    make_facility, general, make_entry, make_stat
):
    facility = make_facility(open_now=False, reports_queue=True, services=[general])
    make_stat(facility, general, median=8.0, samples=120)
    make_entry(facility, general)

    snapshot = wait_snapshot([facility], service_code="general_consultation")

    assert snapshot[facility.id]["status"] == STATUS_CLOSED
    assert snapshot[facility.id]["minutes"] is None


@pytest.mark.django_db
def test_wait_snapshot_is_not_n_plus_one(
    make_facility, general, make_stat, django_assert_max_num_queries
):
    facilities = [
        make_facility(reports_queue=True, services=[general]) for _ in range(10)
    ]
    for facility in facilities:
        make_stat(facility, general, samples=120)

    with django_assert_max_num_queries(4):
        wait_snapshot(facilities, service_code="general_consultation")
