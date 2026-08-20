"""Validate a triage protocol before it is deployed.

Run this as part of the clinician sign-off: it proves the file the clinician
reviewed is the file the system will load, and that no option leads a patient
to a dead end.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.triage.protocol import ProtocolError, parse


class Command(BaseCommand):
    help = "Validate a triage protocol file."

    def add_arguments(self, parser):
        parser.add_argument("path", type=str)

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            raise CommandError(f"Not found: {path}")

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            protocol = parse(raw, source=path.name)
        except (ValueError, ProtocolError) as exc:
            raise CommandError(str(exc)) from exc

        red_flags = protocol.red_flag_questions
        services = sorted(
            {
                option.recommend_service
                for question in protocol.questions.values()
                for option in question.options
                if option.recommend_service
            }
        )

        self.stdout.write(self.style.SUCCESS(f"Valid: {path.name}"))
        self.stdout.write(f"  version           {protocol.version}")
        self.stdout.write(f"  questions         {len(protocol.questions)}")
        self.stdout.write(f"  red-flag screens  {len(red_flags)}")
        self.stdout.write(f"  services routed   {', '.join(services) or 'none'}")

        if not red_flags:
            self.stdout.write(
                self.style.WARNING(
                    "  WARNING: no red-flag questions. A protocol with no "
                    "emergency screening can send an emergency home."
                )
            )

        # Cross-check against the directory: a recommendation the facility
        # search cannot act on is useless to the patient.
        from apps.facilities.models import ServiceType

        known = set(ServiceType.objects.values_list("code", flat=True))
        if known:
            unknown = [code for code in services if code not in known]
            if unknown:
                self.stdout.write(
                    self.style.ERROR(
                        f"  ERROR: unknown ServiceType codes: {unknown}"
                    )
                )
                raise CommandError("Protocol routes to services that do not exist.")

        self.stdout.write(
            "\nValidation is not clinical review. This command checks structure "
            "only.\nA licensed clinician must review the content itself."
        )
