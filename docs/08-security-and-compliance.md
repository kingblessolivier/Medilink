# 08 - Security and Compliance

> **This document is engineering guidance, not legal advice.** MediLink processes
> health data about identifiable people in Rwanda. Before launch, have the
> specifics confirmed by a qualified Rwandan lawyer and by the National Cyber
> Security Authority (NCSA). Treat everything below as the floor, not the ceiling.

## 1. What makes this project higher-risk than a normal app

We hold records showing **that a named person attended a named health facility
for a named service on a given date**. That is sensitive health data even though
we store no diagnosis. A leak could expose someone's maternity care, mental
health visit, or HIV clinic attendance.

Design accordingly: the safest data is the data we never collect.

## 2. Rwandan legal framework

The governing instrument is **Law N° 058/2021 of 13/10/2021 relating to the
protection of personal data and privacy**, supervised by the NCSA. The points
that most affect our architecture:

| Area | Practical implication for MediLink |
|---|---|
| Registration | Data controllers and processors are generally required to register with the supervisory authority. Budget time and fees; start early. |
| Sensitive data | Health data receives heightened protection and generally requires explicit consent and a documented lawful basis. |
| Cross-border transfer | Transferring personal data outside Rwanda is restricted and may require authorisation. **This constrains where we host.** |
| Data subject rights | Access, rectification, objection, and erasure must be technically supported, not handled by email alone. |
| Breach notification | Breaches must be reported to the authority within a defined window. Have the runbook written before you need it. |

**Consequence: decide hosting location before writing deployment code.** Defaulting
to a cheap EU or US region and "sorting the legal side later" can force a
migration of production health data - the most expensive kind of rework there is.

Prefer a Rwandan or regional data centre. If any processor sits abroad (an SMS
gateway, an error tracker, a WhatsApp API), document that flow and confirm its
lawful basis.

Sector rules from the **Ministry of Health** and **Rwanda FDA** may also apply,
particularly to the symptom checker. Ask before building, not after.

## 3. Data minimisation

The strongest control available to us, applied per field:

| Field | Decision | Reasoning |
|---|---|---|
| Phone number | **Collect** | Required identity across three channels |
| Name | **Optional** | A queue works with a ticket code alone |
| National ID | **Do not collect**, or hash | We never need the number, only identity matching |
| Date of birth | **Do not collect** | Not needed for booking or queueing |
| Symptoms / diagnosis | **Do not store** | Triage answers are transient - see 3.1 |
| Insurer | **Collect** | Core to the product promise |
| Home location | **Optional, opt-in** | Improves "leave by"; not required |
| GPS at search time | **Do not persist** | Use it for the query, then discard |

Do not log search coordinates in application logs. A log of "who searched for a
maternity clinic from which location, at what time" is a sensitive dataset
created by accident.

### 3.1 Triage answers

Symptom-checker answers are the most sensitive data the product touches. Keep the
session in **Redis with a short TTL**, and persist only an anonymous aggregate
(protocol version, recommended service type, timestamp bucket) for improving the
rules. Never link triage answers to a `Patient` row.

### 3.2 Hashing the national ID

If a facility partnership later requires ID matching:

```python
import hashlib
from django.conf import settings

def hash_national_id(value: str) -> str:
    normalised = "".join(ch for ch in value if ch.isdigit())
    return hashlib.sha256(
        (settings.NATIONAL_ID_PEPPER + normalised).encode()
    ).hexdigest()
```

The pepper lives in the environment, never in the database, so a database dump
alone does not allow brute-forcing the (short, structured) ID space. Rotating it
invalidates all stored hashes - treat rotation as a migration, not a config edit.

## 4. Authentication and authorisation

### Patients

OTP over SMS. No passwords - patients will not manage them, and password reuse
would be worse than an OTP.

| Control | Setting |
|---|---|
| Code length | 6 digits |
| Expiry | 5 minutes |
| Attempts | 5, then the code is invalidated |
| Request rate | 3 per phone per 15 min; 20 per IP per hour |
| Enumeration | `POST /auth/otp/request` always returns `204` |
| Storage | Store a hash of the code, not the code |

### Staff

Username and password, plus per-facility scoping.

**Every provider-side queryset must be filtered by the caller's facility.**
Enforce it once, centrally:

```python
class FacilityScopedMixin:
    def get_queryset(self):
        staff = getattr(self.request.user, "staffmember", None)
        if staff is None or not staff.active:
            raise PermissionDenied
        return super().get_queryset().filter(facility_id=staff.facility_id)
```

