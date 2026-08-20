from django.urls import path

from . import views

urlpatterns = [
    path("specialties", views.specialties, name="specialties"),
    path("providers", views.provider_list, name="provider-list"),
    path("providers/<slug:slug>", views.provider_detail, name="provider-detail"),
    path(
        "facilities/<slug:slug>/providers",
        views.facility_providers,
        name="facility-providers",
    ),
]
