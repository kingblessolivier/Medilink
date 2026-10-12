# MediLink audit - 12 October 2026

Scope: current checkout at 0da5b46, source inspection, focused reproductions,
frontend tests and production build. No application code changed.

## Assessment

MediLink is a healthcare access and facility operations platform. Its strongest
implemented workflow connects facility discovery, insurance acceptance, appointment
booking, reception check-in and a patient queue view. It is not yet the full clinical,
billing and Ministry system depicted in the design documents.

The Care Guide is deterministic phrase matching plus manually authored symptom
weights. There is no trained AI/ML model or imported medical training dataset in
that implementation. The draft contains 12 conditions and explicitly says it is
unreviewed. Its score shares are not calibrated probabilities of disease.

## Findings

### P1 - Private query data survives account changes

Evidence: web/src/hooks/useAuth.tsx:68 clears tokens and session state but not the
global QueryClient created in web/src/App.tsx. Reception uses the shared keys
`["staff-me"]` and `["board"]`; staff-me is fresh for ten minutes. Team and patient
queries also lack identity/facility keys.

A shared browser can show the previous account's data to the next user while a
request runs, and a fresh cached staff-me response may remain from the previous
facility. Server permissions do not remove data already present in the browser.

Fix: cancel private queries on identity change, clear private caches and scope
private query keys to principal and facility. Test account switches with slow and
failed requests. Static trace; browser cross-account reproduction not run today.

### P1 - Offline actions can replay into another facility

Evidence: web/src/workspace/lib/offlineQueue.ts:27 uses a global `pending:` prefix.
PendingAction has no staff/facility owner. useQueueActions.ts:43 reads the entire
backlog and automatically flushes on mount. backend/apps/queueing/views.py applies
replayed check-ins to the currently authenticated staff member's facility.

An offline check-in created at facility A can therefore be replayed after someone
signs in at facility B, attaching that patient to B and attributing the action to B's
staff member. Existing server scoping cannot detect the original intended facility.

Fix: partition offline storage by facility and actor, verify replay ownership,
preserve other facilities' pending work and test shared-device account switches.
Static trace; no database mutation performed for this audit.

### P1 - Session triage permits emergency-screening bypass

Evidence: backend/apps/triage/engine.py:179 accepts any defined question and option;
it does not require the submitted question to equal next_question(protocol, state).
views.py:172 exposes this through the public answer endpoint.

Reproduced with the draft: expected first question `danger`; submitted `symptoms /
sym_fever`; session finished with general_consultation and danger was never asked.

Fix: enforce expected question and protocol version server-side before changing
state. Retain one-way escalation and add an API regression test for out-of-order
answers. The configured clinical gate limits exposure while closed; it does not
repair this flaw when opened.

### P1 - Free-text Care Guide does not understand negation or danger paraphrases

Evidence: backend/apps/triage/lexicon.py:137 checks whether a normalized phrase is
contained in the text. It does not analyze negation, context or subject.

Reproduced: `I have no fever but my tooth hurts` includes fever at 44% of the
matched score. `I am struggling to breathe` returns matched=False and no emergency
escalation, whereas `I have chest pain` escalates. These are software examples,
not medical recommendations.

Fix: do not treat substring scores as validated disease likelihood. Build explicit
context/negation handling and clinically reviewed danger coverage, then evaluate
on representative rw/en/fr inputs. Existing passing tests do not establish clinical
validity. The shipped draft remains unreviewed.

### P2 - Temporary staff credentials have no supported password-change flow

Evidence: web/src/workspace/Team.tsx:122 tells the admin to ask the colleague to
change their temporary password. The account/staff URLconfs expose no password
change endpoint or corresponding workspace screen, and no forced-change state.

Fix: provide authenticated staff password change, recovery, forced first change and
appropriate token invalidation. Until then the displayed credential is effectively
a permanent password known to the creating administrator.

### P2 - One-step triage returns a server error for an invalid protocol

Evidence: backend/apps/triage/views.py:252 catches TriageUnavailable but not
ProtocolError from _protocol(). The session endpoint handles ProtocolError.
A missing, malformed or version-mismatched configured file therefore propagates
as a server error instead of the intended unavailable response.

Fix: handle ProtocolError consistently, log operational details and return a
controlled unavailable response. Source-confirmed; HTTP reproduction not run.

### P2 - Care Guide facility queue figures do not refresh while results remain open

Evidence: WhereToGo uses useNearbyFacilities, whose hook has staleTime=60000 but
no refetchInterval. StaleTime alone does not schedule a new request. The service
worker also caches nearby responses; this Care Guide view presents no stale-data
notice or explicit timestamp for its "Queue now" badge.

