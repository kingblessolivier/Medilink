"""Import the Celery app so shared_task binds to it on Django startup."""

try:
    from .celery import app as celery_app

    __all__ = ("celery_app",)
except ImportError:  # pragma: no cover - Celery is optional in development
    __all__ = ()
