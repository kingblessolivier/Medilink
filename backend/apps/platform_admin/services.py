"""Platform-wide figures, and the triage monitoring that must not read answers.

Two rules shape this file.

**Nothing here identifies a patient.** Every figure is a count or a rate. The
admin portal exists to answer "is the platform working?", which never requires
knowing who anybody is - and an endpoint that returns a patient list is one
somebody will eventually be tempted to search.

**Triage monitoring reads `TriageOutcome` only.** That model deliberately has
no patient link, no session id and no answers, and buckets by hour rather than
timestamp so a row cannot be correlated with a queue check-in a minute later.
Reading anything else here would defeat that design. See docs/08 section 8.
"""

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.facilities.models import Facility
from apps.patients.models import Patient
from apps.providers.models import Provider
from apps.queueing.models import QueueEntry
from apps.scheduling.models import Appointment
from apps.triage.models import TriageOutcome

# Below this a rate is noise, and an admin will act on it anyway. The same
# reasoning as the facility reports and the patient-facing wait times.
MIN_OUTCOMES = 20


def overview(days: int = 30) -> dict:
    """The numbers that say whether the platform is being used."""
    now = timezone.localtime()
    since = now - timedelta(days=days)

    facilities = Facility.objects.aggregate(
        total=Count("id"),
        verified=Count("id", filter=Q(verified_at__isnull=False)),
        reporting_queue=Count("id", filter=Q(reports_queue=True)),
    )
    providers = Provider.objects.aggregate(
        total=Count("id"),
        verified=Count("id", filter=Q(verified_at__isnull=False)),
    )

    appointments = Appointment.objects.filter(slot_start__gte=since)
    by_channel = list(
        appointments.values("booked_via")
        .annotate(n=Count("id"))
        .order_by("-n")
    )

    return {
        "days": days,
        "as_of": now.isoformat(),
        "facilities": {
            "total": facilities["total"],
            "verified": facilities["verified"],
            # The queue that matters operationally: unverified facilities are
            # invisible to patients, so this is unmet demand, not a backlog
            # of tidy-up.
            "awaiting_verification": facilities["total"] - facilities["verified"],
            "reporting_queue": facilities["reporting_queue"],
        },
        "providers": {
            "total": providers["total"],
            "verified": providers["verified"],
            "awaiting_verification": providers["total"] - providers["verified"],
        },
        # A count, never a list. See the module docstring.
        "patients": {"registered": Patient.objects.count()},
        "activity": {
            "check_ins": QueueEntry.objects.filter(joined_at__gte=since).count(),
            "appointments": appointments.count(),
            "by_channel": [
                {"channel": row["booked_via"], "count": row["n"]}
                for row in by_channel
            ],
        },
    }


def verification_queue() -> dict:
    """Facilities and providers waiting to become visible to patients.

    Ordered oldest-first: something that has been waiting three weeks is the
    problem, not the one submitted this morning.
    """
    facilities = (
        Facility.objects.filter(verified_at__isnull=True)
        .order_by("id")
        .values("id", "name", "slug", "district", "level", "ownership", "phone")
    )
    providers = (
        Provider.objects.filter(verified_at__isnull=True)
        .prefetch_related("specialties")
        .order_by("id")
    )

    return {
        "facilities": list(facilities),
        "providers": [
            {
                "id": provider.id,
                "slug": provider.slug,
                "full_name": provider.full_name,
                "specialties": [s.name_en for s in provider.specialties.all()],
            }
            for provider in providers
        ],
    }


def triage_monitoring(days: int = 30) -> dict:
    """Aggregates from `TriageOutcome`. Never an answer, never a session.

    The question this exists to answer is "does this protocol send too many
    people to an emergency department?" - a protocol that escalates a quarter
    of its sessions is either seeing a genuinely sick population or is broken,
    and either way a clinician needs to know.
    """
    since = timezone.localdate() - timedelta(days=days)
    outcomes = TriageOutcome.objects.filter(date__gte=since)

    totals = outcomes.aggregate(
        total=Count("id"),
        escalations=Count("id", filter=Q(escalated_emergency=True)),
    )
    total = totals["total"]

    by_service = (
        outcomes.exclude(recommended_service="")
        .values("recommended_service")
        .annotate(n=Count("id"))
        .order_by("-n")[:10]
    )
    by_version = (
        outcomes.values("protocol_version")
        .annotate(
            n=Count("id"),
            escalations=Count("id", filter=Q(escalated_emergency=True)),
        )
        .order_by("-n")
    )

    return {
        "days": days,
        "sessions": total,
        "escalations": totals["escalations"],
        # Null under the floor, so nobody tunes a protocol on four sessions.
        "escalation_rate": (
            round(totals["escalations"] / total, 3)
            if total >= MIN_OUTCOMES
            else None
        ),
        "enough_data": total >= MIN_OUTCOMES,
        "minimum_sessions": MIN_OUTCOMES,
        "by_service": [
            {"service": row["recommended_service"], "count": row["n"]}
            for row in by_service
        ],
        "by_version": [
            {
                "protocol_version": row["protocol_version"],
                "sessions": row["n"],
                "escalations": row["escalations"],
            }
            for row in by_version
        ],
    }
