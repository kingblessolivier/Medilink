"""Recompute ServiceTimeStat medians.

Run on a schedule - cron every 15 minutes is fine for Phase 1; Phase 2 moves it
to Celery beat alongside the notification tasks. Computing medians per request
would put a full aggregation on the hottest endpoint in the system.
"""

from django.core.management.base import BaseCommand

from apps.facilities.models import Facility
from apps.queueing.services import STATS_WINDOW_DAYS, refresh_service_time_stats


class Command(BaseCommand):
    help = "Recompute rolling median service times from served queue entries."

    def add_arguments(self, parser):
        parser.add_argument("--facility", type=str, help="Facility slug (optional).")
        parser.add_argument("--days", type=int, default=STATS_WINDOW_DAYS)

    def handle(self, *args, **options):
        facility = None
        if options["facility"]:
            facility = Facility.objects.get(slug=options["facility"])

        written = refresh_service_time_stats(
            facility=facility, window_days=options["days"]
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {written} service-time bucket(s) "
                f"from the last {options['days']} days."
            )
        )
