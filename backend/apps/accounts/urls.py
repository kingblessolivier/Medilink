from django.urls import path

from . import views

urlpatterns = [
    path("auth/login", views.login, name="auth-login"),
    path("auth/register", views.register, name="auth-register"),
    path("auth/session", views.session, name="auth-session"),
]
