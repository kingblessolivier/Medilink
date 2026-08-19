"""Celery bindings for queue maintenance."""

from apps.queueing.services import refresh_service_time_stats

try:
    from celery import shared_task
except ImportError:  # pragma: no cover
    shared_task = None

if shared_task is not None:

    @shared_task(name="queueing.refresh_stats")
    def refresh_stats_task():
        return refresh_service_time_stats()
