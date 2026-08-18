from django.urls import path

from . import views

urlpatterns = [
    path("insurers", views.insurers, name="insurers"),
]
