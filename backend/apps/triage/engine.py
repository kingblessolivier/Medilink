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

from .protocol import Protocol, Question

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


def new_session(protocol: Protocol) -> SessionState:
    state = SessionState(
        session_id=secrets.token_urlsafe(16),
        protocol_version=protocol.version,
        answers={},
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
    if pending in state.asked:
        return None
    return protocol.question(pending)


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
