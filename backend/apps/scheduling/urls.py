from django.urls import path

from . import views

urlpatterns = [
    path("facilities/<slug:slug>/slots", views.slots, name="facility-slots"),
    # GET lists, POST books - one path, as docs/03 specifies.
    path("appointments", views.appointments, name="appointments"),
    path(
        "appointments/<int:pk>/cancel",
        views.cancel_appointment,
        name="appointment-cancel",
    ),
]
