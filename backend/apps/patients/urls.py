from django.urls import path

from . import views

urlpatterns = [
    path("auth/otp/request", views.otp_request, name="otp-request"),
    path("auth/otp/verify", views.otp_verify, name="otp-verify"),
    # GET reads, PATCH updates, DELETE erases - as docs/03 specifies.
    path("me", views.me, name="patient-me"),
    path("me/export", views.export_me, name="patient-export"),
]
