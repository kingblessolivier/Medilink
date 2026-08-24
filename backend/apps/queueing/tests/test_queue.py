from datetime import timedelta

import pytest
from django.utils import timezone

from apps.facilities.wait import (
    STATUS_AVAILABLE,
    STATUS_CLOSED,
    STATUS_INSUFFICIENT_DATA,
    STATUS_NOT_REPORTED,
)
from apps.patients.models import Patient
from apps.queueing.models import QueueEntry, ServiceTimeStat
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


def _run_clinic(facility, service, *, served_every, arrive_every, count, hour=10):
    """A clinic where patients ARRIVE faster than they are SERVED, so a queue
    builds - which is the only arrangement that tells the two quantities apart.

    Returns the served entries, oldest first.
    """
    start = timezone.localtime().replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    free = start
    entries = []
    for index in range(count):
        joined = start + timedelta(minutes=index * arrive_every)
        began = max(joined, free)
        finished = began + timedelta(minutes=served_every)
        free = finished
        entries.append(
            QueueEntry.objects.create(
                facility=facility,
                service_type=service,
                walk_in_name=f"Patient {index}",
                joined_at=joined,
                served_at=finished,
                status=QueueEntry.Status.SERVED,
                ticket_code=f"G-{index:03d}",
            )
        )
    return entries


@pytest.mark.django_db
def test_the_stat_measures_the_service_rate_not_the_wait(facility, general):
    """The defect this test used to hide.

    It previously gave every patient an IDENTICAL joined_at - the one
    arrangement in which a patient's total wait and the clinic's per-patient
    rate are the same number. With staggered arrivals they diverge sharply, and
    the old implementation stored the wait: `served_at - joined_at` grows with
    the queue, and the ETA then multiplied it by the queue again.

    Here the clinic serves one patient every 10 minutes while patients arrive
    every 6, so a queue builds and individual waits climb past an hour. The
    rate is still 10.
    """
    entries = _run_clinic(
        facility, general, served_every=10, arrive_every=6, count=30
    )

    # The waits really do diverge - otherwise this test proves nothing.
    last = entries[-1]
    assert (last.served_at - last.joined_at).total_seconds() / 60 > 60

    refresh_service_time_stats()

    stat = ServiceTimeStat.objects.get(hour_of_day=10)
    assert stat.median_minutes_per_patient == pytest.approx(10, abs=1)


@pytest.mark.django_db
def test_refresh_stats_uses_median_not_mean(facility, general):
    """One ninety-minute patient must not drag the estimate for everyone."""
    start = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
    # Gaps between consecutive departures: 5, 6, 7, 6, then one 90-minute slog.
    served_at = start
    for index, gap in enumerate((0, 5, 6, 7, 6, 90)):
        served_at = served_at + timedelta(minutes=gap)
        QueueEntry.objects.create(
            facility=facility,
            service_type=general,
            walk_in_name=f"Patient {index}",
            joined_at=start,
            served_at=served_at,
            status=QueueEntry.Status.SERVED,
            ticket_code=f"G-{index:03d}",
        )

    refresh_service_time_stats()

    stat = ServiceTimeStat.objects.get(hour_of_day=10)
    assert stat.sample_size == 5
    # A mean would be about 23.
    assert 5 <= stat.median_minutes_per_patient <= 8


@pytest.mark.django_db
def test_an_empty_waiting_room_is_quiet_not_slow(facility, general):
    """The distinction the join time exists to make.

    Three patients are seen ten minutes apart, the clinic then empties, and
    nobody else arrives until the afternoon. Measured on the clock alone that
    looks like one appalling three-hour service. It was nothing of the kind -
    there was no one to serve, and counting it would make a quiet morning read
    as a catastrophic afternoon.
    """
    start = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)

    # Morning: three people already waiting, served ten minutes apart.
    for index, offset in enumerate((0, 10, 20)):
        QueueEntry.objects.create(
            facility=facility,
            service_type=general,
            walk_in_name=f"Morning {index}",
            joined_at=start,
            served_at=start + timedelta(minutes=offset),
            status=QueueEntry.Status.SERVED,
            ticket_code=f"G-{index:03d}",
        )

    # Afternoon: they arrive AFTER the waiting room emptied, so the gap in
    # between was idle rather than slow.
    afternoon = start + timedelta(minutes=180)
    for index, offset in enumerate((0, 10)):
        QueueEntry.objects.create(
            facility=facility,
            service_type=general,
            walk_in_name=f"Afternoon {index}",
            joined_at=afternoon,
            served_at=afternoon + timedelta(minutes=offset),
            status=QueueEntry.Status.SERVED,
            ticket_code=f"G-1{index:02d}",
        )

    refresh_service_time_stats()

    # Only the real ten-minute intervals survive - two in the morning hour, one
    # in the afternoon. The three-hour lull between them is nowhere.
    rates = list(
        ServiceTimeStat.objects.values_list("median_minutes_per_patient", flat=True)
    )
    assert rates == [10.0, 10.0]
    assert sum(ServiceTimeStat.objects.values_list("sample_size", flat=True)) == 3


