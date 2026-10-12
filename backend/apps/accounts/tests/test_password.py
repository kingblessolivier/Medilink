import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.mark.django_db
def test_password_change_revokes_old_access_and_refresh():
    user = User.objects.create_user("password-test", password="Old-Horse-Secret-489")
    refresh = RefreshToken.for_user(user)
    old_access, old_refresh = str(refresh.access_token), str(refresh)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_access}")
    response = client.post("/api/v1/auth/password", {
        "current_password": "Old-Horse-Secret-489",
        "new_password": "New-River-Secret-912",
    }, format="json")
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("New-River-Secret-912")
    assert client.get("/api/v1/auth/session").status_code in (401, 403)
    client.credentials()
    assert client.post("/api/v1/auth/token/refresh", {"refresh": old_refresh}, format="json").status_code == 401
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    assert client.get("/api/v1/auth/session").status_code == 200


@pytest.mark.django_db
def test_password_change_requires_current_password():
    user = User.objects.create_user("password-test", password="Old-Horse-Secret-489")
    client = APIClient()
    client.force_authenticate(user)
    response = client.post("/api/v1/auth/password", {
        "current_password": "wrong", "new_password": "New-River-Secret-912",
    }, format="json")
    assert response.status_code == 400
    user.refresh_from_db()
    assert user.check_password("Old-Horse-Secret-489")


def test_password_change_rejects_anonymous_callers():
    assert APIClient().post("/api/v1/auth/password", {}, format="json").status_code == 401
