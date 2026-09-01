"""The clinician review document.

The load-bearing test here is `test_every_enumerated_path_replays_in_the_engine`.
Everything else in this file checks formatting; that one checks that the
document tells the truth, which is the only property that matters when a
clinician's signature is downstream of it.
"""

import pytest

from apps.triage import engine, review
from apps.triage.protocol import parse

pytestmark = pytest.mark.django_db


def _text(en):
    return {"rw": f"[rw] {en}", "en": en, "fr": f"[fr] {en}"}


def _protocol(**overrides):
    """A protocol with two red flags and a two-level routing tree."""
    raw = {
        "schema": 1,
        "version": "test-1",
        "disclaimer": _text("Not a diagnosis."),
        "emergency_advice": _text("Go to emergency now."),
        "first_question": "where",
        "questions": [
            {
                "code": "chest_pain",
                "red_flag": True,
                "text": _text("Chest pain?"),
                "options": [
                    {
                        "code": "yes",
                        "text": _text("Yes"),
                        "escalate_emergency": True,
                    },
                    {"code": "no", "text": _text("No"), "next_question": "where"},
                ],
            },
            {
                "code": "bleeding",
                "red_flag": True,
                "text": _text("Heavy bleeding?"),
                "options": [
                    {
                        "code": "yes",
                        "text": _text("Yes"),
                        "escalate_emergency": True,
                    },
                    {"code": "no", "text": _text("No"), "next_question": "where"},
                ],
            },
            {
                "code": "where",
                "text": _text("Where is the problem?"),
                "options": [
                    {
                        "code": "tooth",
                        "text": _text("Tooth"),
                        "recommend_service": "dental",
                    },
                    {"code": "eye", "text": _text("Eye"), "next_question": "eye_how"},
                ],
            },
            {
                "code": "eye_how",
                "text": _text("How long?"),
                "options": [
                    {
                        "code": "days",
                        "text": _text("Days"),
                        "recommend_service": "ophthalmology",
                    },
                    {
                        "code": "months",
                        "text": _text("Months"),
                        "recommend_service": "general_consultation",
                    },
                ],
            },
        ],
    }
    raw.update(overrides)
    return parse(raw, source="test.json")


# --------------------------------------------------------------- enumeration


def test_paths_begin_with_red_flag_screening_not_first_question():
    """The engine asks every red flag before it looks at `first_question`.

    Enumerating from `first_question` produced paths no patient can take and
    hid the emergency screening completely.
    """
    paths = review.enumerate_paths(_protocol())

    assert paths, "protocol should produce paths"
    for path in paths:
        assert path.steps[0].question.code == "chest_pain"
        assert path.crosses_red_flag


def test_an_escalating_answer_ends_the_path():
    """Escalation is one-way, so nothing may follow it."""
    paths = review.enumerate_paths(_protocol())
    escalations = [p for p in paths if p.is_emergency]

    assert escalations
    for path in escalations:
        assert len(path.steps) == path.steps.index(path.steps[-1]) + 1
        assert path.steps[-1].option.escalate_emergency
        # The escalating answer is the LAST thing asked.
        assert not path.steps[-1].option.next_question


def test_every_enumerated_path_replays_in_the_engine(settings):
    """The document must describe the flow the engine actually runs.

    Each enumerated path is replayed against the real engine: the questions it
    asks, in order, must be exactly the path's questions, and the outcome must
    match. If `engine.next_question` ever changes its sequencing, this fails
    rather than letting the review document quietly drift out of date.
    """
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    protocol = _protocol()

    for index, path in enumerate(review.enumerate_paths(protocol)):
        state = engine.new_session(protocol)

        for step in path.steps:
            asked = engine.next_question(protocol, state)
            assert asked is not None, f"path {index}: engine ran out of questions"
            assert asked.code == step.question.code, (
                f"path {index}: document says the engine asks "
                f"'{step.question.code}' here, engine asks '{asked.code}'"
            )
            state = engine.answer(protocol, state, asked.code, step.option.code)

        assert state.finished, f"path {index}: engine did not finish"
        assert state.has_outcome, f"path {index}: finished with no outcome"

        if path.is_emergency:
            assert state.escalated, f"path {index}: document says emergency"
            assert state.recommendation == ""
        else:
            assert not state.escalated
            assert state.recommendation == path.service, (
                f"path {index}: document says '{path.service}', "
                f"engine gives '{state.recommendation}'"
            )


def test_enumeration_is_bounded():
    paths = review.enumerate_paths(_protocol(), limit=2)
    assert len(paths) == 2


# ----------------------------------------------------------------- coverage


def test_routed_services_lists_every_reachable_service():
    assert review.routed_services(_protocol()) == [
        "dental",
        "general_consultation",
        "ophthalmology",
    ]


def test_unreachable_services_are_reported_not_treated_as_errors():
    """A protocol may cover a subset on purpose - the clinician decides."""
    known = {"dental", "general_consultation", "ophthalmology", "maternity"}
    assert review.unreachable_services(_protocol(), known) == ["maternity"]


def test_unknown_services_are_surfaced():
    """Routing somewhere the directory has never heard of is a dead end."""
    known = {"dental", "ophthalmology"}
    assert review.unknown_services(_protocol(), known) == ["general_consultation"]


# ------------------------------------------------------------------- render


def test_document_contains_every_path_and_the_signoff_block():
    document = review.render(_protocol(), known_service_codes={"dental"})

    assert "TRIAGE PROTOCOL - CLINICAL REVIEW" in document
    assert "PATH 1" in document
    assert "SIGN-OFF" in document
    # The four settings that open the gate, so the reviewer sees exactly what
    # their signature authorises.
    assert "TRIAGE_PROTOCOL_VERSION=test-1" in document
    assert "TRIAGE_APPROVED_BY" in document
    assert "Registration number" in document


def test_document_renders_the_patient_facing_language_asked_for():
    """Kinyarwanda is what most patients read, so it must be reviewable."""
    document = review.render(_protocol(), lang="rw")
    assert "[rw] Chest pain?" in document
    assert "[rw] Not a diagnosis." in document
    # English text must not leak into a Kinyarwanda review.
    assert "\n  Not a diagnosis." not in document


def test_a_protocol_with_no_red_flags_is_called_out_loudly():
    """No emergency screening is the failure mode that kills someone."""
    protocol = _protocol(
        questions=[
            {
                "code": "where",
                "text": _text("Where?"),
                "options": [
                    {
                        "code": "tooth",
                        "text": _text("Tooth"),
                        "recommend_service": "dental",
                    }
                ],
            }
        ],
        first_question="where",
    )
    document = review.render(protocol)
    assert "NO RED-FLAG QUESTIONS" in document
    assert "can send an emergency" in document


def test_truncation_is_stated_rather_than_silent():
    document = review.render(_protocol(), limit=2)
    assert "TRUNCATED" in document
    assert "Split it before signing" in document


def test_unknown_service_codes_are_flagged_in_the_document():
    document = review.render(_protocol(), known_service_codes={"dental"})
    assert "ROUTES TO SERVICES THAT DO NOT EXIST" in document
    assert "ophthalmology" in document


def test_document_says_it_is_not_a_clinical_opinion():
    """The tool must never be mistaken for the review itself."""
    document = review.render(_protocol())
    assert "not a" in document.lower()
    assert "clinical opinion" in document.lower()
