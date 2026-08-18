from datetime import time

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient

from apps.facilities.models import Facility, FacilityService, OpeningHours, ServiceType
from apps.insurance.models import FacilityInsurer, Insurer

# Kigali Convention Centre - the reference point for every geo assertion.
KCC_LAT = -1.9536
KCC_LNG = 30.0606


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def mutuelle(db):
    return Insurer.objects.create(code="mutuelle", name="Mutuelle de Sante")


@pytest.fixture
def rssb(db):
    return Insurer.objects.create(code="rssb", name="RSSB")


@pytest.fixture
def general(db):
    return ServiceType.objects.create(
        code="general_consultation",
        name_en="General consultation",
        name_rw="Kwivuza rusange",
        name_fr="Consultation generale",
    )


@pytest.fixture
def maternity(db):
    return ServiceType.objects.create(
        code="maternity", name_en="Maternity", name_rw="Kubyara", name_fr="Maternite"
    )


@pytest.fixture
def make_facility(db):
    """Build a verified, currently-open facility unless told otherwise."""
    counter = {"n": 0}

    def _make(
        lat,
        lng,
        *,
        name=None,
        level="health_centre",
        ownership="public",
        district="Gasabo",
        verified=True,
        open_now=True,
        insurers=(),
        services=(),
        reports_queue=False,
    ):
        counter["n"] += 1
        name = name or f"Facility {counter['n']}"
        facility = Facility.objects.create(
            name=name,
            slug=f"facility-{counter['n']}",
            ownership=ownership,
            level=level,
            district=district,
            location=Point(lng, lat, srid=4326),  # lng first
            verified_at=timezone.now() if verified else None,
            reports_queue=reports_queue,
        )

        if open_now:
            # Open every weekday, all day, so tests never depend on wall clock.
            for weekday in range(7):
                OpeningHours.objects.create(
                    facility=facility,
                    weekday=weekday,
                    opens_at=time(0, 0),
                    closes_at=time(23, 59),
                )

        for insurer in insurers:
            FacilityInsurer.objects.create(facility=facility, insurer=insurer)

        for service_type in services:
            FacilityService.objects.create(
                facility=facility, service_type=service_type, available=True
            )

        return facility

    return _make
