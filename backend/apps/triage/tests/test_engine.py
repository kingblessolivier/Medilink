"""Engine and protocol validation.

The safety properties: red flags first, escalation is one-way, and a malformed
protocol never half-loads.
"""

import pytest

from apps.triage import engine
from apps.triage.protocol import ProtocolError, parse

TEXT = {"rw": "rw", "en": "en", "fr": "fr"}


def protocol_dict(**overrides):
    base = {
        "schema": 1,
        "version": "test.1",
        "disclaimer": TEXT,
        "emergency_advice": TEXT,
        "first_question": "route",
        "questions": [
            {
                "code": "red",
                "red_flag": True,
                "text": TEXT,
                "options": [
                    {"code": "yes", "text": TEXT, "escalate_emergency": True},
                    {"code": "no", "text": TEXT, "next_question": "route"},
                ],
            },
            {
                "code": "route",
                "text": TEXT,
                "options": [
                    {
                        "code": "a",
                        "text": TEXT,
                        "recommend_service": "general_consultation",
                    },
                    {"code": "b", "text": TEXT, "recommend_service": "dental"},
                ],
            },
        ],
    }
    base.update(overrides)
    return base


@pytest.fixture
def protocol():
    return parse(protocol_dict())


# --------------------------------------------------------------------------
# Validation - a malformed protocol never half-loads
# --------------------------------------------------------------------------


def test_unsupported_schema_is_rejected():
    with pytest.raises(ProtocolError, match="unsupported schema"):
        parse(protocol_dict(schema=99))


def test_a_missing_translation_is_rejected():
    """No silent fallback: a patient must not get a Kinyarwanda string inside
    an English flow."""
    data = protocol_dict()
    data["questions"][1]["text"] = {"rw": "only", "en": "", "fr": "x"}

    with pytest.raises(ProtocolError, match="missing translations"):
        parse(data)


def test_a_dangling_next_question_is_rejected():
    data = protocol_dict()
    data["questions"][0]["options"][1]["next_question"] = "nowhere"

    with pytest.raises(ProtocolError, match="not defined"):
        parse(data)


def test_an_option_that_leads_nowhere_is_rejected():
    """A dead end in front of a patient is worse than a load failure."""
    data = protocol_dict()
    data["questions"][1]["options"][0] = {"code": "a", "text": TEXT}

    with pytest.raises(ProtocolError, match="leads nowhere"):
        parse(data)


def test_an_unknown_first_question_is_rejected():
    with pytest.raises(ProtocolError, match="first_question"):
        parse(protocol_dict(first_question="missing"))


def test_a_question_with_no_options_is_rejected():
    data = protocol_dict()
    data["questions"][1]["options"] = []

    with pytest.raises(ProtocolError, match="at least one option"):
        parse(data)


# --------------------------------------------------------------------------
# Red flags first, and one-way
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_red_flag_questions_are_asked_before_routing(protocol):
    state = engine.new_session(protocol)

    question = engine.next_question(protocol, state)

    assert question.code == "red"
    assert question.red_flag is True


@pytest.mark.django_db
def test_escalation_ends_the_flow_immediately(protocol):
    state = engine.new_session(protocol)

    state = engine.answer(protocol, state, "red", "yes")

    assert state.escalated is True
    assert state.finished is True
    assert state.recommendation == ""
    assert engine.next_question(protocol, state) is None


@pytest.mark.django_db
def test_escalation_cannot_be_reversed_by_a_later_answer(protocol):
    """A patient who reports a red flag is sent to emergency care even if
    every subsequent answer looks benign."""
    state = engine.new_session(protocol)
    state = engine.answer(protocol, state, "red", "yes")

    state = engine.answer(protocol, state, "route", "a")

    assert state.escalated is True
    assert state.recommendation == ""


@pytest.mark.django_db
def test_a_clear_red_flag_proceeds_to_routing(protocol):
    state = engine.new_session(protocol)

    state = engine.answer(protocol, state, "red", "no")

    assert state.escalated is False
    assert engine.next_question(protocol, state).code == "route"


# --------------------------------------------------------------------------
# Routing, never diagnosis
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_outcome_is_a_service_not_a_condition(protocol):
    state = engine.new_session(protocol)
    state = engine.answer(protocol, state, "red", "no")

    state = engine.answer(protocol, state, "route", "b")

    assert state.recommendation == "dental"
    assert state.finished is True


@pytest.mark.django_db
def test_the_same_answers_always_give_the_same_outcome(protocol):
    """Deterministic: no model, no sampling. A clinician can read the protocol
    and know exactly what a patient will be told."""
    outcomes = []
    for _ in range(5):
        state = engine.new_session(protocol)
        state = engine.answer(protocol, state, "red", "no")
        state = engine.answer(protocol, state, "route", "a")
        outcomes.append((state.escalated, state.recommendation))

    assert len(set(outcomes)) == 1


@pytest.mark.django_db
def test_unknown_questions_and_options_are_rejected(protocol):
    state = engine.new_session(protocol)

    with pytest.raises(engine.TriageError, match="Unknown question"):
        engine.answer(protocol, state, "nope", "yes")

    with pytest.raises(engine.TriageError, match="Unknown answer"):
        engine.answer(protocol, state, "red", "maybe")


# --------------------------------------------------------------------------
# Session privacy
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_sessions_expire_rather_than_persist(protocol):
    """Triage answers live in Redis with a short TTL and are never written to
    the database - see docs/08."""
    state = engine.new_session(protocol)
    engine.discard(state.session_id)

    with pytest.raises(engine.TriageError, match="expired"):
        engine.load_session(state.session_id)


@pytest.mark.django_db
def test_only_an_anonymous_aggregate_is_persisted(client, protocol, settings, tmp_path):
    """The outcome row must carry no identity and no answers."""
    import json

    path = tmp_path / "p.json"
    path.write_text(json.dumps(protocol_dict()), encoding="utf-8")
    settings.TRIAGE_PROTOCOL_VERSION = "test.1"
    settings.TRIAGE_APPROVED_BY = "Dr Test"
    settings.TRIAGE_APPROVED_ON = "2026-09-01"
    settings.TRIAGE_PROTOCOL_FILE = str(path)

    session = client.post("/api/v1/triage/sessions").json()
    client.post(
        f"/api/v1/triage/sessions/{session['session_id']}/answer",
        {"question": "red", "option": "yes"},
        content_type="application/json",
    )

    from apps.triage.models import TriageOutcome

    outcome = TriageOutcome.objects.get()
    assert outcome.escalated_emergency is True
    assert outcome.protocol_version == "test.1"
    # No identity, and no answers, anywhere on the row.
    field_names = {f.name for f in TriageOutcome._meta.get_fields()}
    assert "patient" not in field_names
    assert "answers" not in field_names
    assert "session_id" not in field_names


@pytest.mark.django_db
def test_a_finished_session_cannot_be_changed(protocol):
    """Regression: a later answer overwrote a completed outcome."""
    state = engine.new_session(protocol)
    state = engine.answer(protocol, state, "red", "no")
    state = engine.answer(protocol, state, "route", "a")

    assert state.recommendation == "general_consultation"

    state = engine.answer(protocol, state, "route", "b")

    assert state.recommendation == "general_consultation"


@pytest.mark.django_db
def test_repeated_escalation_posts_are_harmless(protocol):
    """A double-submitting client must still see the escalation, not an
    error that hides it."""
    state = engine.new_session(protocol)
    state = engine.answer(protocol, state, "red", "yes")

    for _ in range(3):
        state = engine.answer(protocol, state, "route", "a")
        assert state.escalated is True
        assert state.recommendation == ""
