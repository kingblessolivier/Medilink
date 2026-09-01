"""Turn a triage protocol into a document a clinician can actually review.

`check_triage_protocol` proves a protocol is *well formed*: no cycles, no dead
ends, no unreachable questions, every string translated. None of that says
whether the routing is clinically right, and that is the only question the
sign-off in docs/08 section 8 is asking.

A clinician cannot answer it from the JSON. The flow is a graph stored as a
flat list of questions keyed by code, so following one patient's route means
holding a dozen `next_question` pointers in your head at once. What a reviewer
needs is the opposite shape: every distinct path a patient can take, written
out end to end, in the language the patient will read.

So this module enumerates the graph into paths and renders them. It makes no
clinical judgement of its own - it cannot - and it deliberately produces plain
text, because the artefact has to survive being printed, emailed, marked up in
red pen, and filed against a `protocol_version` for the life of the approval.

Two coverage questions get answered here because they are invisible in the
JSON and matter to the review:

* Which services can this protocol actually send a patient to, and are any of
  them not in the directory? (`check_triage_protocol` already errors on this;
  repeated here so the reviewer sees the routing surface in one place.)
* Which services exist in the directory and this protocol can NEVER reach? A
  patient with a dental problem whose protocol has no path to `dental` is not
  a validation error - the file is well formed - but it is a clinical gap, and
  it is the reviewer's call whether it is an acceptable one.
"""

from __future__ import annotations

from dataclasses import dataclass

from .protocol import Option, Protocol, Question

# Enumeration is bounded. The parser already rejects cycles, so a protocol
# cannot loop forever - but a wide, deep graph can still expand into more paths
# than anyone will read, and a review document nobody finishes is not a review.
# Hitting this ceiling means the protocol needs splitting, and the caller is
# told rather than handed a silently truncated document.
MAX_PATHS = 500


@dataclass(frozen=True)
class Step:
    """One question and the answer that was given to it."""

    question: Question
    option: Option


@dataclass(frozen=True)
class Path:
    """One complete route through the protocol, from entry to outcome."""

    steps: tuple[Step, ...]

    @property
    def outcome(self) -> Option:
        return self.steps[-1].option

    @property
    def is_emergency(self) -> bool:
        return self.outcome.escalate_emergency

    @property
    def service(self) -> str:
        return self.outcome.recommend_service

    @property
    def crosses_red_flag(self) -> bool:
        return any(step.question.red_flag for step in self.steps)


def enumerate_paths(protocol: Protocol, limit: int = MAX_PATHS) -> list[Path]:
    """Every route a patient can take, in the order the engine asks them.

    **This mirrors `engine.next_question`, and must keep mirroring it.** The
    engine asks EVERY red-flag question first, in protocol order, before it
    looks at `first_question` at all - so walking the graph from
    `first_question` alone produces paths no patient ever takes, and omits the
    emergency screening entirely. A review document that showed those paths
    would be inviting a clinician to sign off on a flow that does not exist,
    which is worse than having no document.

    Escalation is one-way in the engine: once a red flag fires the session is
    over and nothing later can change the outcome. So an escalating answer
    terminates the path here too, rather than continuing into the routing
    questions.

    Declaration order rather than sorted: the reviewer reads paths in the
    order the questions appear in the file, so a note against "the third
    branch" maps onto something they can find again.
    """
    paths: list[Path] = []
    red_flags = protocol.red_flag_questions

    def walk_routing(code: str, taken: tuple[Step, ...]) -> None:
        if len(paths) >= limit:
            return
        question = protocol.question(code)
        if question is None:  # pragma: no cover - parse() guarantees this
            return
        for option in question.options:
            steps = taken + (Step(question=question, option=option),)
            if option.next_question:
                walk_routing(option.next_question, steps)
            else:
                # Terminal: parse() guarantees an option that does not lead to
                # another question either escalates or recommends a service.
                paths.append(Path(steps=steps))
            if len(paths) >= limit:
                return

    def walk_red_flags(index: int, taken: tuple[Step, ...]) -> None:
        if len(paths) >= limit:
            return
        if index >= len(red_flags):
            walk_routing(protocol.first_question, taken)
            return
        question = red_flags[index]
        for option in question.options:
            steps = taken + (Step(question=question, option=option),)
            if option.escalate_emergency:
                # One-way: the session ends here.
                paths.append(Path(steps=steps))
            elif option.recommend_service and not option.next_question:
                paths.append(Path(steps=steps))
            else:
                # A non-escalating red-flag answer carries on to the remaining
                # red flags. Its own `next_question` is deliberately ignored:
                # the engine does not follow it until every red flag has been
                # asked, so following it here would reorder the flow.
                walk_red_flags(index + 1, steps)
            if len(paths) >= limit:
                return

    walk_red_flags(0, ())
    return paths


