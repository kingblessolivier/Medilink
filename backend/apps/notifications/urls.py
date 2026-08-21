from django.urls import path

from . import views

urlpatterns = [
    path("me/notifications", views.notifications, name="notification-list"),
    path(
        "me/notification-preferences",
        views.preferences,
        name="notification-preferences",
    ),
]
