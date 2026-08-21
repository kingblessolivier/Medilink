from django.apps import AppConfig


class PlatformAdminConfig(AppConfig):
    name = "apps.platform_admin"
    # "admin" is taken by django.contrib.admin, and this is not that: Django
    # admin does CRUD on every model, while this app serves the three things
    # it cannot - a verification workflow, platform aggregates, and triage
    # monitoring that must never touch an answer.
    label = "platform_admin"
