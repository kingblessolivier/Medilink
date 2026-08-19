from django.urls import path

from . import views

urlpatterns = [
    path("auth/otp/request", views.otp_request, name="otp-request"),
    path("auth/otp/verify", views.otp_verify, name="otp-verify"),
    path("me", views.me, name="patient-me"),
]