Fix: separate live queue snapshots from reference facility data; refresh explicitly
and show age/offline status. Preserve unknown ETA rather than estimating.

## How the system works

One React/Vite PWA at web/ serves patients (/), facility staff (/workspace) and
platform administrators (/platform). Staff surfaces load as separate chunks.
Translations exist in rw/en/fr, but the staff surface still includes substantial
hardcoded English.

Django/DRF owns authorization and domain rules. PostgreSQL/PostGIS stores facilities,
coordinates, providers, appointments and queue entries. Redis supports cache and
triage session state; Celery handles background work. SMS, USSD and WhatsApp code
connect the same domain functions to other channels.

The central data chain is: a facility configures services, insurance and schedules;
a patient books or walks in; reception creates and transitions queue entries;
position is computed from current entries; service statistics gate the ETA;
travel time and ETA support a leave-by time where inputs exist. Patient queue
updates poll every 20 seconds; there is no WebSocket layer.

Good foundations include generated OpenAPI types, facility-scoped server lookups,
booking capacity locking, queue idempotency, patient access logs, production security
settings and a refusal to manufacture unavailable wait figures. These strengths
do not eliminate the findings above.

## Planned features still absent or partial

- Clinical worklist exists, but no clinical-note, vitals, lab-result or prescription
  model exists. The Clinic screen explicitly states it is not a clinical record.
- Staff account administration exists; credential lifecycle is incomplete.
- Billing/subscription/revenue models and payment integration are absent.
- No separate Ministry principal/portal; platform district aggregates cover only
  part of that plan.
- No trained diagnosis model, model management or dataset evaluation pipeline.
- Web Push subscription infrastructure and SMS receipt webhook remain unbuilt.
- Backup configuration and live operational monitoring need deployment verification.
- Seed commands explicitly mark facility coordinates as approximate. Current live
  facility reporting counts cannot be established without the database.

## Verification and limits

- Frontend: 80 tests passed; TypeScript and Vite production build passed.
- Entry JS: 118.28 kB gzip; lazy map library: 258.52 kB gzip separately.
- Focused backend: 22 condition/check tests passed; two DB-dependent endpoint tests
  deliberately excluded in that successful run. Backend ruff passed.
- Direct engine reproductions confirmed screening bypass and phrase-matching failures.
- Docker daemon is stopped. The attempted database-backed triage run did not finish
  and was stopped. This audit does not claim a fresh full backend pass, live booking
  or queue smoke test, database coverage, or deployed-system security verification.
- Prior conversation test counts and claims that "everything is done" were not used
  as current evidence. README still contains historical counts and broad completion
  language; the code and this scope-limited report should guide the next steps.

Recommended order: fix account/cache isolation and offline ownership first, then
server triage ordering, credential lifecycle, and clinical input validation. Verify
the core booking/check-in/queue journey against the database before deployment.

## Remediation In Progress

Changes on `codex/audit-fixes-dashboard`:

- Clear and cancel query caches across account changes; ignore late session and
  refresh responses after sign-out. Regression tests cover cache and session races.
- Scope pending offline actions to their originating username and facility.
  Preserve legacy ownerless records without replaying them into a guessed account.
  Reject explicitly mismatched ownership at the sync endpoint.
- Enforce current-question and protocol-version checks in the triage engine.
- Return 503 rather than 500 when the one-step protocol fails to load.
- Handle explicit symptom negation and add breathing-distress phrases to the
  unapproved draft. These changes do not constitute clinical validation or approval.
- Add staff/platform password-change screens, current-password verification,
  password validation and token revocation. Existing staff tokens require re-login
  after deploying the revocation setting.
- Poll Care Guide facility queues every 20 seconds using NetworkOnly service-worker
  requests; hide queue figures offline, after errors or after two minutes without a
  successful refresh. Display the time checked and provide district selection.
- Add collapsible mobile dashboard navigation, 44px navigation targets, translated
  workspace navigation and selectable 7/30/90-day report periods.

Current local verification: 87 frontend tests, production build, backend lint and
33 database-independent backend tests pass. Database-dependent password and sync
tests are added but not yet locally verified. Docker's Linux engine is unavailable;
the configured PostGIS port 55432 times out. The separate native PostgreSQL service
rejects the project credentials. No database configuration or credentials were
overwritten. The full backend suite must pass in CI before merge.

Remaining launch gates include clinical approval and evaluation, verified facility
data, end-to-end booking/queue validation against the running stack, deployment
readiness, and the unimplemented clinical-record workflows listed above. This is
not a declaration that the entire roadmap is finished.
