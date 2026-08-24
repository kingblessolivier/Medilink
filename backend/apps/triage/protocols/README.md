# Triage protocols

**No clinical protocol ships with MediLink, and this is deliberate.**

A symptom checker routes patients toward or away from care. Getting it wrong
sends somebody home who needed a hospital. The routing rules are a clinical
artefact and must be authored and signed off by a licensed clinician - not
written by the development team, and not generated.

What the codebase provides is the *mechanism*: a schema, a validator, a
deterministic engine, red-flag screening that can only escalate, and a gate
that keeps the endpoints returning **503** until a sign-off is recorded.

`routing.example.json` is a **structural** example. It shows the file format
with two placeholder questions. It is not clinically reviewed, contains no real
triage logic, and its version (`0.0-example`) will not match any approval, so
loading it in a configured environment fails on purpose.

## What a clinician needs to produce

A JSON file matching `schema: 1`, containing:

| Field | Meaning |
|---|---|
| `version` | e.g. `2026.1`. Must match `TRIAGE_PROTOCOL_VERSION` exactly. |
| `disclaimer` | Shown on **every** response, in rw/en/fr. Must say this is not a diagnosis. |
| `emergency_advice` | What to do when a red flag fires, in rw/en/fr. |
| `first_question` | Code of the first routing question. |
| `questions[]` | Each with `code`, `text` (rw/en/fr), `options[]`, optional `red_flag: true`. |

Each option must do exactly one of three things, or the protocol fails to load:

- `escalate_emergency: true` - one-way; nothing later can reverse it
- `recommend_service: "<ServiceType.code>"` - routes to a service the directory knows
- `next_question: "<question code>"` - continues the flow

`recommend_service` must use a `ServiceType.code` that exists in the database,
so the recommendation joins straight onto the facility directory.

## Rules the engine enforces for you

1. **Red-flag questions are asked first**, before any routing question.
2. **Escalation is one-way.** A patient who reports a red flag is sent to
   emergency care even if every later answer looks benign.
3. **Every option must lead somewhere.** An option that neither escalates,
   recommends, nor continues is rejected at load time rather than producing a
   dead end in front of a patient.
4. **The flow may never return to an earlier question.** This is the one that
   catches people out. *"Do you have any other symptoms?" → yes → back to the
   list* is the most natural follow-up in triage, and it does **not** loop:
   the engine asks each question at most once, so coming back to one ends the
   session with no recommendation at all — a completed symptom check that says
   nothing. Rejected at load, with the path named so you can find it.

   Two paths **converging** on a shared follow-up question are fine. That is
   not a return; the shared question is still asked once.

   To ask "anything else?", give the option its own question with its own
   options rather than pointing back.
5. **Every question must be reachable.** A question nothing links to is
   usually a typo in a `next_question`, which leaves your intended question
   silently unasked — so the flow that runs is not the flow you reviewed.
   Red-flag questions are exempt: they are asked before anything else
   regardless of what links to them.
6. **Every string needs all three languages.** A missing translation fails the
   load; it does not silently fall back.
7. **The file version must match the approved version.** Otherwise the sign-off
   record describes something nobody reviewed.

## Turning it on

Only after a named, licensed clinician has reviewed a specific version:

```bash
TRIAGE_PROTOCOL_VERSION=2026.1
TRIAGE_APPROVED_BY="Dr <name>, <registration number>"
TRIAGE_APPROVED_ON=2026-09-01
TRIAGE_PROTOCOL_FILE=apps/triage/protocols/routing.2026.1.json
```

Validate before deploying:

```bash
python manage.py check_triage_protocol apps/triage/protocols/routing.2026.1.json
```

Then complete the remaining items in
[docs/08 section 8](../../../docs/08-security-and-compliance.md): Ministry of
Health and Rwanda FDA consultation, and the disclaimer wording review.

## Seeing the flow without clinical content

To watch the mechanism work - red-flag escalation, routing, the hand-off to
the facility directory - point the gate at the structural example. The version
must match it exactly, which is the deliberate act that stops this happening
by accident:

```bash
# backend/.env - LOCAL ONLY
TRIAGE_PROTOCOL_VERSION=0.0-example
TRIAGE_APPROVED_BY=DEMO - NOT A CLINICIAN
TRIAGE_APPROVED_ON=2026-08-22
TRIAGE_PROTOCOL_FILE=apps/triage/protocols/routing.example.json
```

Then `docker compose -f infra/docker-compose.yml restart api`.

`manage.py readiness` reports this as a **BLOCKER**, so a deployment cannot
carry it to patients even if somebody forgets to unset it. Unset the four
values to close the gate again.

## If in doubt, leave it off

The rest of MediLink delivers its value without a symptom checker. Shipping one
that has not been clinically reviewed would be the single most harmful thing
this project could do.
