"""Produce the document a clinician signs.

docs/08 section 8 requires the symptom checker to be "reviewed and signed off
by a licensed clinician, with the sign-off recorded against a
`protocol_version`". Nothing produced the thing they sign. The protocol is a
graph in a JSON file, and asking a clinician to trace `next_question` pointers
through it is asking them to do a compiler's job before they can start their
own.

    python manage.py export_triage_review apps/triage/protocols/routing.2026.1.json
    python manage.py export_triage_review <file> --lang rw --output review.rw.txt

Run it once per language. The patient reads Kinyarwanda first, so the
Kinyarwanda document is the one that matters most, and it is the one most
likely to contain a translation that changed the clinical meaning.

This validates before it renders: an unsigned protocol that does not parse is
not worth a reviewer's afternoon.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.triage.protocol import REQUIRED_LANGUAGES, ProtocolError, parse
from apps.triage.review import MAX_PATHS, render


class Command(BaseCommand):
    help = "Render a triage protocol as a clinician review document."

    def add_arguments(self, parser):
        parser.add_argument("path", type=str, help="Protocol JSON file.")
        parser.add_argument(
            "--lang",
            default="en",
            choices=list(REQUIRED_LANGUAGES),
            help="Language to render the patient-facing text in.",
        )
        parser.add_argument(
            "--output",
            default="",
            help="Write to this file instead of stdout.",
        )
        parser.add_argument(
            "--max-paths",
            type=int,
            default=MAX_PATHS,
            help=f"Stop after this many paths (default {MAX_PATHS}).",
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            raise CommandError(f"Not found: {path}")

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            protocol = parse(raw, source=str(path))
        except (ValueError, ProtocolError) as exc:
            raise CommandError(f"Protocol does not parse, so it cannot be reviewed: {exc}") from exc

        # The directory is the other half of the coverage picture. Imported
        # here rather than at module scope to keep the triage app's import
        # graph free of a hard dependency on facilities.
        from django.db import OperationalError, ProgrammingError

        from apps.facilities.models import ServiceType

        # A reviewer generating this on a laptop has a protocol file and no
        # database. That is a perfectly good reason to run the command, so an
        # unreachable database costs the coverage section and nothing else -
        # the paths, the red flags and the sign-off block are all derived from
        # the file alone. Crashing here would make the document unobtainable
        # in exactly the situation it is most needed.
        try:
            known = set(ServiceType.objects.values_list("code", flat=True))
        except (OperationalError, ProgrammingError) as exc:
            known = set()
            self.stderr.write(
                self.style.WARNING(
                    f"No database ({exc.__class__.__name__}), so the service "
                    "coverage section is omitted. Everything else is derived "
                    "from the protocol file and is complete."
                )
            )
        else:
            if not known:
                self.stderr.write(
                    self.style.WARNING(
                        "No ServiceType rows in this database, so the coverage "
                        "section is omitted. Run against a seeded database to "
                        "see which services the protocol cannot reach."
                    )
                )

        document = render(
            protocol,
            lang=options["lang"],
            known_service_codes=known or None,
            limit=options["max_paths"],
        )

        destination = options["output"]
        if destination:
            Path(destination).write_text(document, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Written: {destination}"))
        else:
            self.stdout.write(document)
