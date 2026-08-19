"""WhatsApp Business Cloud API.

The middle tier: richer than USSD, no install to reach, already on most
smartphones in Kigali.

Two constraints that shape everything here:

**The 24-hour window.** Free-form replies are only allowed within 24 hours of
the patient's last message. Outside it, only pre-approved template messages may
be sent. That is why reminders are templates and replies are not.

**Interactive messages beat typing numbers.** WhatsApp has buttons and list
pickers, so patients pick a facility rather than typing "2". The USSD menu
numbering does not belong here.

Unlike USSD there is no GSM-7 or 160-character limit - accented text is fine
and messages may run to 4096 characters. Keep them short anyway; a wall of text
on a phone goes unread.
"""

import logging

from django.conf import settings

from apps.facilities.models import Facility
from apps.facilities.wait import STATUS_AVAILABLE, wait_snapshot
from apps.patients.models import Patient, normalise_phone
from apps.queueing.models import QueueEntry
from apps.queueing.services import eta_for

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v20.0"
MAX_LIST_ROWS = 10
MAX_ROW_TITLE = 24


class WhatsAppNotConfigured(RuntimeError):
    pass


def _config():
    token = getattr(settings, "WA_ACCESS_TOKEN", "")
    phone_id = getattr(settings, "WA_PHONE_NUMBER_ID", "")
    if not token or not phone_id:
        raise WhatsAppNotConfigured(
            "Set WA_ACCESS_TOKEN and WA_PHONE_NUMBER_ID to send WhatsApp messages."
        )
    return token, phone_id


def send(payload: dict) -> dict:
    """POST one message to the Cloud API.

    Import of `requests` is local so the rest of the app - and the whole test
    suite - does not depend on a package that is only needed when WhatsApp is
    actually configured.
    """
    token, phone_id = _config()
    import requests  # noqa: PLC0415

    response = requests.post(
        f"{GRAPH_URL}/{phone_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


# --------------------------------------------------------------------------
# Message builders - pure functions, unit-testable without a network
# --------------------------------------------------------------------------


def text_message(to: str, body: str) -> dict:
    return {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body[:4096]},
    }


def main_menu_message(to: str, language: str = "rw") -> dict:
    labels = {
        "rw": ("MediLink", "Uifuza iki?", "Amavuriro hafi", "Umurongo wanjye"),
        "en": ("MediLink", "What do you need?", "Nearby facilities", "My queue"),
        "fr": ("MediLink", "Que voulez-vous?", "Centres proches", "Ma file"),
    }
    title, body, nearby, queue = labels.get(language, labels["rw"])

    return {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": title},
            "body": {"text": body},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {"id": "menu:nearby", "title": nearby[:20]},
                    },
                    {
                        "type": "reply",
                        "reply": {"id": "menu:queue", "title": queue[:20]},
                    },
                ]
            },
        },
    }


def facility_list_message(to: str, facilities, service_code=None, language="rw") -> dict:
    """A picker, not a numbered list. WhatsApp can do better than USSD."""
    headers = {
        "rw": ("Amavuriro hafi yawe", "Hitamo ivuriro:", "Reba amavuriro"),
        "en": ("Facilities near you", "Choose a facility:", "View facilities"),
        "fr": ("Centres proches", "Choisissez un centre:", "Voir les centres"),
    }
    header, body, button = headers.get(language, headers["rw"])

    snapshot = wait_snapshot(list(facilities), service_code=service_code)

    rows = []
    for facility in list(facilities)[:MAX_LIST_ROWS]:
        wait = snapshot.get(facility.id, {})
        if wait.get("status") == STATUS_AVAILABLE:
            description = f"{facility.district} - {wait['minutes']} min"
        else:
            # Never invent a wait. Say what we do know instead.
            description = facility.district
        rows.append(
            {
                "id": f"facility:{facility.id}",
                "title": facility.name[:MAX_ROW_TITLE],
                "description": description[:72],
            }
        )

    return {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": header},
            "body": {"text": body},
            "action": {
                "button": button[:20],
                "sections": [{"title": header[:24], "rows": rows}],
            },
        },
    }


