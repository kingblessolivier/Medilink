"""Deterministic triage evaluation.

Three properties, each of which exists because the alternative is dangerous:

**Deterministic.** The same answers always produce the same outcome. No model,
no sampling, no free-form generation. A clinician can read the protocol and
know exactly what a patient will be told.

**Red flags first, and one-way.** Emergency screening questions are asked
before anything else, and an escalation can never be reversed by a later
answer. A patient who reports chest pain is sent to emergency care even if
every subsequent answer looks benign.

**Routing, never diagnosis.** The output is a service type to attend - the same
vocabulary the facility directory already uses. It never names a condition.

Session state lives in Redis with a short TTL. Triage answers are the most
sensitive data this product touches, and docs/08 requires that they are never
linked to a patient row. Only an anonymous aggregate is persisted.
"""

import json
import secrets
from dataclasses import dataclass

from django.core.cache import cache

from . import lexicon
from .protocol import Condition, Protocol, Question

SESSION_PREFIX = "triage:"
SESSION_TTL_SECONDS = 30 * 60


class TriageError(Exception):
    pass


@dataclass
class SessionState:
    session_id: str
    protocol_version: str
    answers: dict
    asked: list
    escalated: bool = False
    recommendation: str = ""
    finished: bool = False

    @property
    def has_outcome(self) -> bool:
        """Did this session actually reach an answer?

        A session can finish three ways: escalated, recommended, or run out of
        questions. The third is a protocol defect, and telling those three
        apart is what stops the last one being served as if it were an answer.
        """
        return self.escalated or bool(self.recommendation)

    def to_json(self) -> str:
        return json.dumps(
            {
                "protocol_version": self.protocol_version,
                "answers": self.answers,
                "asked": self.asked,
                "escalated": self.escalated,
                "recommendation": self.recommendation,
                "finished": self.finished,
            }
        )

    @classmethod
    def from_json(cls, session_id: str, raw: str) -> "SessionState":
        data = json.loads(raw)
        return cls(session_id=session_id, **data)


def new_session(protocol: Protocol, symptom_text: str = "") -> SessionState:
    """Start a flow, optionally from something the patient typed.

    `symptom_text` only chooses WHERE the routing questions begin. It cannot
    reach an outcome and it cannot skip screening: `next_question` below still
    asks every red-flag question first, so the entry point is not consulted
    until screening is done. See lexicon.py for why that ordering is the whole
    safety argument.

    The text is not stored. It is matched here, reduced to a question code,
    and dropped - the session keeps the code, never the sentence.
    """
    answers: dict = {}

    if symptom_text:
        from .lexicon import entry_question

        question = entry_question(protocol, symptom_text)
        if question:
            answers["__entry__"] = question

    state = SessionState(
        session_id=secrets.token_urlsafe(16),
        protocol_version=protocol.version,
        answers=answers,
        asked=[],
    )
    save(state)
    return state


def load_session(session_id: str) -> SessionState:
    raw = cache.get(SESSION_PREFIX + session_id)
    if not raw:
        raise TriageError("That session has expired. Please start again.")
    return SessionState.from_json(session_id, raw)


def save(state: SessionState) -> None:
    cache.set(SESSION_PREFIX + state.session_id, state.to_json(), SESSION_TTL_SECONDS)


def discard(session_id: str) -> None:
    """Triage answers are deleted as soon as the flow ends."""
    cache.delete(SESSION_PREFIX + session_id)


def next_question(protocol: Protocol, state: SessionState) -> Question | None:
    """Red-flag questions first, in protocol order, then the routing flow."""
    if state.finished or state.escalated:
        return None

    for question in protocol.red_flag_questions:
        if question.code not in state.asked:
            return question

    pending = state.answers.get("__next__") or protocol.first_question

    # A typed entry point replaces the FIRST routing question and nothing
    # else. It is kept under its own key because red-flag options carry their
    # own `next_question` - "no, I have no chest pain" points at the normal
    # menu - and that write would otherwise overwrite what the patient typed
    # the moment they cleared screening.
    #
    # Once any routing question has been asked the flow owns the sequence
    # again, so the entry point stops applying rather than pulling the patient
    # back to where they came in.
    entry = state.answers.get("__entry__")
    if entry and not _routing_started(protocol, state):
        pending = entry

    if pending in state.asked:
        return None
    return protocol.question(pending)


def _routing_started(protocol: Protocol, state: SessionState) -> bool:
    """Has anything other than red-flag screening been asked yet?"""
    return any(
        (question := protocol.question(code)) is not None and not question.red_flag
        for code in state.asked
    )


def answer(
    protocol: Protocol, state: SessionState, question_code: str, option_code: str
) -> SessionState:
    # Escalation is ONE-WAY. Once a red flag has fired, nothing a patient
    # answers afterwards may change the outcome - not a benign-looking answer,
    # not a client that keeps posting, not a retry.
    #
    # Without this guard a later `recommend_service` overwrites the emergency
    # escalation and the patient is told to attend a general consultation
    # after reporting a red flag. Returned unchanged rather than raising, so a
    # double-submitting client still sees escalate_emergency and abandons the
    # flow rather than surfacing an error that hides it.
    if state.escalated:
        return state

    if state.finished:
        return state

    question = protocol.question(question_code)
    if question is None:
        raise TriageError("Unknown question.")

    option = next((o for o in question.options if o.code == option_code), None)
    if option is None:
        raise TriageError("Unknown answer.")

    state.answers[question_code] = option_code
    if question_code not in state.asked:
        state.asked.append(question_code)

    if option.escalate_emergency:
        # One-way. Nothing later can undo this.
        state.escalated = True
        state.finished = True
        state.recommendation = ""
        save(state)
        return state

    if option.recommend_service:
        state.recommendation = option.recommend_service
        state.finished = True
        save(state)
        return state

    if option.next_question:
        state.answers["__next__"] = option.next_question

    # Finished when nothing is left to ask.
    if next_question(protocol, state) is None:
        state.finished = True

    save(state)
    return state


