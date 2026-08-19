"""WhatsApp webhook and message construction.

Two properties matter. Signature verification fails closed, and the webhook
always answers 200 once the signature is valid: Meta retries on anything else,
and the patient receives the same reply several times.
"""

import hashlib
import hmac
import json
from datetime import time

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.facilities.models import Facility, FacilityService, OpeningHours, ServiceType
from apps.gateway import whatsapp as wa
from apps.patients.models import Patient
from apps.queueing.models import QueueEntry, ServiceTimeStat

HOOK = "/api/v1/gateway/whatsapp"
PHONE = "+250788111222"
APP_SECRET = "test-app-secret"


@pytest.fixture(autouse=True)
def whatsapp_secrets(settings):
    """Signature verification fails closed, so every POST must be signed."""
    settings.WA_APP_SECRET = APP_SECRET
    settings.WA_VERIFY_TOKEN = "test-verify-token"


def signed_post(client, payload, secret=APP_SECRET):
    """POST with a valid X-Hub-Signature-256 over the RAW body."""
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return client.post(
        HOOK,
        data=raw,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256=f"sha256={signature}",
    )


@pytest.fixture
def general(db):
    return ServiceType.objects.create(
        code="general_consultation",
        name_en="General consultation",
        name_rw="Kwivuza rusange",
        name_fr="Consultation generale",
    )


@pytest.fixture
def facility(db, general):
    facility = Facility.objects.create(
        name="Kimironko Health Centre",
        slug="kimironko-hc",
        ownership="public",
        level="health_centre",
        district="Gasabo",
        location=Point(30.1122, -1.9481, srid=4326),
        verified_at=timezone.now(),
        reports_queue=True,
    )
    for weekday in range(7):
        OpeningHours.objects.create(
            facility=facility,
            weekday=weekday,
            opens_at=time(0, 0),
            closes_at=time(23, 59),
        )
    FacilityService.objects.create(
        facility=facility, service_type=general, available=True
    )
    return facility


@pytest.fixture
def patient(db):
    return Patient.objects.create(phone=PHONE, district="Gasabo")


@pytest.fixture
def sent(monkeypatch):
    """Capture outbound payloads instead of calling the Graph API."""
    outbox = []
    monkeypatch.setattr(wa, "send", lambda payload: outbox.append(payload) or {})
    return outbox


def inbound_text(body: str, sender: str = "250788111222") -> dict:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": sender,
                                    "type": "text",
                                    "text": {"body": body},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }


def inbound_reply(reply_id: str, sender: str = "250788111222") -> dict:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {
                                            "id": reply_id,
                                            "title": "x",
                                        },
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }


# --------------------------------------------------------------------------
# Verification handshake
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_verification_handshake(client):
    response = client.get(
        HOOK,
        {
            "hub.mode": "subscribe",
            "hub.verify_token": "test-verify-token",
            "hub.challenge": "12345",
        },
    )

    assert response.status_code == 200
    assert response.content.decode() == "12345"


@pytest.mark.django_db
def test_verification_rejects_a_wrong_token(client):
    response = client.get(
        HOOK, {"hub.verify_token": "guess", "hub.challenge": "12345"}
    )

    assert response.status_code == 403