def queue_status_message(to: str, entry: QueueEntry, language: str = "rw") -> dict:
    estimate = eta_for(entry)
    facility = entry.facility.name

    if entry.status == QueueEntry.Status.CALLED:
        bodies = {
            "rw": f"Barahamagara {entry.ticket_code} kuri {facility}. Injira.",
            "en": f"You are being called: {entry.ticket_code} at {facility}.",
            "fr": f"On vous appelle: {entry.ticket_code} a {facility}.",
        }
    elif estimate["eta_minutes"] is None:
        bodies = {
            "rw": (
                f"Uri nomero {estimate['position']} kuri {facility}. "
                "Igihe cyo gutegereza ntikiboneka."
            ),
            "en": (
                f"You are number {estimate['position']} at {facility}. "
                "Wait time not available."
            ),
            "fr": (
                f"Vous etes numero {estimate['position']} a {facility}. "
                "Temps d'attente inconnu."
            ),
        }
    else:
        bodies = {
            "rw": (
                f"Uri nomero {estimate['position']} kuri {facility}. "
                f"Hasigaye nka iminota {estimate['eta_minutes']}."
            ),
            "en": (
                f"You are number {estimate['position']} at {facility}. "
                f"About {estimate['eta_minutes']} minutes to go."
            ),
            "fr": (
                f"Vous etes numero {estimate['position']} a {facility}. "
                f"Environ {estimate['eta_minutes']} minutes."
            ),
        }

    return text_message(to, bodies.get(language, bodies["rw"]))


def no_queue_message(to: str, language: str = "rw") -> dict:
    bodies = {
        "rw": "Nta murongo urimo ubu.",
        "en": "You are not in a queue right now.",
        "fr": "Vous n'etes dans aucune file.",
    }
    return text_message(to, bodies.get(language, bodies["rw"]))


# --------------------------------------------------------------------------
# Inbound
# --------------------------------------------------------------------------


def extract_messages(payload: dict) -> list[dict]:
    """Pull messages out of Meta's deeply nested webhook envelope.

    Status callbacks (delivered/read) arrive on the same webhook with no
    `messages` key at all, so this returns an empty list for them.
    """
    messages = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for message in value.get("messages", []) or []:
                messages.append(message)
    return messages


def reply_id(message: dict) -> str | None:
    """The id of a tapped button or picked list row, if any."""
    interactive = message.get("interactive") or {}
    for key in ("button_reply", "list_reply"):
        if key in interactive:
            return (interactive[key] or {}).get("id")
    return None


def handle_inbound_message(payload: dict) -> int:
    """Route inbound WhatsApp messages. Returns how many were handled."""
    handled = 0

    for message in extract_messages(payload):
        raw_from = message.get("from", "")
        try:
            phone = normalise_phone(raw_from)
        except Exception:  # noqa: BLE001
            logger.warning("whatsapp_bad_phone")
            continue

        patient = Patient.objects.filter(phone=phone).first()
        language = patient.language if patient else "rw"

        choice = reply_id(message)
        body = ((message.get("text") or {}).get("body") or "").strip().lower()

        if choice == "menu:queue" or body in {"queue", "umurongo", "file"}:
            _reply_with_queue(phone, patient, language)
        elif choice == "menu:nearby" or body in {"nearby", "hafi", "proche"}:
            _reply_with_nearby(phone, patient, language)
        else:
            _safe_send(main_menu_message(phone, language))

        handled += 1

    return handled


def _reply_with_queue(phone, patient, language) -> None:
    entry = None
    if patient is not None:
        entry = (
            QueueEntry.objects.filter(
                patient=patient, status__in=QueueEntry.OPEN_STATUSES
            )
            .select_related("facility", "service_type")
            .order_by("-joined_at")
            .first()
        )
    if entry is None:
        _safe_send(no_queue_message(phone, language))
    else:
        _safe_send(queue_status_message(phone, entry, language))


def _reply_with_nearby(phone, patient, language) -> None:
    queryset = Facility.objects.filter(verified_at__isnull=False)
    if patient is not None and patient.district:
        queryset = queryset.filter(district=patient.district)

    facilities = list(queryset[:MAX_LIST_ROWS])
    if not facilities:
        _safe_send(text_message(phone, "No facilities found."))
        return
    _safe_send(facility_list_message(phone, facilities, language=language))


def _safe_send(payload: dict) -> None:
    """A send failure must not make Meta redeliver the inbound message."""
    try:
        send(payload)
    except WhatsAppNotConfigured:
        logger.info("whatsapp_not_configured", extra={"to": payload.get("to")})
    except Exception:  # noqa: BLE001
        logger.exception("whatsapp_send_failed", extra={"to": payload.get("to")})
