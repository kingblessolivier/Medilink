from django.urls import path

from . import views

urlpatterns = [
    path("facilities/nearby", views.nearby, name="facility-nearby"),
    path("facilities/<slug:slug>", views.facility_detail, name="facility-detail"),
    path("service-types", views.service_types, name="service-types"),
    path("districts", views.districts, name="districts"),
]
