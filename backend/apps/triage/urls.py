from django.urls import path

from . import views

urlpatterns = [
    # One-step check: text in, conditions out. No session.
    path("triage/check", views.check, name="triage-check"),
    path("triage/status", views.status_view, name="triage-status"),
    path("triage/sessions", views.create_session, name="triage-create"),
    path(
        "triage/sessions/<str:session_id>/answer",
        views.answer_question,
        name="triage-answer",
    ),
]
