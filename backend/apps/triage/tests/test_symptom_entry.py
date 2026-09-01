"""Free-text entry into the protocol.

The load-bearing test is `test_no_phrase_can_skip_red_flag_screening`. Free
text is the one part of the flow a patient steers with their own words, so the
property that must hold for EVERY possible match is that emergency screening
still runs first. Everything else here is matcher behaviour.
"""

import pytest

from apps.triage import engine, lexicon
from apps.triage.protocol import ProtocolError, parse

pytestmark = pytest.mark.django_db


def _text(en):
    return {"rw": f"[rw] {en}", "en": en, "fr": f"[fr] {en}"}


def _raw(**overrides):
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
                    {"code": "yes", "text": _text("Yes"), "escalate_emergency": True},
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
                ],
            },
        ],
        "symptom_entries": [
            {
                "question": "eye_how",
                "phrases": {
                    "rw": ["ijisho ribabaza"],
                    "en": ["my eye hurts", "eye pain", "eye"],
                    "fr": ["mal aux yeux"],
                },
            },
            {
                "question": "where",
                "phrases": {
                    "rw": ["ndwaye"],
                    "en": ["i feel unwell", "pain"],
                    "fr": ["je me sens mal"],
                },
            },
        ],
    }
    raw.update(overrides)
    return raw


def _protocol(**overrides):
    return parse(_raw(**overrides), source="test.json")


def locmem(settings):
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }


# ------------------------------------------------------------------ matching


@pytest.mark.parametrize(
    "typed,expected",
    [
        ("my eye hurts", "eye_how"),
        ("My Eye Hurts!", "eye_how"),  # case and punctuation
        ("  my   eye   hurts  ", "eye_how"),  # whitespace
        ("ijisho ribabaza", "eye_how"),  # Kinyarwanda
        ("mal aux yeux", "eye_how"),  # French
        ("i feel unwell", "where"),
        ("ndwaye", "where"),
    ],
)
def test_matches_across_languages_and_formatting(typed, expected):
    assert lexicon.entry_question(_protocol(), typed) == expected


def test_accents_are_folded():
    """A phone keyboard may or may not produce the accent."""
    assert lexicon.entry_question(_protocol(), "mal aux yeux") == "eye_how"
    assert lexicon.entry_question(_protocol(), "MAL AUX YEUX") == "eye_how"


def test_the_longest_phrase_wins():
    """A specific entry must not lose to a general one inside it.

    "my eye hurts" contains "pain"? No - but it contains "eye", which belongs
    to the same entry. The real risk is a general phrase from ANOTHER entry
    swallowing a specific one, so the longer match is preferred.
    """
    protocol = _protocol()
    # "eye pain" contains both "eye" (eye_how) and "pain" (where).
    # The longer match, "eye pain", must win.
    assert lexicon.entry_question(protocol, "eye pain") == "eye_how"


def test_matching_respects_word_boundaries():
    """"ear" must not match inside "heart"."""
    protocol = _protocol(
        symptom_entries=[
            {
                "question": "eye_how",
                "phrases": {"rw": ["ugutwi"], "en": ["ear"], "fr": ["oreille"]},
            }
        ]
    )
    assert lexicon.entry_question(protocol, "my ear hurts") == "eye_how"
    assert lexicon.entry_question(protocol, "my heart is racing") is None


def test_no_match_returns_none_rather_than_guessing():
    """Guessing an entry point for text we do not recognise is worse than
    falling back to the menu: the patient at least sees a question they can
    answer, instead of a branch chosen at random."""
    assert lexicon.entry_question(_protocol(), "zzzzz qwerty") is None
    assert lexicon.entry_question(_protocol(), "") is None
    assert lexicon.entry_question(_protocol(), "   ") is None


# ------------------------------------------------------------------- safety


def test_no_phrase_can_skip_red_flag_screening(settings):
    """THE safety property. Asserted for every phrase in the lexicon.

    Whatever a patient types, the engine must still ask the red-flag questions
    before anything else. If this ever fails, free-text entry is routing
    people past emergency screening and must be switched off.
    """
    locmem(settings)
    protocol = _protocol()

    for entry in protocol.symptom_entries:
        for phrase in entry.all_phrases:
            state = engine.new_session(protocol, symptom_text=phrase)
            first = engine.next_question(protocol, state)
            assert first is not None
            assert first.red_flag is True, (
                f"typing {phrase!r} started at {first.code!r}, "
                "which is not a red-flag screen"
            )
            assert first.code == "chest_pain"