Never rely on each view remembering to filter. One forgotten `.filter()` exposes
another clinic's patient list, and that is the breach that ends the project.

Add a test that asserts staff at facility A receive `403`/`404` for every object
belonging to facility B. Run it against every staff endpoint.

## 5. Transport and storage

| Control | Requirement |
|---|---|
| TLS | 1.2 minimum, HSTS enabled, HTTP redirected |
| Database at rest | Full-disk encryption on the database volume |
| Backups | Encrypted, tested restore **monthly** - an untested backup is not a backup |
| Secrets | Environment variables or a secret manager; never in git |
| Admin access | Restricted by IP allowlist and protected with MFA |
| Database access | No direct production access for developers; use read replicas and audited tooling |

```python
# config/settings/production.py
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
```

## 6. Audit logging

Every read and write of an identifiable patient record must be attributable.

```python
class PatientAccessLog(models.Model):
    actor       = models.ForeignKey("auth.User", on_delete=models.PROTECT)
    patient     = models.ForeignKey("patients.Patient", on_delete=models.PROTECT)
    action      = models.CharField(max_length=20)     # view | check_in | update
    facility    = models.ForeignKey("facilities.Facility", on_delete=models.PROTECT)
    occurred_at = models.DateTimeField(auto_now_add=True)
    ip_address  = models.GenericIPAddressField(null=True)
```

Retain for at least one year. Review monthly for anomalies - a receptionist
viewing hundreds of records outside their shift is the signal this table exists
to surface.

**Never log:** phone numbers in plaintext application logs, OTP codes, JWTs,
search coordinates, or full request bodies on patient endpoints. Configure the
logging formatter to redact, and add a test that asserts a known phone number
does not appear in captured log output.

## 7. Data subject rights

Each right needs an implementation, not a policy page.

| Right | Implementation |
|---|---|
| Access | `GET /me/export` returns JSON of everything held about the caller |
| Rectification | `PATCH /me` |
| Erasure | `DELETE /me` - see below |
| Objection | Notification opt-out per channel, honoured by the sender |

Erasure cannot simply delete rows: a facility may have a legitimate interest in
its own attendance records. Implement it as **anonymisation**:

```python
def anonymise_patient(patient):
    patient.queue_entries.update(patient=None, walk_in_name="")
    patient.appointments.update(patient=None)
    patient.notifications.all().delete()
    patient.phone = f"deleted-{uuid4().hex[:12]}"
    patient.full_name = ""
    patient.national_id_hash = ""
    patient.home_location = None
    patient.save()
```

The facility keeps its counts; the person is no longer identifiable.

## 8. The symptom checker - specific risk

Anything that routes patients toward or away from care carries clinical
liability.

**Requirements before this feature may ship:**

- [x] Rule-based and deterministic. **No free-form LLM** answering "what disease
      do I have".
- [ ] Built from a published, citable triage protocol - not written by the
      development team from intuition.
- [ ] Reviewed and signed off by a licensed clinician, with the sign-off recorded
      against a `protocol_version`.
