"""`manage.py readiness` - what code can check before a launch.

docs/08 section 9 is a launch checklist. Most of it is human work: a signed
data-processing agreement, a rehearsed restore, a regulator consulted. Those
cannot be verified from here and this command does not pretend to.

What it DOES do is check the settings-level items, so that the ones a
deployment can get wrong are caught by a command rather than by a patient.

Exit code 1 if any BLOCKER fails, so it can gate a deploy. Warnings do not
fail: they are things that are usually wrong in staging and deliberately so.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

BLOCKER = "BLOCK"
WARNING = "WARN"
OK = "OK"


class Command(BaseCommand):
    help = "Check the settings-level items on the docs/08 launch checklist."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Treat warnings as blockers too.",
        )

    def handle(self, *args, **options):
        results = list(self._checks())

        width = max(len(name) for name, _, _ in results)
        for name, status, detail in results:
            colour = {
                OK: self.style.SUCCESS,
                WARNING: self.style.WARNING,
                BLOCKER: self.style.ERROR,
            }[status]
            self.stdout.write(f"{name.ljust(width)}  {colour(status)}  {detail}")

        failed = [r for r in results if r[1] == BLOCKER]
        if options["strict"]:
            failed += [r for r in results if r[1] == WARNING]

        self.stdout.write("")
        if failed:
            self.stdout.write(
                self.style.ERROR(f"{len(failed)} item(s) block a launch.")
            )
            raise SystemExit(1)

        self.stdout.write(
            self.style.SUCCESS("Settings-level checks pass.")
        )
        self.stdout.write(
            "\nThis command cannot verify the human items on the docs/08\n"
            "checklist - a signed DPA, a rehearsed restore, a regulator\n"
            "consulted, a clinician sign-off. Those remain outstanding until\n"
            "somebody does them."
        )

    # ------------------------------------------------------------------
    def _checks(self):
        debug = getattr(settings, "DEBUG", True)
        yield (
            "DEBUG is off",
            OK if not debug else BLOCKER,
            "DEBUG=True serves tracebacks, with settings, to the internet."
            if debug
            else "",
        )

        hosts = getattr(settings, "ALLOWED_HOSTS", [])
        wildcard = "*" in hosts
        yield (
            "ALLOWED_HOSTS is explicit",
            OK if hosts and not wildcard else BLOCKER,
            "A wildcard allows Host-header attacks and password-reset poisoning."
            if wildcard or not hosts
            else ", ".join(hosts),
        )

        key = getattr(settings, "SECRET_KEY", "")
        weak = (
            not key
            or len(key) < 32
            or "insecure" in key.lower()
            or "dev" in key.lower()
            or "change" in key.lower()
        )
        yield (
            "SECRET_KEY is strong",
            OK if not weak else BLOCKER,
            "Short, missing, or still the development placeholder."
            if weak
            else f"{len(key)} chars",
        )

        # TLS. Only meaningful with DEBUG off; in development these are
        # deliberately relaxed and flagging them would train people to ignore
        # this command.
        if not debug:
            yield (
                "TLS redirect",
                OK if getattr(settings, "SECURE_SSL_REDIRECT", False) else BLOCKER,
                "" if getattr(settings, "SECURE_SSL_REDIRECT", False)
                else "SECURE_SSL_REDIRECT is off.",
            )
            hsts = getattr(settings, "SECURE_HSTS_SECONDS", 0)
            yield (
                "HSTS",
                OK if hsts >= 3600 else WARNING,
                f"{hsts}s" if hsts else "SECURE_HSTS_SECONDS is 0.",
            )
            for name in ("SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE"):
                on = getattr(settings, name, False)
                yield (name, OK if on else BLOCKER, "" if on else "Off.")

        # Rate limits. The OTP bucket is the one that protects an SMS bill and
        # a patient's inbox; signin protects against password guessing.
        rates = getattr(settings, "REST_FRAMEWORK", {}).get(
            "DEFAULT_THROTTLE_RATES", {}
        )
        for scope in ("anon", "otp", "signin"):
            yield (
                f"Rate limit: {scope}",
                OK if rates.get(scope) else BLOCKER,
                rates.get(scope, "unset"),
            )

        # The clinical gate. Being SHUT is a passing state - the product is
        # designed to ship without the symptom checker.
        from apps.triage.gate import approval

        record = approval()
        yield (
            "Care Guide gate",
            OK,
            f"open, protocol {record.protocol_version} approved by "
            f"{record.approved_by}"
            if record
            else "shut - no clinician sign-off configured, which is the "
            "correct default",
        )

        # Logging redaction, which docs/08 s6 requires.
        logging_config = getattr(settings, "LOGGING", {})
        handlers = logging_config.get("handlers", {})
        redacted = all(
            "redact_pii" in handler.get("filters", [])
            for handler in handlers.values()
        ) and bool(handlers)
        yield (
            "Log redaction",
            OK if redacted else BLOCKER,
            "" if redacted else "A handler is missing the redact_pii filter.",
        )

        yield (
            "Privacy notice version",
            OK if getattr(settings, "PRIVACY_NOTICE_VERSION", "") else BLOCKER,
            getattr(settings, "PRIVACY_NOTICE_VERSION", "unset"),
        )
