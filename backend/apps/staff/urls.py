from django.urls import path

from . import views

urlpatterns = [
    path("staff/me", views.me, name="staff-me"),
    path("staff/appointments", views.appointments, name="staff-appointments"),
    path(
        "staff/appointments/<int:pk>/status",
        views.set_appointment_status,
        name="staff-appointment-status",
    ),
    path("staff/reports", views.reports, name="staff-reports"),
]
