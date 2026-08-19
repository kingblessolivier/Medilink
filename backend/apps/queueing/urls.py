from django.urls import path

from . import views

urlpatterns = [
    path("queue/entries", views.check_in_view, name="queue-check-in"),
    path("queue/board", views.board, name="queue-board"),
    path("queue/sync", views.sync, name="queue-sync"),
    path("queue/current", views.current_entry, name="queue-current"),
    path("queue/entries/<int:pk>", views.entry_detail, name="queue-entry"),
    path(
        "queue/entries/<int:pk>/<slug:action>",
        views.transition,
        name="queue-transition",
    ),
]
