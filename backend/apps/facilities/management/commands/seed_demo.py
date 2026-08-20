"""Development-only seeding.

Attaches plausible opening hours, services and insurers to the loaded fixture
facilities and marks them verified, so a developer sees a working app on first
run rather than an empty list.

The coordinates it verifies are APPROXIMATE. Never run this against production.
"""

import random
from datetime import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.facilities.models import Facility, FacilityService, OpeningHours, ServiceType
from apps.insurance.models import FacilityInsurer, Insurer
from apps.providers.models import Provider, ProviderFacility, Specialty

WEEKDAYS_MON_FRI = [0, 1, 2, 3, 4]

# Service mix by facility level, mirroring what these levels actually offer.
SERVICES_BY_LEVEL = {
    "health_post": ["general_consultation", "vaccination", "antenatal"],
    "health_centre": [
        "general_consultation",
        "maternity",
        "antenatal",
        "paediatrics",
        "laboratory",
        "pharmacy",
        "vaccination",
    ],
    "district_hospital": [
        "general_consultation",
        "maternity",
        "antenatal",
        "paediatrics",
        "laboratory",
        "imaging",
        "pharmacy",
        "surgery",
        "emergency",
        "dental",
    ],
    "referral_hospital": [
        "general_consultation",
        "maternity",
        "paediatrics",
        "laboratory",
        "imaging",
        "pharmacy",
        "surgery",
        "emergency",
        "dental",
        "ophthalmology",
        "mental_health",
        "physiotherapy",
    ],
    "clinic": [
        "general_consultation",
        "laboratory",
        "imaging",
        "pharmacy",
        "dental",
    ],
    "pharmacy": ["pharmacy"],
}

# Public facilities take the public schemes; private ones vary.
INSURERS_BY_OWNERSHIP = {
    "public": ["mutuelle", "rssb", "mmi"],
    "faith_based": ["mutuelle", "rssb"],
    "private": ["rssb", "radiant", "britam", "cash"],
}


