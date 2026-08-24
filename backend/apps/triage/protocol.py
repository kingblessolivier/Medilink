"""Protocol loading and validation.

A protocol is DATA, authored by a clinician, not logic written by developers.
This module loads one, validates its shape, and refuses anything malformed -
a protocol that half-loads would route patients on a partial rule set.

Deliberately not a rules engine with arbitrary expressions. Every question is a
fixed multiple choice, every answer maps to a fixed outcome, and evaluation is
a lookup. That makes the whole thing reviewable by the clinician who signs it
off, which a scripting language would not be.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings

SUPPORTED_SCHEMA = 1


class ProtocolError(Exception):
    """A malformed protocol. Never served; fails at load."""


@dataclass(frozen=True)
class Option:
    code: str
    text: dict  # {"rw": ..., "en": ..., "fr": ...}
    # An option may end the flow immediately.
    escalate_emergency: bool = False
    recommend_service: str = ""
    next_question: str = ""


@dataclass(frozen=True)
class Question:
    code: str
    text: dict
    options: tuple[Option, ...]
    # Red-flag questions are asked first and can only escalate, never de-escalate.
    red_flag: bool = False


@dataclass(frozen=True)
class Protocol:
    version: str
    source: str
    languages: tuple[str, ...]
    disclaimer: dict
    emergency_advice: dict
    questions: dict = field(default_factory=dict)
    first_question: str = ""

    def question(self, code: str) -> Question | None:
        return self.questions.get(code)

    @property
    def red_flag_questions(self) -> tuple[Question, ...]:
        return tuple(q for q in self.questions.values() if q.red_flag)


REQUIRED_LANGUAGES = ("rw", "en", "fr")


def _require(data: dict, key: str, where: str):
    if key not in data:
        raise ProtocolError(f"{where}: missing '{key}'")
    return data[key]


def _require_translations(data: dict, where: str) -> dict:
    if not isinstance(data, dict):
        raise ProtocolError(f"{where}: expected a translation object")
    missing = [lang for lang in REQUIRED_LANGUAGES if not data.get(lang)]
    if missing:
        raise ProtocolError(f"{where}: missing translations for {missing}")
    return data


def parse(raw: dict, source: str = "<memory>") -> Protocol:
    schema = raw.get("schema")
    if schema != SUPPORTED_SCHEMA:
        raise ProtocolError(
            f"{source}: unsupported schema {schema!r}, expected {SUPPORTED_SCHEMA}"
        )

    version = _require(raw, "version", source)
    disclaimer = _require_translations(
        _require(raw, "disclaimer", source), f"{source}.disclaimer"
    )
    emergency_advice = _require_translations(
        _require(raw, "emergency_advice", source), f"{source}.emergency_advice"
    )

    questions: dict[str, Question] = {}
    for entry in _require(raw, "questions", source):
        code = _require(entry, "code", source)
        where = f"{source}.questions[{code}]"
        options = []
        for option in _require(entry, "options", where):
            option_code = _require(option, "code", where)
            options.append(
                Option(
                    code=option_code,
                    text=_require_translations(
                        _require(option, "text", where), f"{where}.{option_code}"
                    ),
                    escalate_emergency=bool(option.get("escalate_emergency", False)),
                    recommend_service=option.get("recommend_service", ""),
                    next_question=option.get("next_question", ""),
                )
            )
        if not options:
            raise ProtocolError(f"{where}: a question needs at least one option")

        questions[code] = Question(
            code=code,
            text=_require_translations(_require(entry, "text", where), where),
            options=tuple(options),
            red_flag=bool(entry.get("red_flag", False)),
        )

    first_question = _require(raw, "first_question", source)
    if first_question not in questions:
        raise ProtocolError(f"{source}: first_question '{first_question}' not defined")

    # Every next_question must exist, or a patient reaches a dead end mid-flow.
    for question in questions.values():
        for option in question.options:
            target = option.next_question
            if target and target not in questions:
                raise ProtocolError(
                    f"{source}.{question.code}.{option.code}: "
                    f"next_question '{target}' not defined"
                )
            terminal = (
                option.escalate_emergency
                or option.recommend_service
                or option.next_question
            )
            if not terminal:
                raise ProtocolError(
                    f"{source}.{question.code}.{option.code}: option leads nowhere - "
                    "it must escalate, recommend a service, or ask another question"
                )

    _reject_cycles(questions, first_question, source)
    _reject_unreachable(questions, first_question, source)

    return Protocol(
        version=version,
        source=source,
        languages=REQUIRED_LANGUAGES,
        disclaimer=disclaimer,
        emergency_advice=emergency_advice,
        questions=questions,
        first_question=first_question,
    )


def _links(question: Question) -> tuple[str, ...]:
    return tuple(o.next_question for o in question.options if o.next_question)


def _entry_points(questions: dict, first_question: str) -> list[str]:
    """Where the flow can begin.

    `first_question`, plus anything a red-flag answer routes to - a red flag
    that does not escalate hands the patient on, and that target is reachable
    without ever passing through first_question.
    """
    entries = [first_question]
    for question in questions.values():
        if question.red_flag:
            entries.extend(_links(question))
    return entries


def _reject_cycles(questions: dict, first_question: str, source: str) -> None:
    """A question the flow can return to is a dead end, not a loop.

    The engine asks each question at most once - `asked` guards it - so a
    protocol that routes back to somewhere already answered does not loop. It
    stops. The patient reaches `finished` with no recommendation, no
    escalation and no error: a completed symptom check that says nothing.

    This is not an exotic authoring mistake. "Do you have any other symptoms?
    -> yes -> back to the list" is the most natural follow-up in triage, and
    every option in it escalates, recommends or links to a question that
    exists, so every other check here passes it.

    Rejected at load rather than handled at runtime, because the clinician who
    signed the protocol off needs to know the flow they reviewed is the flow
    that runs.
    """
    WHITE, GREY, BLACK = 0, 1, 2
    colour = dict.fromkeys(questions, WHITE)

    def walk(code: str, path: list[str]) -> None:
        colour[code] = GREY
        for target in _links(questions[code]):
            if colour.get(target) == GREY:
                loop = " -> ".join([*path[path.index(target) :], target])
                raise ProtocolError(
                    f"{source}: the flow can return to '{target}' ({loop}). "
                    "A question is only ever asked once, so this ends the "
                    "session with no recommendation instead of looping."
                )
            if colour.get(target) == WHITE:
                walk(target, [*path, target])
        colour[code] = BLACK

    for entry in _entry_points(questions, first_question):
        if entry in questions and colour[entry] == WHITE:
            walk(entry, [entry])


def _reject_unreachable(questions: dict, first_question: str, source: str) -> None:
    """A question nobody can reach is not the protocol that was reviewed.

    Usually a typo in a `next_question` that points somewhere else, which
    leaves the intended question silently unasked. Red-flag questions are
    always reachable - the engine asks them before anything else, regardless
    of what links to them.
    """
    seen: set[str] = set()
    queue = [e for e in _entry_points(questions, first_question) if e in questions]
    while queue:
        code = queue.pop()
        if code in seen:
            continue
        seen.add(code)
        queue.extend(t for t in _links(questions[code]) if t in questions)

    orphans = sorted(
        code
        for code, question in questions.items()
        if code not in seen and not question.red_flag
    )
    if orphans:
        raise ProtocolError(
            f"{source}: no path reaches {orphans}. A question that cannot be "
            "asked is not part of the flow that was signed off."
        )


def load(path: str | Path) -> Protocol:
    path = Path(path)
    if not path.is_absolute():
        path = Path(settings.BASE_DIR) / path
    if not path.exists():
        raise ProtocolError(f"Protocol file not found: {path}")

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ProtocolError(f"{path}: invalid JSON - {exc}") from exc

    protocol = parse(raw, source=path.name)

    approved_version = getattr(settings, "TRIAGE_PROTOCOL_VERSION", "")
    if approved_version and protocol.version != approved_version:
        # The signed-off version and the file on disk must be the same thing,
        # or the approval record describes something nobody reviewed.
        raise ProtocolError(
            f"{path}: protocol version {protocol.version!r} does not match the "
            f"approved version {approved_version!r}"
        )

    return protocol
