from django.urls import path

from . import views

urlpatterns = [
    path("search", views.global_search, name="global-search"),
]
