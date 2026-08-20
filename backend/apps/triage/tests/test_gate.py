"""The clinical gate.

The most important tests in this app assert that the feature is OFF. A symptom
checker that routes patients toward or away from care must not be reachable
until a named clinician has signed off a specific protocol version.
"""

import json
from pathlib import Path

import pytest
from django.conf import settings

from apps.triage.gate import approval, is_enabled

EXAMPLE = Path(settings.BASE_DIR) / "apps/triage/protocols/routing.example.json"

STATUS = "/api/v1/triage/status"
SESSIONS = "/api/v1/triage/sessions"


@pytest.fixture
def gate_open(settings, tmp_path):
    """A signed-off protocol, for testing the engine behind the gate.

    Uses a copy of the structural example with a version that matches the
    approval, because the real example is deliberately unloadable.
    """
    raw = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    raw["version"] = "test.1"
    path = tmp_path / "routing.test.1.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    settings.TRIAGE_PROTOCOL_VERSION = "test.1"
    settings.TRIAGE_APPROVED_BY = "Dr Test, RMDC-0000"
    settings.TRIAGE_APPROVED_ON = "2026-09-01"
    settings.TRIAGE_PROTOCOL_FILE = str(path)
    return path


# --------------------------------------------------------------------------
# Off by default
# --------------------------------------------------------------------------


def test_the_gate_is_shut_out_of_the_box():
    """No approval configured means no symptom checker. This is the default
    in every environment, including production."""
    assert approval() is None
    assert is_enabled() is False


@pytest.mark.django_db
def test_starting_a_session_is_refused(client):
    response = client.post(SESSIONS)

    assert response.status_code == 503
    assert response.json()["type"] == "service_unavailable"
    assert "clinician" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_answering_is_refused(client):
    response = client.post(
        f"{SESSIONS}/anything/answer",
        {"question": "q", "option": "yes"},
        content_type="application/json",
    )

    assert response.status_code == 503


@pytest.mark.django_db
def test_status_reports_unavailable_with_a_reason(client):
    body = client.get(STATUS).json()

    assert body["available"] is False
    assert body["reason"]
    assert body["protocol_version"] == ""


@pytest.mark.django_db
@pytest.mark.parametrize(
    "missing",
    [
        "TRIAGE_PROTOCOL_VERSION",
        "TRIAGE_APPROVED_BY",
        "TRIAGE_APPROVED_ON",
        "TRIAGE_PROTOCOL_FILE",
    ],
)
def test_a_partial_approval_does_not_open_the_gate(client, gate_open, settings, missing):
    """All four must be present. A half-configured approval is not an
    approval - it is somebody having forgotten a step."""
    setattr(settings, missing, "")

    assert is_enabled() is False
    assert client.post(SESSIONS).status_code == 503


# --------------------------------------------------------------------------
# The shipped example must not be loadable
# --------------------------------------------------------------------------


def test_the_example_protocol_ships_with_a_non_matching_version():
    """It is a structural example, not clinical content. Its version cannot
    match any real approval."""
    raw = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    assert raw["version"] == "0.0-example"
    assert "EXAMPLE ONLY" in raw["_warning"].upper()


@pytest.mark.django_db
def test_the_example_protocol_is_refused_when_configured(client, settings, gate_open):
    """Pointing an approval at the example fails: the version does not match,
    so the sign-off would describe something nobody reviewed."""
    settings.TRIAGE_PROTOCOL_FILE = str(EXAMPLE)

    response = client.post(SESSIONS)

    assert response.status_code == 503
    assert "misconfigured" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_a_missing_protocol_file_is_refused(client, settings, gate_open):
    settings.TRIAGE_PROTOCOL_FILE = "does/not/exist.json"

    assert client.post(SESSIONS).status_code == 503


# --------------------------------------------------------------------------
# Behind an open gate
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_status_reports_available_once_signed_off(client, gate_open):
    body = client.get(STATUS).json()

    assert body["available"] is True
    assert body["protocol_version"] == "test.1"
    assert body["approved_by"] == "Dr Test, RMDC-0000"


@pytest.mark.django_db
def test_a_session_starts_with_the_red_flag_question(client, gate_open):
    body = client.post(SESSIONS).json()

    assert body["next_question"]["red_flag"] is True
    assert body["escalate_emergency"] is False


@pytest.mark.django_db
def test_the_disclaimer_is_on_every_response(client, gate_open):
    """Not shown once at onboarding: a patient who returns later must still
    see it."""
    body = client.post(SESSIONS).json()

    assert set(body["disclaimer"]) == {"rw", "en", "fr"}
    assert "not a diagnosis" in body["disclaimer"]["en"].lower()

    answered = client.post(
        f"{SESSIONS}/{body['session_id']}/answer",
        {"question": "example_red_flag", "option": "no"},
        content_type="application/json",
    ).json()

    assert set(answered["disclaimer"]) == {"rw", "en", "fr"}
