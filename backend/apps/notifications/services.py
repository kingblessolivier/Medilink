"""Notification dispatch.

Every send goes through `dispatch()`, which creates the Notification row FIRST.
The unique constraints on that row are the duplicate defence - not an `if
already_sent` check in Python, which two overlapping beat runs would both pass.
"""

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Notification, NotificationPreference
from .sms import get_backend, render

logger = logging.getLogger(__name__)

# Kinyarwanda first. These are short by necessity: one SMS segment is 160
# GSM-7 characters and a second segment costs a second message.
TEMPLATES = {
    Notification.Kind.OTP: {
        "rw": "MediLink: kode yawe ni {code}. Igira agaciro k'iminota {minutes}.",
        "en": "MediLink: your code is {code}. It expires in {minutes} minutes.",
        "fr": "MediLink: votre code est {code}. Il expire dans {minutes} minutes.",
    },
    Notification.Kind.LEAVE_NOW: {
        "rw": "MediLink: uri nomero {position} kuri {facility}. Genda ubu.",
        "en": "MediLink: you are number {position} at {facility}. Leave now.",
        "fr": "MediLink: vous etes numero {position} a {facility}. Partez maintenant.",
    },
    Notification.Kind.CALLED: {
        "rw": "MediLink: barahamagara nomero yawe {ticket} kuri {facility}. Injira.",
        "en": "MediLink: your number {ticket} is being called at {facility}.",
        "fr": "MediLink: votre numero {ticket} est appele a {facility}.",
    },
    Notification.Kind.APPT_REMINDER_24H: {
        "rw": "MediLink: ejo saa {time} uzajya {facility}. Kode: {reference}.",
        "en": "MediLink: appointment tomorrow at {time}, {facility}. Ref {reference}.",
        "fr": "MediLink: rendez-vous demain a {time}, {facility}. Ref {reference}.",
    },
    Notification.Kind.APPT_REMINDER_2H: {
        "rw": "MediLink: saa {time} uzajya {facility}. Kode: {reference}.",
        "en": "MediLink: appointment at {time} today, {facility}. Ref {reference}.",
        "fr": "MediLink: rendez-vous a {time} aujourd'hui, {facility}. Ref {reference}.",
    },
    Notification.Kind.APPT_CANCELLED: {
        "rw": "MediLink: gahunda yawe yo kuri {facility} yahagaritswe.",
        "en": "MediLink: your appointment at {facility} was cancelled.",
        "fr": "MediLink: votre rendez-vous a {facility} a ete annule.",
    },
}


def compose(kind: str, language: str, **context) -> str:
    bundle = TEMPLATES[kind]
    template = bundle.get(language) or bundle["rw"]
    return render(template.format(**context))


def dispatch(
    *,
    kind: str,
    phone: str,
    language: str = "rw",
    patient=None,
    queue_entry=None,
    appointment=None,
    **context,
) -> Notification | None:
    """Send one notification, exactly once.

    Returns None when the same notification has already been created for this
    queue entry or appointment - that is the normal, expected outcome of two
    overlapping schedulers, not an error.
    """
    # Honoured HERE rather than at each call site, so nothing can forget.
    # Transactional kinds ignore preferences entirely - see OPTIONAL_KINDS.
    if patient is not None and not NotificationPreference.is_enabled(patient, kind):
        logger.debug("notification_opted_out", extra={"kind": kind})
        return None

    body = compose(kind, language, **context)

    try:
        with transaction.atomic():
            notification = Notification.objects.create(
                patient=patient,
                phone=phone,
                channel=Notification.Channel.SMS,
                kind=kind,
                body=body,
                queue_entry=queue_entry,
                appointment=appointment,
            )
    except IntegrityError:
        logger.debug("notification_already_sent", extra={"kind": kind})
        return None

    try:
        reference = get_backend().send(phone, body)
    except Exception as exc:  # noqa: BLE001 - a failed send must be recorded
        notification.failed_at = timezone.now()
        notification.error = str(exc)[:255]
        notification.save(update_fields=["failed_at", "error"])
        logger.exception("sms_send_failed", extra={"kind": kind})
        return notification

    notification.sent_at = timezone.now()
    notification.provider_ref = reference
    notification.save(update_fields=["sent_at", "provider_ref"])
    return notification
