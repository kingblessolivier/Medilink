"""Test helpers for queue timing.

Not imported by application code. It lives here rather than in a conftest
because five different apps need it, and a conftest is only visible to its own
directory tree.
"""

from django.utils import timezone

from .models import ServiceTimeStat


def make_service_time_stat(
    facility, service_type, *, median=6.0, samples=120, hour=None
):
    """A service-time stat that the code under test will actually find.

    `ServiceTimeStat` is keyed per hour of day, and `wait_snapshot` looks up
    the hour it runs in. Writing the stat for the hour the TEST runs in opens
    an hour-boundary race: a test that sets up at 23:59:59 and asserts at
    00:00:00 writes hour 23, looks up hour 0, finds nothing, and reports the
    wait as unavailable.

    That is not theoretical. Fourteen tests failed at exactly midnight and
    passed again four minutes later, which is the worst kind of failure - it
    looks like whatever you changed last, and it is unreproducible by the time
    you go looking.

    Writing the current hour and the next one closes it. Two rows rather than
    twenty-four, because the point is to survive a rollover mid-test, not to
    pretend a facility has been measured all day.

    Pass `hour` explicitly when the test is ABOUT the per-hour lookup.
    """
    if hour is not None:
        return ServiceTimeStat.objects.create(
            facility=facility,
            service_type=service_type,
            hour_of_day=hour,
            median_minutes_per_patient=median,
            sample_size=samples,
        )

    now_hour = timezone.localtime().hour
    rows = [
        ServiceTimeStat.objects.create(
            facility=facility,
            service_type=service_type,
            hour_of_day=h,
            median_minutes_per_patient=median,
            sample_size=samples,
        )
        for h in (now_hour, (now_hour + 1) % 24)
    ]
    return rows[0]