def test_entry_point_is_used_only_after_screening(settings):
    locmem(settings)
    protocol = _protocol()
    state = engine.new_session(protocol, symptom_text="my eye hurts")

    # Screening first...
    first = engine.next_question(protocol, state)
    assert first.code == "chest_pain"
    state = engine.answer(protocol, state, "chest_pain", "no")

    # ...then the typed entry point, skipping the "where" menu.
    second = engine.next_question(protocol, state)
    assert second.code == "eye_how"


def test_an_escalation_still_wins_over_a_typed_entry_point(settings):
    """Answering the red flag yes ends the session, entry point or not."""
    locmem(settings)
    protocol = _protocol()
    state = engine.new_session(protocol, symptom_text="my eye hurts")
    state = engine.answer(protocol, state, "chest_pain", "yes")

    assert state.escalated
    assert state.finished
    assert state.recommendation == ""
    assert engine.next_question(protocol, state) is None


def test_unmatched_text_falls_back_to_the_normal_first_question(settings):
    locmem(settings)
    protocol = _protocol()
    state = engine.new_session(protocol, symptom_text="zzzzz")
    state = engine.answer(protocol, state, "chest_pain", "no")

    assert engine.next_question(protocol, state).code == "where"


def test_the_typed_text_is_never_stored(settings):
    """docs/08 minimisation: we keep the matched code, never the sentence."""
    locmem(settings)
    protocol = _protocol()
    typed = "my eye hurts"
    state = engine.new_session(protocol, symptom_text=typed)

    serialised = state.to_json()
    assert typed not in serialised
    assert "eye_how" in serialised


# --------------------------------------------------------------- validation


def test_an_entry_pointing_at_an_unknown_question_is_rejected():
    with pytest.raises(ProtocolError, match="not defined"):
        _protocol(
            symptom_entries=[
                {
                    "question": "nope",
                    "phrases": {"rw": ["a"], "en": ["b"], "fr": ["c"]},
                }
            ]
        )


def test_every_entry_needs_all_three_languages():
    """Kinyarwanda is the default language. An English-only phrase list routes
    English speakers and silently ignores everybody else."""
    with pytest.raises(ProtocolError, match="missing phrases for 'rw'"):
        _protocol(
            symptom_entries=[
                {"question": "where", "phrases": {"en": ["pain"], "fr": ["douleur"]}}
            ]
        )


def test_duplicate_entries_for_one_question_are_rejected():
    with pytest.raises(ProtocolError, match="duplicate entry"):
        _protocol(
            symptom_entries=[
                {
                    "question": "where",
                    "phrases": {"rw": ["a"], "en": ["b"], "fr": ["c"]},
                },
                {
                    "question": "where",
                    "phrases": {"rw": ["d"], "en": ["e"], "fr": ["f"]},
                },
            ]
        )


def test_blank_phrases_are_rejected():
    """A blank phrase normalises to nothing and would match every input."""
    with pytest.raises(ProtocolError, match="blank phrase"):
        _protocol(
            symptom_entries=[
                {
                    "question": "where",
                    "phrases": {"rw": ["a"], "en": ["  "], "fr": ["c"]},
                }
            ]
        )


def test_a_protocol_without_symptom_entries_is_still_valid():
    """Menu-only is what every protocol was before this existed."""
    raw = _raw()
    del raw["symptom_entries"]
    protocol = parse(raw, source="test.json")
    assert protocol.symptom_entries == ()
    assert lexicon.entry_question(protocol, "my eye hurts") is None


# ------------------------------------------------------- the review document


def test_the_review_document_lists_the_phrases_for_signing():
    """The lexicon is clinical content, so the clinician must see it.

    A phrase on the wrong entry starts a patient in the wrong branch. That is
    a clinical judgement, which means it belongs in the document they sign
    rather than only in the JSON.
    """
    from apps.triage import review

    document = review.render(_protocol(), lang="en")

    assert "FREE-TEXT ENTRY POINTS" in document
    assert "my eye hurts" in document
    assert "STARTS AT: eye_how" in document
    # And it must say what the phrases can and cannot do.
    assert "cannot skip screening" in document


def test_the_review_document_says_when_a_protocol_is_menu_only():
    from apps.triage import review

    raw = _raw()
    del raw["symptom_entries"]
    document = review.render(parse(raw, source="test.json"), lang="en")
    assert "menu-only" in document


def test_review_renders_phrases_in_the_language_asked_for():
    from apps.triage import review

    document = review.render(_protocol(), lang="rw")
    assert "ijisho ribabaza" in document
