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
    # What this facility accepts. The facility maintains it, because the
    # facility runs the counter that takes the card.
    path("staff/insurance", views.insurance, name="staff-insurance"),
    path(
        "staff/insurance/<slug:code>",
        views.set_insurer,
        name="staff-insurance-set",
    ),
    path(
        "staff/insurance/<slug:code>/services/<slug:service>",
        views.set_coverage,
        name="staff-insurance-coverage",
    ),
    # Contact details and opening hours. Name, level and coordinates are NOT
    # here - those are what verification attests to.
    path("staff/facility", views.facility_settings, name="staff-facility"),
    path(
        "staff/facility/contact",
        views.update_facility_contact,
        name="staff-facility-contact",
    ),
    path("staff/facility/hours", views.replace_opening_hours, name="staff-hours"),
    # Scoped to this facility's own patients, logged, and throttled.
    path("staff/patients", views.patient_lookup, name="staff-patients"),
    # FA-10. Administrators only - see IsFacilityAdmin.
    path("staff/team", views.team, name="staff-team"),
    path("staff/team/<int:pk>", views.team_member, name="staff-team-member"),
]
