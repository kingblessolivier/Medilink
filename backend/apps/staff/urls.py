from django.urls import path

from . import views

urlpatterns = [
    path("staff/me", views.me, name="staff-me"),
]
