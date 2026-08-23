from datetime import time, timedelta

import pytest
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient

from apps.facilities.models import Facility, FacilityService, OpeningHours, ServiceType
from apps.queueing.models import QueueEntry
from apps.queueing.testing import make_service_time_stat
from apps.staff.models import StaffMember

KCC_LAT = -1.9536
KCC_LNG = 30.0606


@pytest.fixture
def general(db):
    return ServiceType.objects.create(
        code="general_consultation",
        name_en="General consultation",
        name_rw="Kwivuza rusange",
        name_fr="Consultation generale",
        sort_order=10,
    )


@pytest.fixture
def maternity(db):
    return ServiceType.objects.create(
        code="maternity",
        name_en="Maternity",
        name_rw="Kubyara",
        name_fr="Maternite",
        sort_order=20,
    )


@pytest.fixture
def make_facility(db):
    counter = {"n": 0}

    def _make(*, name=None, open_now=True, reports_queue=False, services=()):
        counter["n"] += 1
        facility = Facility.objects.create(
            name=name or f"Facility {counter['n']}",
            slug=f"facility-{counter['n']}",
            ownership="public",
            level="health_centre",
            district="Gasabo",
            location=Point(KCC_LNG, KCC_LAT, srid=4326),
            verified_at=timezone.now(),
            reports_queue=reports_queue,
        )
        if open_now:
            for weekday in range(7):
                OpeningHours.objects.create(
                    facility=facility,
                    weekday=weekday,
                    opens_at=time(0, 0),
                    closes_at=time(23, 59),
                )
        for service_type in services:
            FacilityService.objects.create(
                facility=facility, service_type=service_type, available=True
            )
        return facility

    return _make


@pytest.fixture
def facility(make_facility, general, maternity):
    return make_facility(name="Kimironko HC", services=[general, maternity])


@pytest.fixture
def other_facility(make_facility, general):
    return make_facility(name="Remera HC", services=[general])


def _make_staff(facility, username, role=StaffMember.Role.RECEPTIONIST):
    user = User.objects.create_user(username=username, password="test-pass-123")
    StaffMember.objects.create(user=user, facility=facility, role=role)
    return user


@pytest.fixture
def receptionist(db, facility):
    return _make_staff(facility, "reception-a")


@pytest.fixture
def other_receptionist(db, other_facility):
    return _make_staff(other_facility, "reception-b")


@pytest.fixture
def clinician(db, facility):
    return _make_staff(facility, "clinician-a", role=StaffMember.Role.CLINICIAN)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def staff_client(api_client, receptionist):
    api_client.force_authenticate(receptionist)
    return api_client


@pytest.fixture
def make_entry(db):
    """Create a queue entry with an explicit joined_at, for ordering tests."""

    def _make(facility, service_type, *, minutes_ago=0, status="waiting", name="Walk"):
        return QueueEntry.objects.create(
            facility=facility,
            service_type=service_type,
            walk_in_name=name,
            joined_at=timezone.now() - timedelta(minutes=minutes_ago),
            status=status,
            ticket_code=f"T-{QueueEntry.objects.count() + 1:03d}",
        )

    return _make


@pytest.fixture
def make_stat(db):
    """A service-time stat the code under test will actually find.

    Thin wrapper over `apps.queueing.testing.make_service_time_stat` so queue
    tests can ask for one without importing it. The hour-boundary reasoning
    lives there, next to the helper the other four apps use.
    """

    def _make(facility, service_type, *, median=6.0, samples=100, hour=None):
        return make_service_time_stat(
            facility, service_type, median=median, samples=samples, hour=hour
        )

    return _make
