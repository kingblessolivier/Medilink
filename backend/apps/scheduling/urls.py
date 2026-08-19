from django.urls import path

from . import views

urlpatterns = [
    path("facilities/<slug:slug>/slots", views.slots, name="facility-slots"),
    path("appointments", views.list_appointments, name="appointment-list"),
    path("appointments/create", views.create_appointment, name="appointment-create"),
    path(
        "appointments/<int:pk>/cancel",
        views.cancel_appointment,
        name="appointment-cancel",
    ),
]
