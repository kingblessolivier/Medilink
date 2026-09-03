"""The one-step check: free text in, conditions and a service out.

No session, no questionnaire, no sign-in. Most of these tests are about the
screening that had to survive losing the questions.
"""

import pytest

from apps.triage import engine
from apps.triage.protocol import parse

PROTOCOL = {
    "schema": 2,
    "version": "check-test",
    "disclaimer": {"rw": "x", "en": "Not a diagnosis.", "fr": "x"},
    "emergency_advice": {"rw": "x", "en": "Go now.", "fr": "x"},
    "first_question": "route",
    "questions": [
        {
            "code": "danger",
            "red_flag": True,
            "text": {"rw": "x", "en": "Danger?", "fr": "x"},
            "options": [
                {"code": "danger_yes", "text": {"rw": "x", "en": "Yes", "fr": "x"},
                 "escalate_emergency": True},
                {"code": "danger_no", "text": {"rw": "x", "en": "No", "fr": "x"},
                 "next_question": "route"},
            ],
        },
        {
            "code": "route",
            "text": {"rw": "x", "en": "Where?", "fr": "x"},
            "options": [
                {"code": "febrile", "text": {"rw": "x", "en": "Fever", "fr": "x"},
                 "recommend_service": "general_consultation"},
                {"code": "dental", "text": {"rw": "x", "en": "Tooth", "fr": "x"},
                 "recommend_service": "dental"},
            ],
        },
    ],
    "symptom_entries": [
        {
            "question": "danger",
            "red_flag": True,
            "phrases": {"rw": ["sinshobora guhumeka"], "en": ["cannot breathe"],
                        "fr": ["je ne peux pas respirer"]},
        },
        {
            "question": "route",
            "implies": ["febrile"],
            "phrases": {"rw": ["umuriro"], "en": ["fever"], "fr": ["fievre"]},
        },
        {
            "question": "route",
            "implies": ["dental"],
            "phrases": {"rw": ["iryinyo"], "en": ["tooth"], "fr": ["dent"]},
        },
    ],
    "conditions": [
        {
            "code": "febrile_illness",
            "names": {"rw": "x", "en": "Febrile illness", "fr": "x"},
            "weights": {"febrile": 3},
            "service": "general_consultation",
        },
        {
            "code": "dental_problem",
            "names": {"rw": "x", "en": "Dental problem", "fr": "x"},
            "weights": {"dental": 3},
            "service": "dental",
        },
    ],
}


@pytest.fixture
def protocol():
    return parse(PROTOCOL, source="test")


# ------------------------------------------------------------------- the flow


def test_free_text_produces_a_condition_and_a_service(protocol):
    result = engine.check(protocol, "I have had a fever for three days")

    assert result.escalate is False
    assert [c.code for c in result.conditions] == ["febrile_illness"]
    assert result.recommendation == "general_consultation"


def test_two_symptoms_both_count(protocol):
    """`match_all`, not `match`. Somebody who says two things has said two
    things - scoring only the longer phrase discards half of it."""
    result = engine.check(protocol, "fever and my tooth hurts")

    assert {c.code for c in result.conditions} == {
        "febrile_illness",
        "dental_problem",
    }


def test_the_service_follows_the_top_condition(protocol):
    result = engine.check(protocol, "my tooth hurts")

    assert result.conditions[0].code == "dental_problem"
    assert result.recommendation == "dental"


# ------------------------------------------------- screening without questions


def test_a_red_flag_phrase_escalates_on_its_own(protocol):
    """The property that had to survive removing the questionnaire.

    In the menu flow every red-flag question is asked before anything else. A
    one-step check has no questions, so the phrase itself has to carry it.
    """
    result = engine.check(protocol, "I cannot breathe")

    assert result.escalate is True


def test_an_escalated_check_returns_no_conditions_and_no_service(protocol):
    """Somebody told to go to hospital must not also be handed a list to
    weigh up, or a clinic to consider instead."""
    result = engine.check(protocol, "I cannot breathe and I have a fever")

    assert result.escalate is True
    assert result.conditions == ()
    assert result.recommendation == ""


def test_a_red_flag_wins_however_it_is_phrased_alongside_other_symptoms(protocol):
    """Order in the sentence must not decide whether screening fires."""
    for text in (
        "fever, tooth pain, cannot breathe",
        "cannot breathe, fever",
    ):
        assert engine.check(protocol, text).escalate is True


# -------------------------------------------------------------- saying nothing


def test_unrecognised_text_recommends_nothing(protocol):
    """A service picked from no signal is a guess wearing a recommendation's
    clothes. `matched` is what lets the client say "we did not understand"
    rather than showing an empty result as if it were reassurance."""
    result = engine.check(protocol, "asdfghjkl")

    assert result.matched is False
    assert result.conditions == ()
    assert result.recommendation == ""


def test_empty_text_matches_nothing(protocol):
    result = engine.check(protocol, "   ")

    assert result.matched is False
    assert result.escalate is False


def test_matching_is_case_and_accent_insensitive(protocol):
    assert engine.check(protocol, "FEVER").conditions
    assert engine.check(protocol, "fièvre").conditions


# ------------------------------------------------------------------- endpoint


@pytest.fixture
def gate_open(settings, tmp_path):
    """This protocol, signed off, so the endpoint can be exercised."""
    import json as _json

    path = tmp_path / "routing.check-test.json"
    path.write_text(_json.dumps(PROTOCOL), encoding="utf-8")
    settings.TRIAGE_PROTOCOL_VERSION = "check-test"
    settings.TRIAGE_APPROVED_BY = "Dr Test, RMDC-0000"
    settings.TRIAGE_APPROVED_ON = "2026-09-01"
    settings.TRIAGE_PROTOCOL_FILE = str(path)
    return path


@pytest.mark.django_db
def test_the_endpoint_is_public_and_needs_no_sign_in(client, gate_open):
    """No account, no session. A patient who is unwell should not have to
    register before finding out where to go."""
    response = client.post(
        "/api/v1/triage/check",
        data={"text": "fever"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["matched"] is True


@pytest.mark.django_db
def test_the_endpoint_is_503_while_the_gate_is_shut(client):
    response = client.post(
        "/api/v1/triage/check",
        data={"text": "fever"},
        content_type="application/json",
    )

    assert response.status_code == 503
