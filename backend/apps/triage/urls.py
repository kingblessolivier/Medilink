from django.urls import path

from . import views

urlpatterns = [
    path("triage/status", views.status_view, name="triage-status"),
    path("triage/sessions", views.create_session, name="triage-create"),
    path(
        "triage/sessions/<str:session_id>/answer",
        views.answer_question,
        name="triage-answer",
    ),
]