# --------------------------------------------------------------------------
# Condition ranking (schema 2)
#
# WHAT THIS IS, precisely, because the words around this feature are loaded.
# It adds up clinician-authored weights for the options a patient actually
# selected, and returns the conditions that scored, in order. There is no
# model and no training data. The whole computation is a signed table plus
# addition, which is what makes it reviewable by the person whose registration
# number is attached to it.
#
# WHAT IT IS NOT is a diagnosis, and two properties keep it from drifting into
# one. Ranking never changes the recommended service - that still comes from
# the protocol's own routing, so the thing a patient is told to DO is
# unaffected by the list. And an escalated session returns no conditions at
# all: when a red flag has fired the only correct output is "go now", and a
# list of possibilities underneath it invites somebody to weigh them up.
#
# The percentage is a SHARE OF THE SCORE THAT MATCHED, not a probability. It
# says "of what your answers pointed at, this was most of it" - not "you have
# a 74% chance of this". Those are different claims and only one of them is
# supportable without prevalence data this protocol does not carry.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RankedCondition:
    code: str
    names: dict
    advice: dict
    score: float
    share: float  # 0..1, this condition's portion of the total score


def rank_conditions(
    protocol: Protocol, state: SessionState, *, limit: int = 3
) -> tuple[RankedCondition, ...]:
    """Rank the protocol's conditions against the answers given so far."""
    # A red flag outranks everything. Offering possibilities to somebody who
    # has just been told to go to hospital gives them something to weigh.
    if state.escalated:
        return ()

    chosen = set(state.answers.values())
    scored: list[tuple[float, Condition]] = []
    for condition in protocol.conditions:
        # All-or-nothing gate before any arithmetic.
        if not set(condition.requires) <= chosen:
            continue
        score = sum(
            weight for option, weight in condition.weights.items() if option in chosen
        )
        if score > 0:
            scored.append((score, condition))

    if not scored:
        return ()

    total = sum(score for score, _ in scored)
    scored.sort(key=lambda pair: (-pair[0], pair[1].code))

    return tuple(
        RankedCondition(
            code=condition.code,
            names=condition.names,
            advice=condition.advice,
            score=score,
            share=score / total,
        )
        for score, condition in scored[:limit]
    )


# --------------------------------------------------------------------------
# The direct check
#
# One box, one answer: a patient types how they feel and gets conditions and a
# service back, with no questionnaire in between. Stateless - nothing is
# stored, and the text itself is dropped the moment it has been matched.
#
# RED-FLAG SCREENING SURVIVED THE SIMPLIFICATION, and it had to. In the menu
# flow every red-flag question is asked before anything else, so no phrase can
# route a patient past emergency screening. Deleting the questions would have
# deleted that guarantee with them. So an entry may itself be marked
# `red_flag`, and one match escalates immediately - no conditions, no service,
# just emergency guidance. Somebody who types "I cannot breathe" must not
# receive a ranked list to think about.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckResult:
    escalate: bool
    conditions: tuple[RankedCondition, ...]
    recommendation: str
    matched: bool  # did anything in the lexicon match at all?


def check(protocol: Protocol, text: str, *, limit: int = 3) -> CheckResult:
    """Match free text, then rank conditions from what it implied."""
    entries = lexicon.match_all(protocol, text)

    if any(entry.red_flag for entry in entries):
        return CheckResult(
            escalate=True, conditions=(), recommendation="", matched=True
        )

    implied = {option for entry in entries for option in entry.implies}
    if not implied:
        # Nothing recognised. Saying so is the honest outcome - a service
        # picked from no signal is a guess wearing a recommendation's clothes.
        return CheckResult(
            escalate=False, conditions=(), recommendation="", matched=bool(entries)
        )

    # Reuse the session ranker rather than growing a second scoring path: one
    # of them would drift, and it would be this one.
    state = SessionState(
        session_id="",
        protocol_version=protocol.version,
        answers={f"implied_{i}": option for i, option in enumerate(sorted(implied))},
        asked=[],
    )
    ranked = rank_conditions(protocol, state, limit=limit)

    # The service still comes from the protocol, never from the condition
    # list: the first ranked condition's own `service`, falling back to the
    # options the text implied.
    recommendation = ""
    for condition in protocol.conditions:
        if ranked and condition.code == ranked[0].code and condition.service:
            recommendation = condition.service
            break
    if not recommendation:
        for question in protocol.questions.values():
            for option in question.options:
                if option.code in implied and option.recommend_service:
                    recommendation = option.recommend_service
                    break
            if recommendation:
                break

    return CheckResult(
        escalate=False,
        conditions=ranked,
        recommendation=recommendation,
        matched=True,
    )