class Command(BaseCommand):
    help = "Seed development data: hours, services, insurers, verification."

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed", type=int, default=42, help="RNG seed for reproducible data."
        )
        parser.add_argument(
            "--no-verify",
            action="store_true",
            help="Attach data but leave facilities unverified (hidden from search).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(options["seed"])

        facilities = list(Facility.objects.all())
        if not facilities:
            raise CommandError(
                "No facilities found. Run:\n"
                "  python manage.py loaddata fixtures/kigali_facilities.json"
            )

        service_types = {s.code: s for s in ServiceType.objects.all()}
        insurers = {i.code: i for i in Insurer.objects.all()}
        if not service_types or not insurers:
            raise CommandError(
                "Reference data missing. Run:\n"
                "  python manage.py loaddata fixtures/insurers.json\n"
                "  python manage.py loaddata fixtures/service_types.json"
            )

        self.stdout.write(
            self.style.WARNING(
                "\n  WARNING: seed_demo marks facilities verified using "
                "APPROXIMATE coordinates.\n"
                "  This is development data only. See backend/fixtures/README.md.\n"
            )
        )

        hours_created = services_created = insurers_created = 0

        for facility in facilities:
            hours_created += self._seed_hours(facility)
            services_created += self._seed_services(facility, service_types)
            insurers_created += self._seed_insurers(facility, insurers)

        providers_made = self._seed_providers(facilities, service_types)

        verified = 0
        if not options["no_verify"]:
            verified = Facility.objects.filter(verified_at__isnull=True).update(
                verified_at=timezone.now()
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(facilities)} facilities: "
                f"{hours_created} opening-hour rows, "
                f"{services_created} services, "
                f"{insurers_created} insurer links, "
                f"{providers_made} doctors, "
                f"{verified} marked verified."
            )
        )
        self.stdout.write(
            "\nTry it:\n"
            "  curl 'http://localhost:8000/api/v1/facilities/nearby"
            "?lat=-1.9536&lng=30.0606&insurer=mutuelle'\n"
        )

    def _seed_hours(self, facility) -> int:
        if facility.opening_hours.exists():
            return 0

        created = 0
        if facility.level == "referral_hospital":
            # Emergency departments run around the clock.
            for weekday in range(7):
                OpeningHours.objects.create(
                    facility=facility,
                    weekday=weekday,
                    opens_at=time(0, 0),
                    closes_at=time(23, 59),
                )
                created += 1
            return created

        if facility.level == "district_hospital":
            for weekday in range(7):
                OpeningHours.objects.create(
                    facility=facility,
                    weekday=weekday,
                    opens_at=time(7, 0),
                    closes_at=time(20, 0),
                )
                created += 1
            return created

        # Health centres, posts and clinics: weekdays with a lunch break,
        # short Saturday, closed Sunday.
        for weekday in WEEKDAYS_MON_FRI:
            OpeningHours.objects.create(
                facility=facility,
                weekday=weekday,
                opens_at=time(7, 0),
                closes_at=time(12, 0),
            )
            OpeningHours.objects.create(
                facility=facility,
                weekday=weekday,
                opens_at=time(13, 0),
                closes_at=time(17, 0),
            )
            created += 2

        OpeningHours.objects.create(
            facility=facility, weekday=5, opens_at=time(8, 0), closes_at=time(12, 0)
        )
        return created + 1

    def _seed_services(self, facility, service_types) -> int:
        codes = SERVICES_BY_LEVEL.get(facility.level, ["general_consultation"])
        created = 0
        for code in codes:
            service_type = service_types.get(code)
            if service_type is None:
                continue
            _, was_created = FacilityService.objects.get_or_create(
                facility=facility,
                service_type=service_type,
                defaults={"available": True},
            )
            created += int(was_created)
        return created

    def _seed_insurers(self, facility, insurers) -> int:
        codes = INSURERS_BY_OWNERSHIP.get(facility.ownership, ["cash"])
        created = 0
        for code in codes:
            insurer = insurers.get(code)
            if insurer is None:
                continue
            _, was_created = FacilityInsurer.objects.get_or_create(
                facility=facility,
                insurer=insurer,
                defaults={"confirmed_at": timezone.now()},
            )
            created += int(was_created)
        return created

    # Plausible Rwandan names for demo doctors. Clearly demo data: every one
    # is created unverified, so none of them reaches patient-facing search
    # until a human confirms the placement with the facility.
    DEMO_NAMES = [
        "Uwase Alice", "Mugisha Jean", "Keza Diane", "Habimana Eric",
        "Ingabire Claudine", "Niyonsaba Patrick", "Umutoni Sandrine",
        "Nshimiyimana Olivier", "Mukamana Josiane", "Bizimana Thierry",
        "Uwimana Chantal", "Kayitesi Solange",
    ]

    def _seed_providers(self, facilities, service_types) -> int:
        specialties = list(Specialty.objects.prefetch_related("service_types"))
        if not specialties:
            self.stdout.write(
                self.style.WARNING(
                    "  No specialties loaded - skipping doctors. Run: "
                    "python manage.py loaddata fixtures/specialties.json"
                )
            )
            return 0

        if Provider.objects.exists():
            return 0

        made = 0
        for index, name in enumerate(self.DEMO_NAMES):
            specialty = specialties[index % len(specialties)]
            # Place each doctor at a facility that actually offers one of
            # their specialty's services - a cardiologist at a dental clinic
            # would be nonsense data that makes the directory untrustworthy.
            codes = {s.code for s in specialty.service_types.all()}
            candidates = [
                f
                for f in facilities
                if codes & {fs.service_type.code for fs in f.services.all()}
            ]
            if not candidates:
                continue

            facility = candidates[index % len(candidates)]
            provider = Provider.objects.create(
                slug=f"demo-{name.lower().replace(' ', '-')}",
                full_name=name,
                title=Provider.Title.DR,
                languages=["rw", "en"] if index % 2 == 0 else ["rw", "en", "fr"],
                bio_en="",
            )
            provider.specialties.add(specialty)

            placement = ProviderFacility.objects.create(
                provider=provider, facility=facility
            )
            placement.service_types.set(
                [
                    fs.service_type
                    for fs in facility.services.all()
                    if fs.service_type.code in codes
                ]
            )
            made += 1

        if made:
            self.stdout.write(
                self.style.WARNING(
                    f"  {made} DEMO doctors created, all unverified. They will "
                    "not appear as verified until a human confirms each "
                    "placement with the facility."
                )
            )
        return made
