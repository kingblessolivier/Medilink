"""One sign-in account per user type, so every surface can actually be opened.

Until this existed, the demo accounts were created by hand in a shell. Three
consequences, all of them real:

  - a fresh clone could seed facilities, start the stack, and then not sign in
    at all, because no account existed and nothing said so
  - only the receptionist had an account, so the clinician and facility
    administrator surfaces had never once been opened in a browser
  - no patient had a username, so `/visits`, `/profile`, `/queue` and
    `/notifications` could only be reached by registering a throwaway account
    on every run

Refuses to run unless DEBUG. A command that sets known passwords is a hole in
anything facing the internet, and "we will remember not to run it in
production" is not a control.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count

from apps.facilities.models import Facility
from apps.patients.models import Patient
from apps.staff.models import StaffMember

# Deliberately obvious. Anyone reading a log and wondering whether this is a
# real credential should be able to answer in under a second.
PASSWORD = "demo-pass-123"

STAFF = [
    ("reception", "Receptionist", StaffMember.Role.RECEPTIONIST),
    ("clinician", "Clinician", StaffMember.Role.CLINICIAN),
    ("facility-admin", "Facility administrator", StaffMember.Role.ADMIN),
]


class Command(BaseCommand):
    help = "Create one demo account per user type (development only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=PASSWORD,
            help=f"Password for every seeded account (default: {PASSWORD}).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Refusing to run with DEBUG off. This command sets known "
                "passwords; that is a development convenience, not a "
                "deployment step."
            )

        password = options["password"]

        facility = self._busiest_facility()
        if facility is None:
            raise CommandError(
                "No verified facility to attach staff to. Run:\n"
                "  python manage.py loaddata fixtures/kigali_facilities.json\n"
                "  python manage.py seed_demo"
            )

        rows = []

        # ------------------------------------------------------------ staff
        for username, label, role in STAFF:
            user, _ = User.objects.get_or_create(
                username=username, defaults={"first_name": label}
            )
            # Always reset: the point is a password you can predict.
            user.set_password(password)
            user.is_active = True
            user.save()

            staff, _ = StaffMember.objects.get_or_create(
                user=user, defaults={"facility": facility, "role": role}
            )
            # An existing row may carry a stale role from an earlier run.
            staff.facility = facility
            staff.role = role
            staff.active = True
            staff.save()

            rows.append((username, label, facility.name))

        # --------------------------------------------------- platform admin
        admin, _ = User.objects.get_or_create(
            username="platform", defaults={"first_name": "Platform administrator"}
        )
        admin.set_password(password)
        admin.is_staff = True
        admin.is_superuser = True
        admin.is_active = True
        admin.save()
        # A superuser who is also facility staff would route to the workspace
        # instead of the portal, which makes the portal look broken.
        StaffMember.objects.filter(user=admin).delete()
        rows.append(("platform", "Platform administrator", "all facilities"))

        # ---------------------------------------------------------- patient
        patient = Patient.objects.filter(username__iexact="patient").first()
        if patient is None:
            # Prefer an existing seeded patient over inventing another one:
            # the seeded ones already have visits and bookings attached, which
            # is what makes the signed-in screens worth looking at.
            patient = (
                Patient.objects.filter(username__isnull=True)
                .order_by("id")
                .first()
            )
        if patient is None:
            raise CommandError(
                "No patient to promote. Run `python manage.py seed_demo` first."
            )
        patient.username = "patient"
        patient.set_password(password)
        patient.save()
        rows.append(("patient", "Patient", patient.full_name or patient.phone))

        # ----------------------------------------------------------- report
        width = max(len(r[0]) for r in rows)
        self.stdout.write(self.style.SUCCESS("\nDemo accounts (password below):\n"))
        for username, label, where in rows:
            self.stdout.write(f"  {username.ljust(width)}  {label:24} {where}")
        self.stdout.write(f"\n  password: {password}\n")
        self.stdout.write(
            self.style.WARNING(
                "  Development only. These credentials are in version control.\n"
            )
        )

    def _busiest_facility(self):
        """The facility whose workspace is worth opening.

        Attaching demo staff to whichever facility sorted first gave the
        receptionist an empty queue, an empty report and nothing to click -
        which reads as a broken app rather than an unstaffed facility. Order
        by whether the facility publishes a queue at all, then by how much
        queue history it has, then by id so two runs agree.
        """
        return (
            Facility.objects.filter(verified_at__isnull=False)
            .annotate(entries=Count("queue_entries"))
            .order_by("-reports_queue", "-entries", "id")
            .first()
        )
