"""Data subject rights.

Rwanda's Law N° 058/2021 gives people rights over their own data. docs/08
section 7 is explicit that each right needs an implementation, not a policy
page - a promise to handle erasure by email is not a control.

Two rights are non-obvious to implement and are handled here.

**Access.** `export()` returns everything held about one patient, in one JSON
document, in a form they can actually read. It must include the queue and
appointment history, because "which facility did I attend, when" is exactly
the sensitive part.

**Erasure.** `anonymise()` does NOT delete rows. A facility has a legitimate
interest in its own attendance counts, and deleting a queue entry would
silently corrupt the service-time statistics that every other patient's wait
estimate depends on. Instead the person is severed from the record: the
facility keeps its counts, and nobody can tell who it was.
"""

import logging
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def export(patient) -> dict:
    """Everything held about one patient.

    Deliberately built from explicit field lists rather than a serializer:
    a field added to the model later should not silently start or stop being
    exported without somebody deciding.
    """
    from apps.notifications.models import Notification
    from apps.queueing.models import QueueEntry
    from apps.scheduling.models import Appointment

    return {
        "exported_at": timezone.now().isoformat(),
        "profile": {
            "phone": patient.phone,
            # Held about them, so it is disclosed. Its absence made the export
            # incomplete for anyone who had registered on the web.
            "username": patient.username,
            "full_name": patient.full_name,
            "language": patient.language,
            "district": patient.district,
            "insurer": patient.insurer.code if patient.insurer_id else None,
            "home_location": (
                {"lat": patient.home_location.y, "lng": patient.home_location.x}
                if patient.home_location
                else None
            ),
            "created_at": patient.created_at.isoformat(),
            "last_seen_at": (
                patient.last_seen_at.isoformat() if patient.last_seen_at else None
            ),
            # The hash is disclosed, not the number - we never held the number.
            "national_id_hash": patient.national_id_hash or None,
            # What they agreed to and when. A person asking what is held about
            # them is entitled to see the record of their own consent, and to
            # notice if it names a notice version they never saw.
            "consent": {
                "given_at": (
                    patient.consented_at.isoformat() if patient.consented_at else None
                ),
                "notice_version": patient.consent_version or None,
            },
        },
        "appointments": [
            {
                "reference": a.reference,
                "facility": a.facility.name,
                "service": a.service_type.code,
                "slot_start": a.slot_start.isoformat(),
                "status": a.status,
                "booked_via": a.booked_via,
                "created_at": a.created_at.isoformat(),
            }
            for a in Appointment.objects.filter(patient=patient)
            .select_related("facility", "service_type")
            .order_by("slot_start")
        ],
        "queue_entries": [
            {
                "facility": q.facility.name,
                "service": q.service_type.code,
                "ticket_code": q.ticket_code,
                "joined_at": q.joined_at.isoformat(),
                "status": q.status,
                "served_at": q.served_at.isoformat() if q.served_at else None,
            }
            for q in QueueEntry.objects.filter(patient=patient)
            .select_related("facility", "service_type")
            .order_by("joined_at")
        ],
        "messages_sent_to_you": [
            {
                "kind": n.kind,
                "channel": n.channel,
                "body": n.body,
                "sent_at": n.sent_at.isoformat() if n.sent_at else None,
            }
            for n in Notification.objects.filter(patient=patient).order_by(
                "created_at"
            )
        ],
        "note": (
            "Symptom-checker answers are not listed because they are never "
            "stored against your account. They are held in temporary memory "
            "for at most 30 minutes and then discarded."
        ),
    }


@transaction.atomic
def anonymise(patient) -> None:
    """Sever the person from their records, keeping the facility's counts.

    Deleting instead would corrupt ServiceTimeStat, and therefore the wait
    estimate shown to every other patient at that facility.

    The phone is replaced rather than blanked because it is a unique column;
    a second erasure would otherwise collide with the first. The placeholder is
    kept under Patient.phone's 20-character limit - 48 bits of randomness is
    ample to keep erasures from colliding.
    """
    from apps.notifications.models import Notification
    from apps.queueing.models import QueueEntry
    from apps.scheduling.models import Appointment

    # Queue history stays; the name and the link to a person do not.
    QueueEntry.objects.filter(patient=patient).update(patient=None, walk_in_name="")

    # Cancel and detach rather than delete. The facility keeps the booking in
    # its own counts - a slot that was held and not released is part of its
    # no-show and utilisation picture - and the person is no longer in it.
    Appointment.objects.filter(patient=patient).update(
        patient=None, status=Appointment.Status.CANCELLED, cancelled_at=timezone.now()
    )

    # Message bodies name facilities and times. Nothing here is needed once
    # the person is gone.
    Notification.objects.filter(patient=patient).delete()

    patient.phone = f"del-{uuid4().hex[:12]}"  # 16 chars, fits max_length=20
    patient.full_name = ""
    patient.district = ""
    patient.national_id_hash = ""
    patient.home_location = None
    patient.insurer = None

    # Web credentials go too. Without this the account stays reachable: sign-in
    # resolves a patient by username and the password hash was left intact, so
    # somebody who had exercised their right to erasure could still log in
    # afterwards. The username is identifying data in its own right as well -
    # people choose their own name for it.
    #
    # None rather than "", because the column is unique: a second erasure would
    # collide on an empty string the way it would have collided on a blank
    # phone. Postgres permits many NULLs in a unique index.
    patient.username = None
    patient.password = ""

    # `consented_at` and `consent_version` are deliberately NOT cleared. Once
    # the row is severed from the person they are no longer personal data, and
    # they are the controller's record that processing had a lawful basis while
    # it was happening. Erasing the evidence of consent is not the same as
    # erasing the person.
    patient.save()

    logger.info("patient_anonymised", extra={"patient_id": patient.pk})