- [x] Framed as *routing guidance*, never diagnosis, in all three languages.
- [x] Red-flag escalation always present (the ENGINE enforces one-way
      escalation; the QUESTIONS are the clinician's to write): chest pain, difficulty breathing,
      heavy bleeding, unresponsiveness, convulsions in a child -> immediate
      "go to emergency now", flow abandoned.
- [x] Disclaimer shown on every screen, not once at onboarding.
- [ ] Ministry of Health and Rwanda FDA consulted on classification.
- [x] Every session logged with its `protocol_version`, so a later rule change is
      traceable to what a given patient actually saw.

**If any box is unticked, ship the product without the symptom checker.** The
rest of MediLink delivers its value without it.

### How this is enforced in code

The checklist above is not trusted to a checklist. `apps/triage/gate.py` refuses
to serve any triage endpoint unless **all four** of these are configured:

```
TRIAGE_PROTOCOL_VERSION    the exact version a clinician reviewed
TRIAGE_APPROVED_BY         their name and registration number
TRIAGE_APPROVED_ON         the date of sign-off
TRIAGE_PROTOCOL_FILE       the file they reviewed
```

With any of them missing, `/triage/*` returns **503** and `/triage/status`
reports `available: false` with a reason. That is the default in every
environment, including production. A partial approval does not open the gate -
it is somebody having forgotten a step.

**No clinical protocol ships with the codebase.** What ships is the mechanism:
a schema, a validator, a deterministic engine, and red-flag screening that can
only escalate. The routing rules are a clinical artefact and are authored by a
clinician. `apps/triage/protocols/README.md` describes what they need to
produce; the example file carries a version that cannot match any approval, so
it fails to load on purpose.

Three safety properties are enforced by the engine rather than by protocol
authors remembering them:

1. **Red-flag questions are asked first**, before any routing question.
2. **Escalation is one-way.** Nothing a patient answers afterwards can reverse
   it.
3. **Every option must lead somewhere** - escalate, recommend a service, or ask
   another question. An option that does none is rejected at load time rather
   than becoming a dead end in front of a patient.

The recommendation is always a `ServiceType` code, never a condition name, and
`manage.py check_triage_protocol` fails if a protocol routes to a service the
facility directory does not have.

Session answers live in Redis with a 30-minute TTL and are discarded the moment
the flow ends. Only `TriageOutcome` persists, and it deliberately has no
patient link, no session id and no answers - just protocol version, outcome,
date and hour bucket. The hour bucket rather than a timestamp is so a row
cannot be correlated with a queue check-in a minute later to re-identify
somebody.

## 9. Third-party processors

| Processor | Data shared | Location | Notes |
|---|---|---|---|
| USSD aggregator | Phone number, menu choices | Regional | Data processing agreement required |
| SMS gateway | Phone number, message body | Regional | Message bodies contain facility names - minimise |
| Meta (WhatsApp) | Phone number, message content | Outside Rwanda | Cross-border transfer - document the basis |
| Error tracking | Stack traces | Often outside Rwanda | **Scrub PII before sending**, or self-host |
| Map tiles | Coordinates | Outside Rwanda | Prefer a source that does not log user coordinates |

Keep a record of processing activities listing each of these, what is shared, why,
and under what agreement. Maintain it from day one - reconstructing it later is
painful.

## 10. Incident response

Write this runbook **before** it is needed:

1. **Detect** - alerting on error-rate spikes, unusual admin logins, unusual
   `PatientAccessLog` volume.
2. **Contain** - revoke sessions and rotate secrets; the commands should be
   pre-written, not improvised at 2 a.m.
3. **Assess** - which records, how many people, what categories of data.
4. **Notify** - the supervisory authority within the legally defined window, and
   affected patients where required. Draft the SMS copy in advance, in all three
   languages.
5. **Remediate and record** - fix, then write the post-mortem.

Name a person responsible for this. On a student team, "everyone" means nobody.

## 11. Pre-launch security checklist

- [x] `DEBUG = False` in production, verified by a deployment check -
      `manage.py readiness` blocks on it
- [x] `SECRET_KEY` unique per environment, never committed - `readiness`
      blocks on a short or placeholder key
- [x] `ALLOWED_HOSTS` explicit, no wildcard - `readiness` blocks on `*`
- [ ] TLS enforced, HSTS on, valid certificate
- [x] Facility scoping tested across every staff endpoint
- [x] Rate limits active on OTP, sign-in and anonymous browsing -
      `readiness` blocks on an unset bucket
- [x] No PII in application logs - redacted on the HANDLER by
      `config/logging.py`, so it applies to third-party loggers too, and
      asserted by `config/tests/test_log_redaction.py`
- [ ] Backups encrypted, restore drill completed and documented
- [x] Dependency audit clean - `npm audit` reports 0; `pip-audit` reports
      only advisories against `pip` itself, which is the installer and not
      shipped. Django 5.0 (EOL, 9 advisories) was upgraded to 5.2 LTS
- [ ] Admin behind IP allowlist with MFA
- [ ] Data processing agreements signed with every processor
- [~] Privacy notice published in Kinyarwanda, English and French - the
      page exists at `/privacy` in all three, written from what the code
      actually does, but has NOT been reviewed by a lawyer. It says so.
- [x] Consent captured and recorded at registration, with a timestamp AND
      the notice version agreed to. Null for USSD patients, because nobody
      collected it and a backfilled timestamp would be a manufactured record
- [x] Erasure endpoint implemented and tested - anonymises rather than
      deletes, so a facility keeps its counts
- [ ] NCSA registration completed
- [ ] Legal review of the privacy notice and consent flow completed
