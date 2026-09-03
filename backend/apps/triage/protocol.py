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

SUPPORTED_SCHEMA = 2

# Schema 1 protocols still load. They simply carry no conditions, and the
# engine returns none - which is exactly how this behaved before conditions
# existed, so an existing signed protocol does not become invalid because the
# software learned a new trick.
ACCEPTED_SCHEMAS = (1, 2)


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
class SymptomEntry:
    """A way into the protocol from something a patient typed.

    `phrases` is per language and clinician-authored. It carries NO clinical
    meaning of its own: it only says "text like this starts at this question".
    The routing decision stays in the questions, which is what keeps the whole
    protocol signable as one artefact.
    """

    question: str
    phrases: dict  # {"rw": [...], "en": [...], "fr": [...]}
    # Schema 2, both optional.
    #
    # `implies` lists the option codes this phrase stands in for, so a patient
    # who types "fever and headache" scores the same conditions as one who
    # answered those two questions from the menu. It is what lets the direct
    # check work without a questionnaire.
    #
    # `red_flag` means the phrase alone is enough to escalate. It exists
    # because the direct check has no questions to screen with: in the menu
    # flow every red-flag question is asked before anything else, and removing
    # the questions would have removed the screening with them.
    implies: tuple = ()
    red_flag: bool = False

    @property
    def all_phrases(self) -> tuple[str, ...]:
        return tuple(
            phrase
            for language in REQUIRED_LANGUAGES
            for phrase in self.phrases.get(language, ())
        )


