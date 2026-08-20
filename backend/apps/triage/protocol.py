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

    return Protocol(
        version=version,
        source=source,
        languages=REQUIRED_LANGUAGES,
        disclaimer=disclaimer,
        emergency_advice=emergency_advice,
        questions=questions,
        first_question=first_question,
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
