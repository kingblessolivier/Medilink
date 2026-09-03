"""FA-10: staff accounts.

This is the one workspace endpoint that grants access rather than using it, so
the tests here are mostly about who is refused and how a facility avoids
locking itself out - not about the happy path, which is three lines.
"""

import pytest
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient

from apps.facilities.models import Facility
from apps.staff.models import StaffMember

LIST = "/api/v1/staff/team"


# Fixtures are local, matching test_workspace.py beside this file: apps/staff
# has no conftest, and the shared ones live under apps/queueing/tests where
# pytest will not see them from here.


def _make_facility(name, slug):
    return Facility.objects.create(
        name=name,
        slug=slug,
        ownership="public",
        level="health_centre",
        district="Gasabo",
        location=Point(30.11, -1.94, srid=4326),
        verified_at=timezone.now(),
        reports_queue=True,
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def facility(db):
    return _make_facility("Kimironko HC", "kimironko-hc")


@pytest.fixture
def other_facility(db):
    return _make_facility("Remera HC", "remera-hc")


@pytest.fixture
def other_receptionist(other_facility):
    """A receptionist at a DIFFERENT facility. Every scoping assertion here
    turns on this account being invisible and untouchable."""
    user = User.objects.create_user("other-desk", password="pw-for-tests")
    StaffMember.objects.create(
        user=user,
        facility=other_facility,
        role=StaffMember.Role.RECEPTIONIST,
        active=True,
    )
    return user


def member_url(pk: int) -> str:
    return f"/api/v1/staff/team/{pk}"


@pytest.fixture
def admin_member(facility):
    user = User.objects.create_user("fa-admin", password="x", first_name="Ada")
    return StaffMember.objects.create(
        user=user, facility=facility, role=StaffMember.Role.ADMIN, active=True
    )


@pytest.fixture
def receptionist_member(facility):
    user = User.objects.create_user("fa-desk", password="x")
    return StaffMember.objects.create(
        user=user, facility=facility, role=StaffMember.Role.RECEPTIONIST, active=True
    )


# --------------------------------------------------------------- who may act


@pytest.mark.django_db
def test_anonymous_is_rejected(api_client):
    assert api_client.get(LIST).status_code in (401, 403)


@pytest.mark.django_db
def test_receptionist_cannot_manage_accounts(api_client, receptionist_member):
    """The whole reason this is not gated on `can_manage_queue`.

    A receptionist moves the queue all day. Minting accounts is a different
    power, and the dashboards spec says so from the other side: "Receptionist
    sees FA-03 and FA-06 only".
    """
    api_client.force_authenticate(receptionist_member.user)

    assert api_client.get(LIST).status_code == 403
    assert (
        api_client.post(
            LIST, {"username": "sneaky", "role": "admin"}, format="json"
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_admin_sees_only_their_own_facility(
    api_client, admin_member, other_receptionist
):
    """The leak this file exists for.

    `other_receptionist` belongs to a different facility and must not appear.
    """
    api_client.force_authenticate(admin_member.user)

    response = api_client.get(LIST)

    assert response.status_code == 200
    usernames = {row["username"] for row in response.data}
    assert admin_member.user.username in usernames
    assert other_receptionist.username not in usernames


@pytest.mark.django_db
def test_admin_cannot_touch_another_facilitys_account(
    api_client, admin_member, other_receptionist
):
    """404, not 403: an enumerated id must not confirm the account exists."""
    api_client.force_authenticate(admin_member.user)
    target = other_receptionist.staffmember

    response = api_client.patch(
        member_url(target.pk), {"active": False}, format="json"
    )

    assert response.status_code == 404
    target.refresh_from_db()
    assert target.active is True


# ------------------------------------------------------------------ creating


@pytest.mark.django_db
def test_creates_an_account_at_the_callers_facility(api_client, admin_member):
    api_client.force_authenticate(admin_member.user)

    response = api_client.post(
        LIST,
        {"username": "new-desk", "full_name": "Mukamana Jeanne", "role": "receptionist"},
        format="json",
    )

    assert response.status_code == 201
    created = StaffMember.objects.get(user__username="new-desk")
    # Facility is never taken from the payload - it comes from the caller.
    assert created.facility_id == admin_member.facility_id
    assert created.role == StaffMember.Role.RECEPTIONIST
    assert created.active is True


@pytest.mark.django_db
def test_the_temporary_password_is_returned_once_and_works(
    api_client, admin_member
):
    api_client.force_authenticate(admin_member.user)

    response = api_client.post(
        LIST, {"username": "new-desk", "role": "receptionist"}, format="json"
    )
    password = response.data["temporary_password"]

    # It is a real credential, not a placeholder.
    assert User.objects.get(username="new-desk").check_password(password)

    # And it is never shown again.
    listed = api_client.get(LIST).data
    row = next(r for r in listed if r["username"] == "new-desk")
    assert "temporary_password" not in row


@pytest.mark.django_db
def test_facility_in_the_payload_is_ignored(api_client, admin_member, other_facility):
    """Belt and braces: the serializer has no `facility` field, so a supplied
    one is dropped rather than honoured."""
    api_client.force_authenticate(admin_member.user)

    api_client.post(
        LIST,
        {
            "username": "new-desk",
            "role": "receptionist",
            "facility": other_facility.id,
        },
        format="json",
    )

    assert (
        StaffMember.objects.get(user__username="new-desk").facility_id
        == admin_member.facility_id
    )


@pytest.mark.django_db
def test_duplicate_username_is_refused(api_client, admin_member):
    api_client.force_authenticate(admin_member.user)
    User.objects.create_user("taken", password="x")

    response = api_client.post(
        LIST, {"username": "taken", "role": "receptionist"}, format="json"
    )

    assert response.status_code == 400


# ------------------------------------------------------- lockout protections


@pytest.mark.django_db
def test_admin_cannot_switch_off_their_own_account(api_client, admin_member):
    api_client.force_authenticate(admin_member.user)

    response = api_client.patch(
        member_url(admin_member.pk), {"active": False}, format="json"
    )

    assert response.status_code == 400
    admin_member.refresh_from_db()
    assert admin_member.active is True


@pytest.mark.django_db
def test_admin_cannot_demote_themselves(api_client, admin_member):
    """The same lockout by a slower route - demote yourself, and nobody at the
    facility can undo it."""
    api_client.force_authenticate(admin_member.user)

    response = api_client.patch(
        member_url(admin_member.pk), {"role": "receptionist"}, format="json"
    )

    assert response.status_code == 400
    admin_member.refresh_from_db()
    assert admin_member.role == StaffMember.Role.ADMIN


@pytest.mark.django_db
def test_the_last_active_admin_cannot_be_switched_off(
    api_client, admin_member, facility
):
    """A second admin switching off the first is fine. Switching off the only
    one left is not - that facility would need a developer to get back in."""
    other = User.objects.create_user("fa-admin-2", password="x")
    second = StaffMember.objects.create(
        user=other, facility=facility, role=StaffMember.Role.ADMIN, active=True
    )
    api_client.force_authenticate(other)

    # Two admins: switching one off is allowed.
    assert (
        api_client.patch(
            member_url(admin_member.pk), {"active": False}, format="json"
        ).status_code
        == 200
    )

    # Now `second` is the only one left, and cannot remove itself.
    assert (
        api_client.patch(
            member_url(second.pk), {"active": False}, format="json"
        ).status_code
        == 400
    )


@pytest.mark.django_db
def test_role_change_is_applied(api_client, admin_member, receptionist_member):
    api_client.force_authenticate(admin_member.user)

    response = api_client.patch(
        member_url(receptionist_member.pk), {"role": "clinician"}, format="json"
    )

    assert response.status_code == 200
    receptionist_member.refresh_from_db()
    assert receptionist_member.role == StaffMember.Role.CLINICIAN


@pytest.mark.django_db
def test_an_empty_patch_is_refused(api_client, admin_member, receptionist_member):
    api_client.force_authenticate(admin_member.user)

    assert (
        api_client.patch(
            member_url(receptionist_member.pk), {}, format="json"
        ).status_code
        == 400
    )