# --------------------------------------------------------------------------
# Signature verification fails closed
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_forged_signatures_are_rejected(client):
    response = client.post(
        HOOK,
        data=json.dumps(inbound_text("hello")),
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256="sha256=deadbeef",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_an_unsigned_payload_is_rejected(client):
    response = client.post(
        HOOK,
        data=json.dumps(inbound_text("hello")),
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_an_unconfigured_app_secret_refuses_everything(client, settings):
    settings.WA_APP_SECRET = ""

    assert signed_post(client, inbound_text("hello")).status_code == 403


@pytest.mark.django_db
def test_valid_signature_is_accepted(client, sent, patient):
    assert signed_post(client, inbound_text("hello")).status_code == 200


@pytest.mark.django_db
def test_signature_is_checked_against_the_raw_body(client, sent):
    """Re-serialising the parsed JSON changes whitespace and breaks the
    signature, so verification must read request.body."""
    raw = b'{"entry": [{"changes": [{"value": {"messages": []}}]}]}   '
    signature = hmac.new(APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()

    response = client.post(
        HOOK,
        data=raw,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256=f"sha256={signature}",
    )

    assert response.status_code == 200


# --------------------------------------------------------------------------
# Always 200 once authenticated
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_malformed_json_still_returns_200(client):
    """A non-200 makes Meta redeliver forever."""
    assert signed_post(client, b"{not json").status_code == 200


@pytest.mark.django_db
def test_a_handler_error_still_returns_200(client, monkeypatch):
    from apps.gateway import views

    def boom(payload):
        raise RuntimeError("boom")

    # The view imports the symbol directly, so patch it there.
    monkeypatch.setattr(views, "handle_inbound_message", boom)

    assert signed_post(client, inbound_text("hello")).status_code == 200


@pytest.mark.django_db
def test_status_callbacks_are_ignored_quietly(client):
    """Delivery receipts arrive on the same webhook with no messages key."""
    payload = {"entry": [{"changes": [{"value": {"statuses": [{"id": "x"}]}}]}]}

    assert wa.extract_messages(payload) == []
    assert signed_post(client, payload).status_code == 200


# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_unknown_text_gets_the_menu(sent, patient):
    wa.handle_inbound_message(inbound_text("hello there"))

    assert len(sent) == 1
    assert sent[0]["interactive"]["type"] == "button"


@pytest.mark.django_db
def test_queue_button_reports_position(sent, facility, general, patient):
    QueueEntry.objects.create(
        facility=facility, service_type=general, patient=patient, ticket_code="G-007"
    )

    wa.handle_inbound_message(inbound_reply("menu:queue"))

    assert "1" in sent[0]["text"]["body"]


@pytest.mark.django_db
def test_queue_button_when_not_waiting(sent, patient):
    wa.handle_inbound_message(inbound_reply("menu:queue"))

    assert "text" in sent[0]


@pytest.mark.django_db
def test_nearby_button_returns_a_picker(sent, facility, patient):
    wa.handle_inbound_message(inbound_reply("menu:nearby"))

    interactive = sent[0]["interactive"]
    assert interactive["type"] == "list"
    rows = interactive["action"]["sections"][0]["rows"]
    assert rows[0]["id"] == f"facility:{facility.id}"


# --------------------------------------------------------------------------
# Message construction
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_facility_list_omits_unknown_wait_times(facility):
    """Never invent a wait; show what we do know instead."""
    message = wa.facility_list_message("250788111222", [facility])

    row = message["interactive"]["action"]["sections"][0]["rows"][0]
    assert row["description"] == "Gasabo"
    assert "min" not in row["description"]


@pytest.mark.django_db
def test_facility_list_shows_a_known_wait(facility, general):
    ServiceTimeStat.objects.create(
        facility=facility,
        service_type=general,
        hour_of_day=timezone.localtime().hour,
        median_minutes=7.0,
        sample_size=120,
    )
    QueueEntry.objects.create(
        facility=facility, service_type=general, walk_in_name="A", ticket_code="G-1"
    )

    message = wa.facility_list_message(
        "250788111222", [facility], service_code="general_consultation"
    )

    row = message["interactive"]["action"]["sections"][0]["rows"][0]
    assert "min" in row["description"]


@pytest.mark.django_db
def test_row_titles_respect_the_whatsapp_limit(db):
    long_name = Facility.objects.create(
        name="A Very Long Facility Name That Exceeds The Limit",
        slug="long",
        ownership="public",
        level="health_centre",
        district="Gasabo",
        location=Point(30.1, -1.9, srid=4326),
        verified_at=timezone.now(),
    )

    message = wa.facility_list_message("250788111222", [long_name])
    row = message["interactive"]["action"]["sections"][0]["rows"][0]

    assert len(row["title"]) <= wa.MAX_ROW_TITLE


def test_accented_text_is_allowed_on_whatsapp():
    """Unlike USSD, WhatsApp is not limited to the GSM-7 alphabet."""
    message = wa.text_message("250788111222", "Rendez-vous confirme a l hopital")

    assert "confirme" in message["text"]["body"]


@pytest.mark.django_db
def test_send_without_configuration_raises_clearly(settings):
    settings.WA_ACCESS_TOKEN = ""
    settings.WA_PHONE_NUMBER_ID = ""

    with pytest.raises(wa.WhatsAppNotConfigured):
        wa.send({"messaging_product": "whatsapp"})
