# Production readiness

**Question asked:** is MediLink ready to be used by companies?

**Answer:** the software is ready. The *service* is not, and most of what is
missing cannot be written in code.

This document separates those two things, because conflating them is how a
health product gets deployed with a symptom checker no clinician approved and
a database in the wrong country.

---

## 1. Where the software stands

| | |
|---|---|
| Backend tests | 669 passing, 94% coverage |
| Frontend tests | 37 passing |
| API operations | 68 across 64 paths, schema generated with zero warnings, no drift from the committed file |
| Routes | 48 `<Route>` declarations across three surfaces |
| Translations | 401 keys × 3 languages, parity enforced by test |
| Patient bundle | 112.64 KB gzipped (budget 150 KB, enforced in CI) |
| `ruff check apps/` | clean |
| `npm audit` | 0 in production dependencies; 6 in the dev toolchain (see below) |
| `pip-audit` | clean, excluding `pip` itself (the installer, not shipped) |
| Django | 5.2 LTS |

Every figure above was observed on 2026-08-27, in the compose stack, not
carried over from a previous edit.

**This is the third time these numbers have drifted, and the second time the
same correction has been written here.** The previous note recorded that the
test counts had gone stale and that "35 routes" did not match the router; both
were fixed, and within three days every count in the table was wrong again
because PRs #53-#60 landed after it was last measured. The table is the one
thing in the repo people quote without re-checking, so the rule stands and
now has a habit behind it: **a number here is a measurement or it does not
belong.** If you change what the system contains, re-run the checks in
`docs/07` and edit this table in the same PR.

Two rows earned their qualifiers the hard way:

- **`npm audit`** previously read "0 vulnerabilities" without qualification.
  Plain `npm audit` reports 6 (1 critical, 1 high, 4 moderate), all in Vite
  and Vitest. `npm audit --omit=dev` is what reports zero. Nothing vulnerable
  reaches a patient, but the unqualified sentence did not survive somebody
  running the command - and two of the advisories are Windows path-handling
  issues on a team that develops on Windows.
- **`pip-audit`** was reported here while being installed in neither the image
  nor the host venv, so the documented command failed and this result could
  not be reproduced anywhere. It is now pinned in `requirements-dev.txt`. The
  claim itself was accurate: all six findings are in `pip`, exactly the
  exclusion named above.

Run `python manage.py readiness` for the settings-level launch checks. It
exits non-zero on a blocker, so it can gate a deploy.

### The August 2026 audit