@dataclass(frozen=True)
class Condition:
    """A condition the protocol can rank, and the answers that suggest it.

    THIS IS NOT A DIAGNOSIS AND THE SHAPE OF IT MATTERS. `weights` maps an
    option code to a number a clinician chose - "this answer makes this
    condition more likely, by this much" - and the engine adds up the ones a
    patient actually selected. There is no model, no training set and no
    inference: the whole thing is a table somebody signed.

    That is deliberate rather than a shortcut. A gradient-boosted classifier
    trained on a public symptom-disease dataset produces a number nobody can
    explain, cannot be reviewed by the clinician who has to put their
    registration number against it, and carries the prevalence of whatever
    population it was collected from. In Kigali that last part is not a
    detail: a model that has never seen malaria will not rank it.

    `service` is what the patient should actually DO about it, and it stays
    the primary output. The condition list is context for the conversation
    they are about to have at a facility.
    """

    code: str
    names: dict  # {"rw": ..., "en": ..., "fr": ...}
    weights: dict  # {option_code: float}
    # Every one of these must be present or the condition does not score at
    # all. Without it a condition cannot express "only when a child is
    # involved": "a child who is unwell" carried a small fever weight so a
    # feverish child would rank higher, and that weight leaked onto every
    # adult with a fever, who was then shown a paediatric suggestion.
    requires: tuple = ()
    service: str = ""
    # Shown under the condition. Clinician-authored, per language.
    advice: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Protocol:
    version: str
    source: str
    languages: tuple[str, ...]
    disclaimer: dict
    emergency_advice: dict
    questions: dict = field(default_factory=dict)
    first_question: str = ""
    # Optional. A protocol with none is menu-only, which is the behaviour
    # every existing protocol had before free-text entry existed.
    symptom_entries: tuple = ()
    # Optional, schema 2. Empty on a schema 1 protocol.
    conditions: tuple = ()

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
    if schema not in ACCEPTED_SCHEMAS:
        raise ProtocolError(
            f"{source}: unsupported schema {schema!r}, expected one of "
            f"{list(ACCEPTED_SCHEMAS)}"
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

    symptom_entries = _parse_symptom_entries(raw, questions, source)

    # ------------------------------------------------------------ conditions
    #
    # Optional. Every weight must name an option that exists, because a weight
    # pointing at a typo is a condition that can never be ranked - and it
    # would fail silently, which on a protocol somebody has signed is the
    # worst way for it to fail.
    known_options = {
        option.code for question in questions.values() for option in question.options
    }
    conditions: list[Condition] = []
    for entry in raw.get("conditions", ()):
        code = _require(entry, "code", source)
        where = f"{source}.conditions[{code}]"
        weights = _require(entry, "weights", where)
        if not isinstance(weights, dict) or not weights:
            raise ProtocolError(f"{where}: 'weights' must be a non-empty object")
        unknown = sorted(set(weights) - known_options)
        if unknown:
            raise ProtocolError(f"{where}: weights name unknown options {unknown}")
        try:
            weights = {k: float(v) for k, v in weights.items()}
        except (TypeError, ValueError) as exc:
            raise ProtocolError(f"{where}: weights must be numbers") from exc

        requires = tuple(entry.get("requires", ()))
        unknown_requires = sorted(set(requires) - known_options)
        if unknown_requires:
            raise ProtocolError(
                f"{where}: requires names unknown options {unknown_requires}"
            )

        conditions.append(
            Condition(
                code=code,
                requires=requires,
                names=_require_translations(_require(entry, "names", where), f"{where}.names"),
                weights=weights,
                service=entry.get("service", ""),
                advice=entry.get("advice", {}),
            )
        )

    return Protocol(
        version=version,
        source=source,
        languages=REQUIRED_LANGUAGES,
        disclaimer=disclaimer,
        emergency_advice=emergency_advice,
        questions=questions,
        first_question=first_question,
        symptom_entries=symptom_entries,
        conditions=tuple(conditions),
    )


def _parse_symptom_entries(
    raw: dict, questions: dict, source: str
) -> tuple[SymptomEntry, ...]:
    """Free-text entry points. Optional; absent means a menu-only protocol.

    Validated as strictly as the questions, because a phrase list is the one
    part of the protocol a patient can steer with their own words. Every entry
    must point at a question that exists - an entry pointing nowhere would
    silently fall back to the menu, which looks like the feature ignoring what
    the patient typed.
    """
    entries_raw = raw.get("symptom_entries")
    if entries_raw is None:
        return ()
    if not isinstance(entries_raw, list):
        raise ProtocolError(f"{source}.symptom_entries: expected a list")

    seen: set[tuple] = set()
    entries: list[SymptomEntry] = []

    for entry in entries_raw:
        where = f"{source}.symptom_entries"
        question = _require(entry, "question", where)
        where = f"{where}[{question}]"

        if question not in questions:
            raise ProtocolError(
                f"{where}: question '{question}' is not defined in this protocol"
            )
        implies = tuple(entry.get("implies", ()))
        unknown_implies = sorted(
            set(implies)
            - {o.code for q in questions.values() for o in q.options}
        )
        if unknown_implies:
            raise ProtocolError(
                f"{where}: 'implies' names unknown options {unknown_implies}"
            )

        # Uniqueness is on (question, implies), not on question alone.
        #
        # It was question alone, to stop the menu matcher depending on which
        # of two identical entries came first. Schema 2 gives an entry
        # `implies`, and two entries can now legitimately start at the same
        # routing question while standing in for different symptoms - "fever"
        # and "stomach pain" both open the routing branch and mean different
        # things. Entries that agree on BOTH are still refused, which is the
        # case the original rule was actually protecting against.
        signature = (question, implies)
        if signature in seen:
            raise ProtocolError(
                f"{where}: duplicate entry - merge the phrase lists instead, "
                "so the matcher cannot depend on which one is declared first"
            )
        seen.add(signature)

        phrases_raw = _require(entry, "phrases", where)
        if not isinstance(phrases_raw, dict):
            raise ProtocolError(f"{where}.phrases: expected an object keyed by language")

        phrases: dict[str, tuple[str, ...]] = {}
        for language in REQUIRED_LANGUAGES:
            value = phrases_raw.get(language)
            # Kinyarwanda is the default language of this product. A phrase
            # list that only speaks English routes English speakers and
            # silently ignores everybody else.
            if not value:
                raise ProtocolError(
                    f"{where}.phrases: missing phrases for '{language}'. Every "
                    "entry needs all of " + ", ".join(REQUIRED_LANGUAGES)
                )
            if not isinstance(value, list) or not all(isinstance(p, str) for p in value):
                raise ProtocolError(
                    f"{where}.phrases.{language}: expected a list of strings"
                )
            blank = [p for p in value if not p.strip()]
            if blank:
                raise ProtocolError(f"{where}.phrases.{language}: blank phrase")
            phrases[language] = tuple(value)

        entries.append(
            SymptomEntry(
                question=question,
                phrases=phrases,
                implies=implies,
                red_flag=bool(entry.get("red_flag", False)),
            )
        )

    return tuple(entries)


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
    seen: set[tuple] = set()
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
