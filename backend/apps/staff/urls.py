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
    # The facility's own bookable hours. Until these existed, opening a
    # clinic session meant somebody editing the database on its behalf.
    path("staff/schedule", views.schedule, name="staff-schedule"),
    path("staff/schedule/new", views.create_schedule, name="staff-schedule-create"),
    path(
        "staff/schedule/<int:pk>",
        views.update_schedule,
        name="staff-schedule-update",
    ),
]