def routed_services(protocol: Protocol) -> list[str]:
    """Every service code this protocol can recommend, sorted."""
    return sorted(
        {
            option.recommend_service
            for question in protocol.questions.values()
            for option in question.options
            if option.recommend_service
        }
    )


def unreachable_services(protocol: Protocol, known_codes: set[str]) -> list[str]:
    """Directory services this protocol can never route to.

    Not an error. A protocol may legitimately cover a subset of what the
    country offers - but the reviewer should be the one deciding that, with
    the list in front of them, rather than discovering it from a patient.
    """
    return sorted(known_codes - set(routed_services(protocol)))


def unknown_services(protocol: Protocol, known_codes: set[str]) -> list[str]:
    """Services this protocol routes to that the directory does not have.

    A recommendation the facility search cannot act on is a dead end wearing
    the costume of an answer.
    """
    return sorted(set(routed_services(protocol)) - known_codes)


def _wrap(text: str, width: int, indent: str = "") -> list[str]:
    """Wrap without breaking words. Kinyarwanda compounds are long."""
    words = text.split()
    if not words:
        return [indent.rstrip()]
    lines, current = [], words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= width - len(indent):
            current += " " + word
        else:
            lines.append(indent + current)
            current = word
    lines.append(indent + current)
    return lines


def render(
    protocol: Protocol,
    *,
    lang: str = "en",
    known_service_codes: set[str] | None = None,
    limit: int = MAX_PATHS,
    width: int = 78,
) -> str:
    """The review document, as plain text."""
    out: list[str] = []
    add = out.append

    def rule(char: str = "-") -> None:
        add(char * width)

    paths = enumerate_paths(protocol, limit=limit)
    truncated = len(paths) >= limit

    # ---------------------------------------------------------------- header
    rule("=")
    add("TRIAGE PROTOCOL - CLINICAL REVIEW")
    rule("=")
    add("")
    add(f"Version           {protocol.version}")
    add(f"Source file       {protocol.source}")
    add(f"Language shown    {lang}")
    add(f"Questions         {len(protocol.questions)}")
    add(f"Red-flag screens  {len(protocol.red_flag_questions)}")
    add(f"Distinct paths    {len(paths)}{' (TRUNCATED)' if truncated else ''}")
    add("")
    add("This document is generated from the protocol file. It is not a")
    add("clinical opinion and it does not check whether the routing is")
    add("correct - that is what your review is for.")
    add("")

    if truncated:
        add(f"!! Only the first {limit} paths are shown. The protocol is too")
        add("!! large to review in one document. Split it before signing.")
        add("")

    # ------------------------------------------------------------ what shows
    rule()
    add("SHOWN TO THE PATIENT ON EVERY SCREEN")
    rule()
    add("")
    add("Disclaimer:")
    for line in _wrap(protocol.disclaimer.get(lang, ""), width, "  "):
        add(line)
    add("")
    add("Emergency advice:")
    for line in _wrap(protocol.emergency_advice.get(lang, ""), width, "  "):
        add(line)
    add("")

    # ------------------------------------------------------------- red flags
    rule()
    add("RED-FLAG SCREENING")
    rule()
    add("")
    red_flags = protocol.red_flag_questions
    if not red_flags:
        add("  *** NO RED-FLAG QUESTIONS IN THIS PROTOCOL. ***")
        add("  A protocol with no emergency screening can send an emergency")
        add("  home. Do not sign this without deciding that is intended.")
    else:
        add("These are asked first and can only escalate, never de-escalate.")
        add("")
        for question in red_flags:
            for line in _wrap(question.text.get(lang, ""), width, "  "):
                add(line)
            add(f"    [{question.code}]")
            for option in question.options:
                marker = "-> EMERGENCY" if option.escalate_emergency else ""
                add(f"    - {option.text.get(lang, '')} {marker}".rstrip())
            add("")

    # ----------------------------------------------------------------- paths
    rule()
    add("EVERY PATH A PATIENT CAN TAKE")
    rule()
    add("")
    add("Read each as one patient's whole journey. The outcome is the last")
    add("line: an emergency escalation, or the service they are sent to.")
    add("")

    for number, path in enumerate(paths, start=1):
        flag = " [crosses red-flag screening]" if path.crosses_red_flag else ""
        add(f"PATH {number}{flag}")
        for depth, step in enumerate(path.steps):
            pad = "  " + ("  " * depth)
            for line in _wrap(step.question.text.get(lang, ""), width, pad):
                add(line)
            add(f"{pad}ANSWER: {step.option.text.get(lang, '')}")
        outcome = path.outcome
        if outcome.escalate_emergency:
            add("  => OUTCOME: EMERGENCY. Flow stops, patient told to seek")
            add("     immediate care.")
        else:
            add(f"  => OUTCOME: routed to service '{outcome.recommend_service}'")
        add("")

    # ------------------------------------------------------- symptom entries
    rule()
    add("FREE-TEXT ENTRY POINTS")
    rule()
    add("")
    if not protocol.symptom_entries:
        add("  None. This protocol is menu-only: patients answer questions")
        add("  from the first one, and cannot type how they feel.")
        add("")
    else:
        add("A patient may type how they feel instead of starting at the")
        add("first question. What they type is matched against the phrases")
        add("below and used ONLY to choose which question the flow starts on.")
        add("")
        add("It cannot reach an outcome, and it cannot skip screening: the")
        add("red-flag questions above are asked first whatever was typed.")
        add("These phrases are yours to review - a phrase on the wrong entry")
        add("starts a patient in the wrong part of the flow.")
        add("")
        for entry in protocol.symptom_entries:
            target = protocol.question(entry.question)
            add(f"  STARTS AT: {entry.question}")
            if target is not None:
                for line in _wrap(target.text.get(lang, ""), width, "    "):
                    add(line)
            phrases = entry.phrases.get(lang, ())
            add(f"    phrases ({lang}, {len(phrases)}):")
            for phrase in phrases:
                add(f"      - {phrase}")
            add("")

    # -------------------------------------------------------------- coverage
    rule()
    add("SERVICE COVERAGE")
    rule()
    add("")
    routed = routed_services(protocol)
    add(f"Routes to {len(routed)} service(s):")
    for code in routed:
        add(f"  - {code}")
    add("")

    if known_service_codes is not None:
        unknown = unknown_services(protocol, known_service_codes)
        missing = unreachable_services(protocol, known_service_codes)

        if unknown:
            add("*** ROUTES TO SERVICES THAT DO NOT EXIST IN THE DIRECTORY ***")
            for code in unknown:
                add(f"  - {code}")
            add("  A patient sent here cannot be shown a facility. Fix before")
            add("  signing.")
            add("")

        add(f"Directory services this protocol can NEVER reach ({len(missing)}):")
        if not missing:
            add("  none - every service in the directory is reachable")
        for code in missing:
            add(f"  - {code}")
        add("")
        add("  Not an error. A protocol may cover a subset on purpose. It is")
        add("  your decision whether these gaps are acceptable.")
        add("")

    # -------------------------------------------------------------- sign-off
    rule("=")
    add("SIGN-OFF")
    rule("=")
    add("")
    add("Signing records that you have read every path above and accept the")
    add("routing as clinically safe for the population it serves.")
    add("")
    add("The four settings below open the gate in `apps/triage/gate.py`.")
    add("Until all four are set, every triage endpoint returns 503 and the")
    add("feature stays hidden. A partial approval does not open the gate.")
    add("")
    add(f"  TRIAGE_PROTOCOL_VERSION={protocol.version}")
    add(f"  TRIAGE_PROTOCOL_FILE={protocol.source}")
    add('  TRIAGE_APPROVED_BY="<name>, <registration number>"')
    add("  TRIAGE_APPROVED_ON=<YYYY-MM-DD>")
    add("")
    add("  Clinician name .............................................")
    add("")
    add("  Registration number ........................................")
    add("")
    add("  Signature ..................................  Date .........")
    add("")
    rule("=")

    return "\n".join(out) + "\n"