A full audit against the proposal produced 26 findings - 13 in the system,
13 in the patient app's design and journeys. All are fixed and merged to
`dev` (PRs #42-#49). Two of them would have blocked a pilot:

- **Registration attached credentials to any phone number without proving
  it.** Every USSD, WhatsApp and reception-created patient has a blank
  password, so anyone who knew a number could claim that person's visit
  history. It now requires a verified one-time code.
- **The wait estimate multiplied a latency by the queue.** The stored
  statistic was `served_at - joined_at` - a patient's whole wait, queue
  included - and the ETA multiplied it by the number of people ahead.
  Simulated at about nine times too high, and worsening with congestion. It
  now measures the gap between consecutive patients being served.

Both survived a 585-test suite because tests asserted the buggy behaviour.
Both of those tests were rewritten rather than deleted, and the frontend
gained its first coverage of a component's failure path.

### The re-audit, 2026-08-27

A third audit covered PRs #53-#60 - 33 commits and roughly 6,700 lines that
had landed after the previous two audits and had never been reviewed. Six
findings, all fixed here. Four were the documentation drift corrected above.
The two in code:

- **A slot could outgrow its session on a partial update.** The rule that a
  slot cannot be longer than the session holding it was enforced on create
  and skipped on every `PATCH`, because the check only compared fields the
  request happened to carry - and it compared the slot length against a
  default of zero, which made the guard a no-op rather than a check. A
  facility could set a four-hour slot on a half-hour session, or shrink a
  session below its slot, and the session would then generate **zero** slots
  while still listing as active: unbookable, with nothing to say why. It now
  validates the session as it will end up, falling back to stored values for
  whatever the request omitted.
- **The USSD address allowlist could be talked past with a header.**
  `client_ip()` read the first `X-Forwarded-For` entry, but nginx forwards
  that header with `$proxy_add_x_forwarded_for`, which *appends* the real peer
  to whatever the caller sent - so the first entry was the caller's own claim.
  Anyone could name an allowlisted address and pass `USSD_ALLOWED_IPS`, and
  every rejection was logged against a spoofable address. The shared secret
  still held, so this was never a way in on its own. It now reads `X-Real-IP`,
  which nginx *replaces* rather than appends, falling back to `REMOTE_ADDR`.

**The pattern from the first audit repeated, and is worth stating plainly.** A
test named `test_a_slot_cannot_be_longer_than_its_session` already existed,
and its docstring described the exact failure - "the session produces zero
slots and reads as broken rather than as misconfigured". It only ever tested
`POST`. Twice now the suite has covered the shape that works rather than the
shape that breaks. When you add a rule, test the update path as well as the
create path; both fixes above ship with tests that were confirmed to fail
against the old code before being kept.

### What works end to end

Verified by driving a browser, not by reading code:

- Patient discovery — search by location or district, facility and doctor
  directories, insurance filtering
- One sign-in for all three user types, routing on the session `kind`
- Facility workspace — keyboard-first check-in measured at **2.6 s** against
  a 10 s budget, appointments, reports
- Platform portal — verification queue, adoption figures, Care Guide
  monitoring
- Offline reception: check-ins queue locally and sync on reconnect — see the
  correction below
- One sign-in account per user type, so every surface can be opened from a
  fresh clone (`manage.py seed_accounts`)

### A claim this document previously got wrong

An earlier version of this table said the offline reception flow was verified
"by driving a browser, not by reading code". The screens were driven. The
**round trip was not**, and it did not work.

The client posted its stored record verbatim — `clientRecordedAt` — to an
endpoint requiring `client_recorded_at`. Every replay returned 400, forever, so
no check-in made during an outage ever reached the server. The backlog was not
even lost; it retried and failed indefinitely, and nothing surfaced it. The
receptionist also got no acknowledgement at all when checking somebody in
offline, because the pending count was computed and never rendered, and the
"you are offline" notice was gated on a board request having failed — which it
does not, since the cached board is served.

Fixed, and pinned three ways: `api.syncQueue` is typed against the generated
schema so the compiler refuses the mismatch, a unit test asserts the wire field
names, and the full round trip is now driven — offline check-in, reconnect,
sync, reload, still there.

The lesson is recorded rather than quietly patched: "verified in a browser" has
to mean the whole path, including the part that only runs when the network is
gone. Opening a screen is not exercising a feature.

---

## 2. What blocks a real launch

None of these are code. All of them are real.

### Clinical

- **No clinician has signed off a triage protocol.** The Care Guide is
  therefore switched off — `apps/triage/gate.py` returns 503 on every triage
  endpoint until four settings are configured, and the UI hides the entry
  points entirely. This is the feature working correctly, not a bug. The rest
  of MediLink delivers its value without it.
- **Ministry of Health and Rwanda FDA have not been consulted** on whether the
  Care Guide is a regulated medical device.

### Legal

- **The privacy notice has not been reviewed by a lawyer.** `/privacy` exists
  in all three languages and describes what the code actually does, but it
  says plainly on the page that it is a draft. Consent captured against an
  unreviewed notice may not be valid consent.
- **No data processing agreements are signed** with any processor — SMS
  gateway, hosting provider, WhatsApp.
- **Hosting location is undecided.** Rwanda Law 058/2021 constrains where
  personal data may live. This has to be settled *before* the first patient
  record exists, not after.

### Operational

- **Nothing has ever been deployed.** `infra/deploy.sh`,
  `docker-compose.prod.yml` and `nginx.conf` are written and have never run.
- **GitHub Actions has never executed a single job.** Every run fails in ~2
  seconds with no runner assigned (`runner_id: 0`, empty `steps`) — an
  account-level Actions block, not a repository problem. **Every test result
  quoted in this document was produced locally.** Until CI runs, there is no
  independent verification that the suite passes on a clean machine.
- **No encrypted backup and no rehearsed restore.** An untested backup is not
  a backup.
- **Admin is not behind an IP allowlist or MFA.**

### Data

- **The 25 seeded facilities are demonstration data.** Coordinates are
  approximate. Before launch, facility locations must be captured on site —
  a patient sent 400 m in the wrong direction in Kigali traffic is a real
  harm, and one wrong pin is worse than no pin.
- **Map tiles come from OpenStreetMap's community servers**, which are
  volunteer-funded and explicitly not for production traffic. A paid tile
  provider or a self-hosted instance is required.

### Channels

- **No USSD shortcode.** Requires RURA and the mobile operators; realistically
  months.
- **No approved WhatsApp templates.** Requires Meta review.

### Not yet tested

- **On a real low-end Android phone on a real 3G connection.** The bundle
  budget and the offline behaviour were verified with throttling in a desktop
  browser, which is not the same thing.
- **A pilot.** docs/09 specifies five unaided days at one facility with a
  stopwatch baseline taken *before* MediLink is installed. Without the
  baseline there is no way to claim the wait times improved.

---

## 3. What "ready for companies" means here

Two different customers, two different answers.

**A facility buying the reception tool** — the workspace is genuinely usable
today. Check-in is measured and fast, the queue works offline, and the reports
answer the four questions a facility manager actually has. What stops a sale
is not the software: it is that nobody has deployed it, no data agreement is
signed, and there is no pilot to point at.

**A patient-facing launch** — blocked on the data quality and legal items
above. Publishing approximate coordinates and an unreviewed privacy notice to
the public is not a soft failure.

---

## 4. Suggested order

1. Decide hosting location, then deploy — nothing else can be validated first
2. Get GitHub Actions unblocked, so the suite is verified somewhere other than
   one laptop
3. Lawyer review of the privacy notice; sign DPAs
4. Field-verify facility coordinates for the pilot facility and its neighbours
5. Encrypted backup with a restore drill
6. Pilot: stopwatch baseline first, then five unaided days
7. Paid map tiles before any public traffic
8. Clinical sign-off — or ship without the Care Guide, which is what the gate
   is designed for

Items 1–6 are weeks. Items 7–8 and the USSD shortcode are months, and none of
them block the facility-facing product.

---

*Last verified 2026-08-24. Every figure here was measured on the date shown,
locally, because CI has never run.*
