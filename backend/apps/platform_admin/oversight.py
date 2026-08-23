"""What a platform administrator needs to SEE.

`services.py` answers "is the platform being used?". This answers "what is
happening on it, and is anything wrong?" - which is a different question and
the one somebody actually opens a dashboard to ask.

The rule from services.py still holds and is if anything more important here:
**nothing in this module returns a patient's identity.** Directory data
(facilities, doctors, insurers) is public information. Operational data
(appointments, queues) is reported as counts and status, never as names. The
one place a person appears is the ACTOR on an audit row - a staff member - and
that is the entire point of an audit trail.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.utils import timezone

from apps.facilities.models import Facility
from apps.notifications.models import Notification
from apps.patients.models import PatientAccessLog
from apps.providers.models import Provider
from apps.queueing.models import QueueEntry
from apps.scheduling.models import Appointment
from apps.staff.models import StaffMember


def facility_directory() -> list[dict]:
    """Every facility, with the things an admin can act on.

    `staff_count` and `is_reporting` matter more than they look: a verified
    facility with no staff account cannot check anybody in, and a facility
    that does not report its queue publishes no wait times. Both look fine
    from the patient side and are silently doing nothing.
    """
    rows = (
        Facility.objects.annotate(
            staff_count=Count("staff", filter=Q(staff__active=True), distinct=True),
            service_count=Count("services", distinct=True),
        )
        .order_by("district", "name")
    )
    return [
        {
            "id": f.id,
            "name": f.name,
            "slug": f.slug,
            "district": f.district,
            "level": f.level,
            "ownership": f.ownership,
            "verified": f.verified_at is not None,
            "reports_queue": f.reports_queue,
            "staff_count": f.staff_count,
            "service_count": f.service_count,
        }
        for f in rows
    ]


def provider_directory() -> list[dict]:
    rows = (
        Provider.objects.prefetch_related("specialties", "placements__facility")
        .order_by("full_name")
    )
    return [
        {
            "id": p.id,
            "slug": p.slug,
            "full_name": p.full_name,
            "verified": p.verified_at is not None,
            "specialties": [s.name_en for s in p.specialties.all()],
            "facilities": [
                pf.facility.name for pf in p.placements.all() if pf.active
            ],
        }
        for p in rows
    ]


def staff_directory() -> list[dict]:
    """Who can read patient records, and at which facility.

    This is an access-control list, not a personnel list. A dormant account
    with `active=True` is a standing door into one facility's patient data,
    and the only way anybody notices is by looking at it here.
    """
    rows = (
        StaffMember.objects.select_related("user", "facility")
        .order_by("facility__name", "user__username")
    )
    return [
        {
            "id": s.id,
            "username": s.user.get_username(),
            "facility": s.facility.name,
            "role": s.role,
            "active": s.active and s.user.is_active,
            "can_manage_queue": s.can_manage_queue,
            "last_login": s.user.last_login,
        }
        for s in rows
    ]


def platform_activity(days: int = 7) -> dict:
    """Operational state across every facility.

    Counts and status only. An admin needs to know that Kimironko has eleven
    people waiting and Remera has none; they do not need to know who those
    people are, and there is no view here that would tell them.
    """
    now = timezone.localtime()
    since = now - timedelta(days=days)

    by_facility = (
        Facility.objects.filter(verified_at__isnull=False)
        .annotate(
            waiting=Count(
                "queue_entries",
                filter=Q(queue_entries__status=QueueEntry.Status.WAITING),
                distinct=True,
            ),
            seen=Count(
                "queue_entries",
                filter=Q(
                    queue_entries__status=QueueEntry.Status.SERVED,
                    queue_entries__joined_at__gte=since,
                ),
                distinct=True,
            ),
            booked=Count(
                "appointments",
                filter=Q(appointments__slot_start__gte=since),
                distinct=True,
            ),
        )
        .order_by("-waiting", "name")
    )

    appointments = Appointment.objects.filter(slot_start__gte=since)

    return {
        "days": days,
        "as_of": now.isoformat(),
        "totals": {
            "waiting_now": QueueEntry.objects.filter(
                status=QueueEntry.Status.WAITING
            ).count(),
            "seen": QueueEntry.objects.filter(
                status=QueueEntry.Status.SERVED, joined_at__gte=since
            ).count(),
            "booked": appointments.count(),
            "no_shows": appointments.filter(
                status=Appointment.Status.NO_SHOW
            ).count(),
            # A facility that is verified but has never checked anybody in is
            # onboarded on paper only. Worth surfacing as a number.
            "facilities_active": sum(
                1 for f in by_facility if f.waiting or f.seen or f.booked
            ),
        },
        "facilities": [
            {
                "name": f.name,
                "district": f.district,
                "waiting": f.waiting,
                "seen": f.seen,
                "booked": f.booked,
                "reports_queue": f.reports_queue,
            }
            for f in by_facility
        ],
    }


def access_log(days: int = 7, limit: int = 25) -> dict:
    """Who looked at whose record.

    docs/08 section 6 built this table "to surface the anomaly that matters -
    a receptionist viewing hundreds of records outside their shift", and then
    nothing surfaced it. An audit trail nobody reads is a log file, not a
    control.

    The PATIENT is never named. Whose record was touched is not what an
    administrator reviewing access needs; who did the touching, how much, and
    when is. Naming the patient here would make the oversight tool its own
    disclosure risk.
    """
    now = timezone.localtime()
    since = now - timedelta(days=days)

    # A sample, not a dump. `total_events` carries the real figure, and the
    # grouped `by_actor` totals are what an anomaly actually shows up in.
    entries = (
        PatientAccessLog.objects.filter(occurred_at__gte=since)
        .select_related("actor", "facility")
        .order_by("-occurred_at")[:limit]
    )

    # Per-actor totals over the window, which is where an anomaly shows up.
    # A single "viewed 40 records" row is a queue board; forty of them from
    # one account at 3am is something else.
    by_actor = (
        PatientAccessLog.objects.filter(occurred_at__gte=since, actor__isnull=False)
        .values("actor__username", "facility__name")
        .annotate(
            events=Count("id"),
            records=Count("id"),
        )
        .order_by("-events")[:20]
    )

    return {
        "days": days,
        "as_of": now.isoformat(),
        "total_events": PatientAccessLog.objects.filter(
            occurred_at__gte=since
        ).count(),
        "by_actor": [
            {
                "actor": row["actor__username"],
                "facility": row["facility__name"] or "—",
                "events": row["events"],
            }
            for row in by_actor
        ],
        "recent": [
            {
                "id": e.id,
                "occurred_at": e.occurred_at,
                # "the patient themselves" is a meaningful actor and is not a
                # name - it says a person exercised a right over their own
                # record, which is the one access nobody needs to review.
                "actor": (
                    e.actor.get_username()
                    if e.actor_id
                    else ("the patient themselves" if e.acting_patient_id else "—")
                ),
                "action": e.action,
                "action_label": e.get_action_display(),
                "facility": e.facility.name if e.facility_id else "—",
                "record_count": e.record_count,
                "ip_address": e.ip_address,
            }
            for e in entries
        ],
    }


def delivery_report(days: int = 7) -> dict:
    """Did the messages actually arrive?

    A "leave now" SMS that never sent is a patient still sitting at home. The
    failure count is the number that matters; the body of any message is not
    shown, because several of them contain a patient's queue position and one
    of them contains a sign-in code.
    """
    since = timezone.localtime() - timedelta(days=days)
    window = Notification.objects.filter(created_at__gte=since)

    by_kind = (
        window.values("kind")
        .annotate(
            total=Count("id"),
            sent=Count("id", filter=Q(sent_at__isnull=False)),
            failed=Count("id", filter=Q(failed_at__isnull=False)),
        )
        .order_by("-total")
    )

    total = window.count()
    failed = window.filter(failed_at__isnull=False).count()

    return {
        "days": days,
        "total": total,
        "sent": window.filter(sent_at__isnull=False).count(),
        "failed": failed,
        # Null rather than 0% when nothing was sent - the same rule the wait
        # times follow. No messages is not a 100% success rate.
        "failure_rate": round(failed / total, 3) if total else None,
        "by_kind": [
            {
                "kind": row["kind"],
                "total": row["total"],
                "sent": row["sent"],
                "failed": row["failed"],
            }
            for row in by_kind
        ],
    }


def account_summary() -> dict:
    """Django users who are neither staff nor superuser have no surface at
    all - they can sign in and land nowhere. Worth counting."""
    users = User.objects.all()
    staffed = set(StaffMember.objects.values_list("user_id", flat=True))
    return {
        "total": users.count(),
        "superusers": users.filter(is_superuser=True).count(),
        "facility_staff": len(staffed),
        "stranded": users.exclude(is_superuser=True).exclude(id__in=staffed).count(),
    }
