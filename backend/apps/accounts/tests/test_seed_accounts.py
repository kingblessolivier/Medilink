"""The demo-account seeder.

Two properties matter. It must never run outside development, and running it
twice must leave the same five accounts rather than a pile of duplicates.
"""

import pytest
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.facilities.models import Facility, ServiceType
from apps.patients.models import Patient
from apps.queueing.models import QueueEntry
from apps.staff.models import StaffMember

PASSWORD = "demo-pass-123"


@pytest.fixture
def quiet_facility(db):
    return Facility.objects.create(
        name="Quiet HC",
        slug="quiet-hc",
        ownership="public",
        level="health_centre",
        district="Gasabo",
        location=Point(30.0606, -1.9536, srid=4326),
        verified_at=timezone.now(),
        reports_queue=False,
    )


@pytest.fixture
def busy_facility(db):
    return Facility.objects.create(
        name="Busy HC",
        slug="busy-hc",
        ownership="public",
        level="health_centre",
        district="Gasabo",
        location=Point(30.0606, -1.9536, srid=4326),
        verified_at=timezone.now(),
        reports_queue=True,
    )


@pytest.fixture
def patient(db):
    return Patient.objects.create(phone="+250788000111", full_name="Seeded Patient")


@pytest.mark.django_db
def test_it_refuses_to_run_with_debug_off(settings, busy_facility, patient):
    """A command that sets known passwords must not be one `--help` away from
    running against production."""
    settings.DEBUG = False

    with pytest.raises(CommandError, match="DEBUG"):
        call_command("seed_accounts")

    assert not User.objects.filter(username="reception").exists()


@pytest.mark.django_db
def test_it_creates_one_account_per_user_type(settings, busy_facility, patient):
    settings.DEBUG = True

    call_command("seed_accounts")

    roles = dict(StaffMember.objects.values_list("user__username", "role"))
    assert roles == {
        "reception": StaffMember.Role.RECEPTIONIST,
        "clinician": StaffMember.Role.CLINICIAN,
        "facility-admin": StaffMember.Role.ADMIN,
    }
    assert User.objects.get(username="platform").is_superuser
    assert Patient.objects.get(username="patient").check_password(PASSWORD)

    for username in ("reception", "clinician", "facility-admin", "platform"):
        assert User.objects.get(username=username).check_password(PASSWORD)


@pytest.mark.django_db
def test_running_it_twice_changes_nothing(settings, busy_facility, patient):
    """Idempotent, because it is the thing you run when you are not sure
    whether you already ran it."""
    settings.DEBUG = True

    call_command("seed_accounts")
    before = set(User.objects.values_list("username", flat=True))

    call_command("seed_accounts")

    assert set(User.objects.values_list("username", flat=True)) == before
    assert StaffMember.objects.count() == 3
    assert Patient.objects.filter(username="patient").count() == 1


@pytest.mark.django_db
def test_staff_land_at_the_facility_with_a_queue(
    settings, quiet_facility, busy_facility, patient
):
    """A receptionist attached to a facility with no queue sees an empty
    workspace, which reads as a broken app rather than an idle facility."""
    settings.DEBUG = True
    service_type = ServiceType.objects.create(
        code="general_consultation", name_en="General", name_rw="x", name_fr="x"
    )
    QueueEntry.objects.create(
        facility=busy_facility,
        service_type=service_type,
        walk_in_name="Someone",
        ticket_code="G-001",
    )

    call_command("seed_accounts")

    assert (
        StaffMember.objects.get(user__username="reception").facility
        == busy_facility
    )


@pytest.mark.django_db
def test_the_platform_admin_is_not_also_facility_staff(
    settings, busy_facility, patient
):
    """Sign-in routes on what the account IS. A superuser who is also staff
    routes to the workspace, and the portal then looks broken."""
    settings.DEBUG = True
    admin = User.objects.create_user(username="platform", password="x")
    StaffMember.objects.create(
        user=admin, facility=busy_facility, role=StaffMember.Role.RECEPTIONIST
    )

    call_command("seed_accounts")

    assert not StaffMember.objects.filter(user__username="platform").exists()


@pytest.mark.django_db
def test_it_says_so_when_there_is_nothing_to_attach_to(settings, patient):
    settings.DEBUG = True

    with pytest.raises(CommandError, match="No verified facility"):
        call_command("seed_accounts")
