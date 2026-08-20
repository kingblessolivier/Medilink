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
4. **Every string needs all three languages.** A missing translation fails the
   load; it does not silently fall back.
5. **The file version must match the approved version.** Otherwise the sign-off
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

## If in doubt, leave it off

The rest of MediLink delivers its value without a symptom checker. Shipping one
that has not been clinically reviewed would be the single most harmful thing
this project could do.
