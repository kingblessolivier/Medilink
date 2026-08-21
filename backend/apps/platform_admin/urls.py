from django.urls import path

from . import views

# "platform-admin", not "admin": /admin/ is Django admin, and a path collision
# between the two would be a confusing place to discover a routing bug.
urlpatterns = [
    path("platform/overview", views.admin_overview, name="admin-overview"),
    path(
        "platform/verification",
        views.admin_verification_queue,
        name="admin-verification-queue",
    ),
    path(
        "platform/verification/facilities/<int:pk>",
        views.verify_facility,
        name="admin-verify-facility",
    ),
    path(
        "platform/verification/providers/<int:pk>",
        views.verify_provider,
        name="admin-verify-provider",
    ),
    path(
        "platform/triage-monitoring",
        views.admin_triage_monitoring,
        name="admin-triage-monitoring",
    ),
]
