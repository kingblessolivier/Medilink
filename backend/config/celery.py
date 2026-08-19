"""Celery application.

Phase 2 can run on plain cron via `manage.py send_due_notifications`; Celery
beat replaces it once the pilot facility is stable. Both call the same
functions in apps.notifications.tasks, so behaviour cannot diverge.
"""

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("medilink")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # Every minute: a patient told to leave five minutes late has lost
    # their place in the queue.
    "send-due-notifications": {
        "task": "notifications.run_due",
        "schedule": crontab(minute="*"),
    },
    # Quarter-hourly is ample for medians over a 30-day window.
    "refresh-service-stats": {
        "task": "queueing.refresh_stats",
        "schedule": crontab(minute="*/15"),
    },
}
