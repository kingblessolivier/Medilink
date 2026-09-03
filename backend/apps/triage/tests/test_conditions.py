"""Condition ranking (protocol schema 2).

The mechanism is simple - add up clinician-authored weights for the options a
patient chose - so most of these tests are about the boundaries that keep a
ranked list from becoming a diagnosis, rather than about the arithmetic.
"""

import pytest

from apps.triage.engine import SessionState, rank_conditions
from apps.triage.protocol import ProtocolError, parse

PROTOCOL = {
    "schema": 2,
    "version": "test-2",
    "disclaimer": {"rw": "x", "en": "Not a diagnosis.", "fr": "x"},
    "emergency_advice": {"rw": "x", "en": "Go now.", "fr": "x"},
    "first_question": "fever",
    "questions": [
        {
            "code": "danger",
            "red_flag": True,
            "text": {"rw": "x", "en": "Danger sign?", "fr": "x"},
            "options": [
                {"code": "danger_yes", "text": {"rw": "x", "en": "Yes", "fr": "x"},
                 "escalate_emergency": True},
                {"code": "danger_no", "text": {"rw": "x", "en": "No", "fr": "x"},
                 "next_question": "fever"},
            ],
        },
        {
            "code": "fever",
            "text": {"rw": "x", "en": "Fever?", "fr": "x"},
            "options": [
                {"code": "fever_yes", "text": {"rw": "x", "en": "Yes", "fr": "x"},
                 "recommend_service": "general_consultation"},
                {"code": "fever_no", "text": {"rw": "x", "en": "No", "fr": "x"},
                 "recommend_service": "general_consultation"},
            ],
        },
    ],
    "conditions": [
        {
            "code": "cond_a",
            "names": {"rw": "A", "en": "Condition A", "fr": "A"},
            "weights": {"fever_yes": 3},
            "service": "general_consultation",
        },
        {
            "code": "cond_b",
            "names": {"rw": "B", "en": "Condition B", "fr": "B"},
            "weights": {"fever_yes": 1},
        },
        {
            "code": "cond_c",
            "names": {"rw": "C", "en": "Condition C", "fr": "C"},
            "weights": {"fever_no": 5},
        },
    ],
}


def protocol():
    return parse(PROTOCOL, source="test")


def state(**answers):
    return SessionState(
        session_id="s", protocol_version="test-2", answers=answers, asked=[]
    )


# ------------------------------------------------------------------ ranking


def test_ranks_by_weight_and_reports_share():
    ranked = rank_conditions(protocol(), state(fever="fever_yes"))

    assert [c.code for c in ranked] == ["cond_a", "cond_b"]
    # A share of what matched - 3 of 4 - not a probability of having it.
    assert ranked[0].share == pytest.approx(0.75)
    assert ranked[1].share == pytest.approx(0.25)


def test_conditions_with_no_matching_answer_are_absent():
    """cond_c keys off `fever_no`, which was not chosen, so it does not appear
    at zero - it is simply not in the list."""
    ranked = rank_conditions(protocol(), state(fever="fever_yes"))

    assert "cond_c" not in [c.code for c in ranked]


def test_no_answers_ranks_nothing():
    assert rank_conditions(protocol(), state()) == ()


def test_limit_is_respected():
    ranked = rank_conditions(protocol(), state(fever="fever_yes"), limit=1)

    assert len(ranked) == 1
    assert ranked[0].code == "cond_a"


# --------------------------------------------- the boundaries that matter


def test_an_escalated_session_ranks_nothing():
    """The one that stops this becoming a diagnosis at the worst moment.

    When a red flag has fired the only correct output is "go now". A list of
    possibilities underneath it invites somebody to weigh them up instead.
    """
    escalated = state(danger="danger_yes", fever="fever_yes")
    escalated.escalated = True

    assert rank_conditions(protocol(), escalated) == ()


def test_ranking_does_not_touch_the_recommended_service():
    """The list is context. What a patient is told to DO still comes from the
    protocol's own routing, so a condition can never redirect care."""
    s = state(fever="fever_yes")
    s.recommendation = "general_consultation"

    rank_conditions(protocol(), s)

    assert s.recommendation == "general_consultation"


# -------------------------------------------------------------- validation


def test_a_weight_naming_an_unknown_option_is_refused():
    """A typo here is a condition that can never rank, failing silently on a
    protocol somebody signed. It fails at load instead."""
    broken = {
        **PROTOCOL,
        "conditions": [
            {
                "code": "cond_typo",
                "names": {"rw": "x", "en": "x", "fr": "x"},
                "weights": {"fevr_yes": 1},
            }
        ],
    }

    with pytest.raises(ProtocolError, match="unknown options"):
        parse(broken, source="test")


def test_conditions_require_all_three_languages():
    broken = {
        **PROTOCOL,
        "conditions": [
            {
                "code": "cond_x",
                "names": {"en": "Only English"},
                "weights": {"fever_yes": 1},
            }
        ],
    }

    with pytest.raises(ProtocolError, match="missing translations"):
        parse(broken, source="test")


def test_empty_weights_are_refused():
    broken = {
        **PROTOCOL,
        "conditions": [
            {"code": "cond_x", "names": {"rw": "x", "en": "x", "fr": "x"}, "weights": {}}
        ],
    }

    with pytest.raises(ProtocolError, match="non-empty"):
        parse(broken, source="test")


# ------------------------------------------------------------ compatibility


def test_a_schema_1_protocol_still_loads_and_ranks_nothing():
    """An already-signed protocol must not become invalid because the software
    learned a new trick."""
    old = {k: v for k, v in PROTOCOL.items() if k != "conditions"}
    old["schema"] = 1

    loaded = parse(old, source="test")

    assert loaded.conditions == ()
    assert rank_conditions(loaded, state(fever="fever_yes")) == ()


# ------------------------------------------------------------------ requires


REQUIRES_PROTOCOL = {
    **PROTOCOL,
    "conditions": [
        {
            "code": "adult_fever",
            "names": {"rw": "x", "en": "Adult fever", "fr": "x"},
            "weights": {"fever_yes": 4},
        },
        {
            "code": "child_illness",
            "names": {"rw": "x", "en": "Child illness", "fr": "x"},
            # Gated: the fever weight exists so a feverish child ranks higher,
            # and must not leak onto an adult who only has a fever.
            "requires": ["fever_no"],
            "weights": {"fever_no": 5, "fever_yes": 1},
        },
    ],
}


def test_a_condition_does_not_score_unless_its_requirements_are_present():
    """The false positive this gate exists for.

    Before `requires`, a small supporting weight on a shared symptom leaked:
    an adult who typed "fever and headache" was shown "a child who is
    unwell", because the paediatric condition carried a fever weight so that
    a feverish child would rank higher.
    """
    ranked = rank_conditions(parse(REQUIRES_PROTOCOL, "test"), state(fever="fever_yes"))

    assert [c.code for c in ranked] == ["adult_fever"]


def test_a_gated_condition_scores_when_its_requirement_is_met():
    ranked = rank_conditions(parse(REQUIRES_PROTOCOL, "test"), state(fever="fever_no"))

    assert [c.code for c in ranked] == ["child_illness"]


def test_requires_naming_an_unknown_option_is_refused():
    broken = {
        **PROTOCOL,
        "conditions": [
            {
                "code": "c",
                "names": {"rw": "x", "en": "x", "fr": "x"},
                "weights": {"fever_yes": 1},
                "requires": ["nope"],
            }
        ],
    }

    with pytest.raises(ProtocolError, match="unknown options"):
        parse(broken, source="test")
