"""Matching what a patient typed to a starting point in the protocol.

The patient wants to say "my tooth hurts" rather than answer a menu. This
module is what makes that possible without moving the clinical decision out of
the signed protocol.

**It chooses a starting question. It never chooses an outcome.**

That distinction is the whole design. A model that reads free text and names a
specialty is making a clinical judgement: non-deterministic, unsignable, and
untraceable to what a given patient saw - which breaks three of the four
requirements in docs/08 section 8. A matcher that only says "start at the
dental branch" makes no clinical claim at all. The recommendation still comes
from the protocol a clinician signed, by the same path it always did.

Two properties keep a bad match harmless:

* **Red-flag screening is unconditional.** `engine.next_question` asks every
  red-flag question before it looks at the entry point, so no phrase, and no
  failure to match a phrase, can route a patient past emergency screening.
  test_symptom_entry.py asserts this for every entry in the lexicon.
* **A wrong match costs a question, not an answer.** The worst case is a
  patient answering something irrelevant before the flow corrects itself.

Matching is deterministic substring matching over a clinician-authored phrase
list, not a model. Same input, same output, forever - which is what lets the
lexicon be signed along with the protocol it lives in.

The typed text itself is never stored. It is matched, reduced to a question
code, and dropped: `docs/08` data minimisation, and free text about symptoms
is the most sensitive thing a patient can hand us.
"""

from __future__ import annotations

import re
import unicodedata

from .protocol import Protocol, SymptomEntry

# Kinyarwanda, English and French all get normalised the same way: casefold,
# strip accents, collapse anything that is not a letter or digit to a single
# space. "Mal aux dents" and "mal aux dents." must match the same phrase, and
# a patient typing on a phone keyboard will not produce clean punctuation.
_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)


def normalise(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text or "").casefold()
    stripped = "".join(c for c in folded if not unicodedata.combining(c))
    return _NON_WORD.sub(" ", stripped).strip()


def _padded(text: str) -> str:
    """Wrap in spaces so substring tests respect word boundaries.

    Without this, the phrase "ear" matches "heart" and a patient with chest
    symptoms is started in the ENT branch. The red flags still run, so it is
    not dangerous - but it is wrong, and it is the kind of wrong that makes a
    patient distrust the whole thing.
    """
    return f" {text} "


def match(protocol: Protocol, text: str) -> tuple[str, str] | None:
    """Return (question_code, matched_phrase), or None if nothing matched.

    The longest matching phrase wins, so a specific entry beats a general one
    that happens to be a substring of it - "chest pain" must not lose to
    "pain". Ties break on declaration order, so the result is stable and a
    clinician reading the file top to bottom can predict it.
    """
    haystack = _padded(normalise(text))
    if not haystack.strip():
        return None

    best: tuple[int, int, str, str] | None = None

    for order, entry in enumerate(protocol.symptom_entries):
        for phrase in entry.all_phrases:
            needle = _padded(normalise(phrase))
            if needle.strip() and needle in haystack:
                candidate = (len(needle.strip()), -order, entry.question, phrase)
                if best is None or candidate > best:
                    best = candidate

    if best is None:
        return None
    return best[2], best[3]


def entry_question(protocol: Protocol, text: str) -> str | None:
    """Just the question code, for callers that do not need the phrase."""
    found = match(protocol, text)
    return found[0] if found else None


def coverage(protocol: Protocol) -> dict[str, int]:
    """Phrase count per entry question, for the review document."""
    return {
        entry.question: len(entry.all_phrases) for entry in protocol.symptom_entries
    }


def unreachable_entries(protocol: Protocol) -> list[SymptomEntry]:
    """Entries whose target question is not reachable from the routing flow.

    Not an error - an entry point is allowed to be a branch the menu never
    offers first. But a clinician should see the list, because an entry
    pointing at a question the protocol can otherwise never ask is usually a
    typo rather than a decision.
    """
    reachable = set(protocol.questions)
    return [e for e in protocol.symptom_entries if e.question not in reachable]


def match_all(protocol: Protocol, text: str) -> tuple[SymptomEntry, ...]:
    """Every entry whose phrase list matches, not just the strongest.

    `match` picks one winner because the menu flow needs a single starting
    question. The direct check needs the opposite: somebody who types "fever
    and headache for three days" has said two things, and scoring only the
    longer phrase would discard half of what they told us.

    Order is declaration order, so a clinician reading the file top to bottom
    can predict the result. Matching is the same deterministic substring pass -
    same input, same output, forever.
    """
    haystack = _padded(normalise(text))
    if not haystack.strip():
        return ()

    found: list[SymptomEntry] = []
    for entry in protocol.symptom_entries:
        for phrase in entry.all_phrases:
            needle = _padded(normalise(phrase))
            if needle.strip() and needle in haystack:
                found.append(entry)
                break

    return tuple(found)
