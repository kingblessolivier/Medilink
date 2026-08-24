"""Send whatever is due right now.

Run every minute from cron during the Phase 2 pilot:

    * * * * * cd /srv/medilink/backend && python manage.py send_due_notifications

Celery beat replaces this once the pilot is stable - one fewer moving part at a
health centre with unreliable power.

Safe to overlap: dispatch() creates the Notification row first and the unique
constraint rejects duplicates.
"""

from django.core.management.base import BaseCommand

from apps.notifications.tasks import run_all


class Command(BaseCommand):
    help = "Send due leave-now nudges and appointment reminders."

    def handle(self, *args, **options):
        result = run_all()
        self.stdout.write(
            self.style.SUCCESS(
                f"leave_now={result['leave_now']} "
                f"reminders={result['reminders']} "
                f"no_shows={result['no_shows']} "
                f"unrecorded={result['unrecorded']}"
            )
        )