@pytest.mark.django_db
def test_a_genuinely_long_consultation_is_still_counted(facility, general):
    """The other side of the same rule.

    Ninety minutes with somebody sitting in the waiting room is slow service,
    and it has to count - otherwise the estimate flatters a clinic exactly
    where patients most need the truth. A fixed "too long to be real" cutoff
    could not tell this apart from the case above; the join time can.
    """
    start = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
    for index, offset in enumerate((0, 90)):
        QueueEntry.objects.create(
            facility=facility,
            service_type=general,
            walk_in_name=f"Patient {index}",
            joined_at=start,  # both waiting from the outset
            served_at=start + timedelta(minutes=offset),
            status=QueueEntry.Status.SERVED,
            ticket_code=f"G-{index:03d}",
        )

    refresh_service_time_stats()

    assert ServiceTimeStat.objects.get().median_minutes_per_patient == 90.0


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


# --------------------------------------------------------------------------
# The hour boundary
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_wait_survives_the_clock_rolling_into_the_next_hour(
    facility, general, make_entry, make_stat
):
    """Fourteen tests failed at exactly midnight and passed four minutes later.

    ServiceTimeStat is keyed per hour of day. A test that wrote its stat at
    23:59:59 and asserted at 00:00:00 wrote hour 23, looked up hour 0, found
    nothing, and reported the wait as unavailable - so the suite was a coin
    flip for one second in every hour, and a guaranteed failure for anybody
    running it across midnight.

    This pins the fix rather than the symptom: the snapshot is taken an hour
    after the stat was written, and still finds one. `wait_snapshot` already
    accepts `now` for exactly this kind of question, so no clock is patched.
    """
    facility.reports_queue = True
    facility.save()
    make_stat(facility, general, median=8.0, samples=120)
    for offset in (30, 20, 10):
        make_entry(facility, general, minutes_ago=offset)

    an_hour_later = timezone.localtime() + timedelta(hours=1)
    snapshot = wait_snapshot(
        [facility], service_code="general_consultation", now=an_hour_later
    )

    assert snapshot[facility.id]["status"] == STATUS_AVAILABLE
    assert snapshot[facility.id]["minutes"] == 24


@pytest.mark.django_db
def test_the_eta_a_patient_is_shown_matches_the_wait_they_get(
    facility, general, settings
):
    """The property the product actually sells, and nothing asserted it.

    Every other test here checks a piece - the median, the sample gate, the
    position count. None of them checked that the number on the patient's
    screen resembles the wait they then experience, which is why an
    eight-fold error survived a suite of 585 tests.

    A clinic that serves one patient every 10 minutes, with five people ahead,
    is a 50-minute wait. Before this fix the same setup was shown as roughly
    440 minutes.
    """
    # The gate is a separate rule with its own tests; this one is about the
    # arithmetic, so let a short history through.
    settings.MIN_SERVICE_TIME_SAMPLES = 3

    _run_clinic(facility, general, served_every=10, arrive_every=6, count=30)
    refresh_service_time_stats()

    now = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
    for index in range(6):
        QueueEntry.objects.create(
            facility=facility,
            service_type=general,
            walk_in_name=f"Waiting {index}",
            joined_at=now + timedelta(seconds=index),
            status=QueueEntry.Status.WAITING,
            ticket_code=f"W-{index:03d}",
        )

    last = QueueEntry.objects.filter(status=QueueEntry.Status.WAITING).last()
    estimate = eta_for(last, now=now)

    assert estimate["people_ahead"] == 5
    # Five people ahead at ten minutes each. Allow a little slack for the
    # median landing a minute either side of the true rate.
    assert 40 <= estimate["eta_minutes"] <= 60


@pytest.mark.django_db
def test_parallel_services_are_not_multiplied_together(
    facility, general, maternity, settings
):
    """Two queues at one site run side by side.

    The facility-level estimate used to multiply EVERY waiting patient in the
    building by a single service's rate, describing a wait nobody was in. At a
    referral hospital with a dozen services that is out by close to an order of
    magnitude. The answer a patient can act on is the longest of the real
    per-service waits.
    """
    settings.MIN_SERVICE_TIME_SAMPLES = 5
    facility.reports_queue = True
    facility.save(update_fields=["reports_queue"])

    now = timezone.localtime()
    for service, waiting, rate in ((general, 4, 10.0), (maternity, 2, 5.0)):
        ServiceTimeStat.objects.create(
            facility=facility,
            service_type=service,
            hour_of_day=now.hour,
            median_minutes_per_patient=rate,
            sample_size=50,
        )
        for index in range(waiting):
            QueueEntry.objects.create(
                facility=facility,
                service_type=service,
                walk_in_name=f"{service.code}-{index}",
                joined_at=now,
                status=QueueEntry.Status.WAITING,
                ticket_code=f"{service.code[:1].upper()}-{index:03d}",
            )

    snapshot = wait_snapshot([facility], now=now)[facility.id]

    # general: 4 x 10 = 40. maternity: 2 x 5 = 10. Longest real wait is 40.
    # The old code did (4 + 2) x 10 = 60 - a queue of six that never existed.
    assert snapshot["minutes"] == 40
    # The head count is still everyone on site.
    assert snapshot["people_waiting"] == 6
