# 11 - Redesign Roadmap

**Status: in progress. Started 2026-08-20.**

This document supersedes [09-roadmap-and-milestones.md](09-roadmap-and-milestones.md)
for all work after Phase 4. Doc 09 remains the record of how the backend was
built and why; this is the plan for turning it into the product described in the
redesign brief.

It exists so that work can be resumed cold, by anyone, without re-deriving the
audit or re-litigating the design decisions.

---

## 1. What the brief asks for

A premium healthcare discovery and access platform for Rwanda: 51 screens
across four surfaces (public, patient, facility workspace, admin portal), a
reusable design system, an interactive map as a first-class feature, a global
doctors/services/insurance directory, an AI Care Guide, and a connected journey
where each feature feeds the next.

The brief's own governing instruction, and the one that shapes everything below:

> Do not design screens independently. Design a connected healthcare journey.

And its recurring constraint, which happens to match the rule this codebase
already lives by:

> Only show information that is actually available from the backend. Do not
> fabricate coverage or costs. Do not invent qualifications.

## 2. Audit: what actually exists (2026-08-20)

Verified against the code, not from memory.

### Backend - strong, and mostly reusable

| App | State |
|---|---|
| `facilities` | Facility, ServiceType, FacilityService, OpeningHours. PostGIS geo search with tiered ranking and radius expansion. **Keep as-is.** |
| `insurance` | Insurer, FacilityInsurer. Facility-level acceptance only. **Needs extending - see gap 3.** |
| `patients` | Patient (phone identity), OTP auth, privacy export/erasure, PatientAccessLog. **Keep.** |
| `staff` | StaffMember with facility scoping. **Keep; extend for doctor profiles.** |
| `queueing` | QueueEntry, ServiceTimeStat, ETA, `leave_by`, offline sync. **Keep - this is the product.** |
| `scheduling` | ScheduleTemplate, Appointment, slot expansion, capacity locking. **Keep.** |
| `notifications` | SMS templates, dedup by DB constraint, Celery tasks. **Keep.** |
| `gateway` | USSD router, WhatsApp webhook. **Keep, unaffected by redesign.** |
| `triage` | Engine, protocol schema, validator, clinical gate. **Keep the gate. See gap 5.** |

396 backend tests, 92% coverage, 28 endpoints, committed OpenAPI schema.

### Frontend - thin, and the real gap

| Surface | Screens today | Brief asks for |
|---|---|---|
| Public / patient | 7 (Home, Search, FacilityDetail, Book, SignIn, Visits, Profile) | 31 |
| Facility workspace | 2 (Login, Reception) | 10 |
| Admin portal | 0 (Django admin only) | 10 |

13 shared components between the two apps. No design system - each app had its
own ad-hoc Tailwind theme.

## 3. The five blocking data gaps

These are why the redesign is not a redesign. Roughly 20 of the 51 screens
cannot be built until the data model behind them exists.

### Gap 1 - There is no doctor

`StaffMember.CLINICIAN` is a **login role**, not a profile. There is no name,
photo, specialty, language, biography, or per-doctor availability anywhere in
the system.

**Blocks:** Doctors directory, doctor profile, facility doctors tab, doctor
selection during booking, AI-to-doctor routing, facility doctor management.
**That is 8+ screens.**

**Decision:** build a `providers` app. `Provider` is distinct from
`StaffMember` - a doctor may not have a login, and a receptionist is not a
doctor. Link optionally.

### Gap 2 - There are no specialties

The system has `ServiceType` (what a facility offers) but no `Specialty` (what
a clinician practises). The brief's central AI flow - *symptoms → specialty →
doctors → facilities* - has no specialty to route to.

**Decision:** add `Specialty`, and a many-to-many from `Specialty` to
`ServiceType` so a recommendation can reach the existing facility search.

### Gap 3 - Insurance is facility-level, not service-level

The brief shows per-service coverage:

```
Mutuelle  ✓ Accepted
General Consultation ✓   Dental — Partial
```

We store only "this facility accepts Mutuelle". `FacilityInsurer.note` is free
text. Per-service coverage does not exist, and **must not be invented** - a
patient turned away at a counter because we implied coverage is a real harm.

**Decision:** extend to `FacilityServiceInsurer` with an explicit
`coverage` enum (`full` / `partial` / `not_covered` / `unknown`), defaulting to
`unknown`. The UI shows "Not confirmed" until a facility states otherwise.

### Gap 4 - There is no map

Deliberately deferred in [04-nearby-facilities.md](04-nearby-facilities.md) §8:
ship the list first, because a list is faster on 3G, accessible, and is what a
patient actually needs. The brief makes the map a core feature, which is a
legitimate change of priority.

**Decision:** MapLibre GL with a free tile source, **lazy-loaded behind the
list**. The list stays the default and the fallback. Map and list stay
synchronised in both directions. Never a key-metered commercial API.

### Gap 5 - The AI Care Guide is switched off, and stays off

`apps/triage` is built and returns **503** until four settings record a named
clinician's sign-off. No clinical protocol ships with the repo.

The brief agrees with this - it asks for a knowledge base that is
"independently researched and medically validated" and for the product to
emphasise "care guidance rather than automated diagnosis".

**Decision:** build the entire Care Guide **UI, flow, and integration** against
the existing engine. Do not author clinical content. Do not touch the gate.
When no approval is configured, the Care Guide entry points are **hidden**, not
shown broken - `GET /triage/status` already exists to drive exactly that.

### Also missing, and deliberately not built

**Ratings and reviews.** The brief hedges every mention ("rating if supported
by the existing system"). Ratings on healthcare providers are a serious product
decision with real reputational consequences for named clinicians, and they
need a moderation policy before a schema. **Out of scope until asked for.**

## 4. Design system decisions (locked)

Established in `design/tailwind-preset.js` and `design/base.css`, shared by
both apps so the surfaces cannot drift.

| Token | Value | Note |
|---|---|---|
| canvas | `#F7F9F8` | page background |
| surface | `#FFFFFF` | cards, tables, sheets |
| line | `#E3E8E5` | default border |
| ink | `#17201C` | primary text |
| ink-muted | `#66716C` | secondary text |
| primary | `#0B6B55` | actions, availability, verification |
| unknown | `#8B948F` | **data we do not have** |

Three rules the preset encodes, because they are what a healthcare UI gets
wrong most often:

1. **Green is not the interface.** It carries availability, verification,
   success and the primary action. Everything structural is neutral.
2. **Radius stops at 12px** for containers. Pills are reserved for status, so
   the shape itself carries meaning.
3. **Elevation is almost flat.** One overlay shadow, one hairline. Borders
   separate; shadows only float.

Plus the rules inherited from the existing product:

4. **Unknown data is the quietest thing on screen.** The `unknown` palette
   exists so a patient can tell "we do not know" from "we know" without
   reading. This is the wait-status rule from docs/04 made visual.
5. **Status is never colour alone.** Every chip pairs a colour with a word.
6. **Tabular figures everywhere.** Queue positions and times must not shift
   width as they tick.
7. **Cards are for facilities, doctors, appointments and summaries.**
   Everything else is a list, a table, a section or whitespace.

Type scale: caption 12 / small 13 / body 15 / h3 17 / h2 21 / h1 28 /
display 40 / queue 72. Inter, tabular numerals.

## 5. Phases

Ordered by the brief's own priority list (§ Final Instruction), with the data
gaps slotted in where they unblock screens.

### R0 - Design system foundations `DONE`

- [x] `design/tailwind-preset.js` - colour, type, radius, shadow, spacing
- [x] `design/base.css` - base layer, component classes, reduced-motion
- [x] Wired into both apps via Tailwind `presets` + `postcss-import`
- [x] Primitives in `web-patient/src/ui`: Button, Spinner, Field, TextInput,
      Select, Chip, Card, Skeleton, CardSkeleton, ListSkeleton, EmptyState,
      ErrorState, Notice, Tabs
- [x] `WaitLine` rebuilt on the `unknown` palette - the honesty rule made visual
- [x] `FacilityCard` rebuilt: distance, open state, insurance, wait, actions
- [x] Home rebuilt on the system, with the B/C/A state ordering explicit
- [x] `src/ui` copied into web-provider (R6) and web-admin (R7)
- [x] DoctorCard, MapMarker (`.ml-marker`)
- [x] Component gallery at `/_gallery`, lazy-loaded and excluded from precache

**Not built: ServiceCard, InsuranceBadge, AvailabilityPicker, Timeline,
Dialog, Sheet.** Nothing imports them. Services render inline where they
appear, insurance is a `Chip`, slot selection lives in Book, and no screen
needs a modal - cancelling deliberately has no confirmation dialog. Extracting
a component pays at the SECOND call site; building one before that is guessing
at an API for a caller that does not exist.

**The gallery earned itself immediately.** It exists because the same failure
happened three times: `index.css` became the design-system import, the old
classes stopped existing, and screens not touched since rendered unstyled -
with type checks, tests and the build all green. On first render it exposed
two more:

- `Spinner` was a bare `<span>`, which is `display: inline`, so `h-4 w-4` did
  nothing and it collapsed to a 2px sliver. It only ever looked right because
  every call site so far had it inside an `inline-flex` button, which
  blockifies its children. Fixed in all three copies.
- `Button`'s `variant` defaults to `secondary`, not `primary`. That is correct
  - a button nobody thought about should not claim the emphasis of the one
  action on the screen - but it was undocumented. The gallery now states it.

**Contrast, now measured rather than assumed.** R8 recorded that contrast had
not been machine-verified. It has been now, and three token pairs failed:

| Token | Was | Ratio | Now | Ratio |
|---|---|---|---|---|
| `ink-subtle` | `#8B948F` | 3.12 | `#69726D` | 4.77 |
| `unknown` | `#8B948F` | 2.84 | `#69726D` | 4.52 |
| `ink-muted` | `#66716C` | 4.44 on danger-subtle | `#4F5A55` | 6.22 worst case |

`unknown` mattered most: "Not confirmed" is the honesty label, and being the
quietest thing on the screen must not mean a patient cannot read it.

`ink-muted` had to move as well. Darkening `ink-subtle` alone would have
collapsed it into `ink-muted`, leaving two tokens that looked identical. The
measurement also showed a real limit: **no three-tier grey scale clears 4.5:1
on the tinted status backgrounds**, so `ink-subtle` is documented as
surface-and-sunken only - the tinted surfaces carry their own text colour.

Verified: every text/background pair across eight routes now meets WCAG AA.

**Gotcha worth keeping:** `design/base.css` must be imported *before* the
`@tailwind` directives and needs `postcss-import` first in the PostCSS chain.
Without it the import is silently dropped and both apps render unstyled. Also:
Tailwind emits `rgb(11 107 85 / …)`, not hex - grepping compiled CSS for
`#0B6B55` finds nothing and proves nothing.

### R1 - Providers and specialties (backend) `DONE`

Unblocks 8+ screens. Nothing in R3 or R5 could start without it.

- [x] `providers` app: `Specialty`, `Provider`, `ProviderFacility`
- [x] `Specialty` <-> `ServiceType` many-to-many, so a recommendation reaches
      the facility search that already exists
- [x] Optional `ProviderFacility` <-> `StaffMember` link
- [x] Endpoints: `/specialties`, `/providers`, `/providers/{slug}`,
      `/facilities/{slug}/providers`
- [x] `/facilities/nearby?specialty=` filter
- [x] `ScheduleTemplate.provider` and `Appointment.provider`, both optional
- [x] Admin with a verification action, `fixtures/specialties.json` (11 rows),
      demo doctors in `seed_demo`, 18 tests

**Decisions worth keeping:**

- **Providers are many-to-many with facilities.** Clinicians in Rwanda commonly
  hold a public post and consult privately; a single FK would force us to pick
  one and hide the other from search.
- **`ScheduleTemplate` was reused, not duplicated.** A template with
  `provider=None` is the facility's "any available" clinic; with a provider it
  is that clinician's own session. Slot expansion, capacity locking and
  cancellation all work unchanged - a parallel availability model would have
  duplicated every one of them.
- **A specialty with no mapped services returns nothing, not everything.**
  Silently widening to every facility would send a patient anywhere. The admin
  flags unroutable specialties with a "Reaches facilities" column.
- **An explicit `service` beats an inferred `specialty`.** A patient's own
  choice always wins over a recommendation.
- **A doctor with no active placement is never listed.** They cannot be booked,
  and listing them sends a patient after an appointment that does not exist.
- **No ratings; no unverified qualifications.** `bio_en` carries an admin
  warning that a doctor profile is a public statement about a named person.
  Every demo doctor is created unverified.

### R2 - Discovery: home, find care, map `DONE`

The brief's highest priority, and the strongest screen in the product.

- [x] Global search: one `/search` over specialties, services, doctors and
      facilities, grouped and ordered by what reaches care fastest
- [x] Find Care: 40/58 split, filter rail in the URL, list <-> map selection
      synchronised both ways
- [x] MapLibre, lazy-loaded, list-first fallback, map opt-in on mobile
- [x] Location: auto, district fallback, never blocks
- [x] Homepage: hero, universal search, nearby, doctors near you, popular
      services, insurance, Care Guide entry
- [x] Search-as-you-type: a real combobox with `aria-activedescendant`,
      grouped results, arrow-key navigation, 250 ms debounce
- [x] `DoctorCard` with initials fallback and honest verification state
- [x] Compare facilities: max 3, six rows, selection in the URL
- [x] Old list-only `Search.tsx` deleted - Find Care supersedes it

**More decisions worth keeping:**

- **The Care Guide entry points are hidden, not disabled**, when
  `/triage/status` reports unavailable - which is the shipped default. A button
  that errors is worse than no button, and implying the feature exists when no
  clinician has reviewed it is worse still. `useTriageStatus` defaults to
  hidden: if we cannot tell, we do not offer it.
- **The doctors section is omitted entirely when no doctors are listed**,
  rather than rendering an empty shelf.
- **Doctor avatars fall back to initials.** Most clinicians have no photo on
  file; a grey person-icon placeholder pretends something is missing.
- **Verification is stated, not implied.** An unverified doctor says so in the
  quiet `unknown` chip rather than looking identical to a checked one.
- **Popular services and insurers are links, not cards.** Sixteen cards would
  be exactly the wall the brief warns against.
- **Compare is capped at three and six rows.** A comparison a patient cannot
  read at a glance has failed at the one job it has.

**Decisions worth keeping:**

- **Specialties and services rank above named results.** Somebody typing
  "dental" almost always wants dentistry near them, not the one dentist whose
  name contains those letters.
- **Empty groups are omitted, not returned empty**, and a query under two
  characters returns nothing rather than everything.
- **The map is excluded from the service-worker precache.** It is a 258 KB
  gzipped chunk; precaching it would push it onto every phone at install and
  undo the lazy import. Fetched on demand, then cached for a month.
- **Filters live in the URL**, so a search can be shared or reloaded, and a
  Care Guide recommendation arrives as `?specialty=` with a banner the patient
  can clear.
- **Tiles are inline OSM raster.** MapLibre's demotiles style carries only
  low-zoom country outlines and renders as empty blue at city zoom. **Before
  launch this must move to a self-hosted or contracted source** - the OSM
  community servers are volunteer-funded and a health service should not lean
  on them.

**Three bugs found by running it:**

1. **Duplicate facilities.** A specialty maps to several service codes, so a
   facility offering more than one of them (paediatrics *and* vaccination)
   joined once per match and was listed twice. Needed `.distinct()` - and only
   on the specialty branch, since a single `service` matches at most one row.
2. **No markers.** The marker effect ran before the async map import resolved,
   found no map, returned early, and never re-ran. Fixed with a readiness flag.
3. **The suite became order-dependent.** DRF throttles per IP through a shared
   cache; as the suite grew, later tests started getting 429 from a budget
   spent by earlier ones. A test could pass alone and fail in the full run.
   Now `config/settings/test.py` disables throttling and uses a local-memory
   cache. Rate limits belong in tests that assert them explicitly.

### R3 - Facility profile `DONE`

- [x] Header: name, location, verified, open state, book, directions
- [x] Tabs: Overview / Services / Doctors / Insurance / Opening hours
- [x] **Per-service live status** - `facility_service_waits`, same four states
      and the same sample gate as everywhere else
- [x] **`FacilityServiceInsurer`** - gap 3 from section 3 is now closed
- [x] Doctor list on the facility, using R1
- [x] Global doctors directory, filtered by specialty, language and name
- [x] Doctor profile page
- [x] Service detail page
- [x] Doctors added to the bottom navigation (five items, still the cap)
- [ ] Appointments and Queue tabs - deferred to R4, where the booking
      redesign lives

**Two more decisions:**

- **Language is a first-class filter in the doctors directory.** A patient who
  is only comfortable in Kinyarwanda needs to know which clinician can consult
  in it *before* they travel - exactly the kind of thing a directory answers
  and a phone call does not.
- **An unverified doctor profile carries a warning, not just a chip.** It is a
  public page about a named person; the page says plainly that MediLink has
  not confirmed it with the facility.
- **Service detail is a lens, not a record.** It composes entirely from
  existing endpoints - facilities offering it, doctors delivering it, the
  specialties behind it - because a service is a view over the directory
  rather than a thing with its own row.

**Decisions worth keeping:**

- **Coverage defaults to `unknown`, and an unconfirmed row publishes as
  `unknown` whatever was entered.** Absence of data is not evidence of
  coverage, and somebody part-way through data entry must not accidentally
  publish a claim. A patient turned away at a counter because we implied
  coverage is a real harm.
- **No price, anywhere.** There is a test asserting the payload contains no
  cost words at all. We hold no verified cost data and a wrong number is worse
  than none.
- **The insurance tab carries a disclaimer on every view**: this is what the
  facility told us it accepts, not confirmation that your own cover is active.
- **A service with no statistics is listed with `insufficient_data`**, never
  dropped - dropping it would silently shorten the service list.
- **Query-count tests assert shape, not a ceiling.** Instead of "at most N
  queries", they measure the cost for two services and require it to be
  identical for twelve. A ceiling breaks whenever a prefetch is added; the
  shape is the property that actually matters.

**A bug worth remembering:** removing `select_related("service_type")` to
respect a caller's prefetch introduced an N+1 for every caller that had no
prefetch. The fix is neither - `facility_service_waits` now takes the services
as a parameter, so the caller that already has them passes them, and the caller
that does not gets `select_related`.

### R4 - Booking and queue `DONE`

Not purely a redesign after all - R1 added `ScheduleTemplate.provider` but the
booking logic still ignored it, so slots and capacity had to be made
provider-aware first.

- [x] Slots and booking are provider-aware
- [x] `GET /appointments/{id}`, scoped to the caller
- [x] Booking: service -> doctor -> time -> review -> confirm, four steps
- [x] Confirmation screen (same screen as the appointment, `?new=1`)
- [x] Queue tracking, full-screen, `leave_by` as the hero
- [x] Notification centre and per-kind preferences
- [x] Patient dashboard - the Home state ordering already does this job; a
      separate dashboard would be a second home screen

**Notification decisions:**

- **Opt-out is honoured inside `dispatch()`**, not at each call site, so no
  sender can forget to check. This closes the "right to object" item from
  docs/08 section 7.
- **Some messages cannot be switched off.** A sign-in code is something a
  patient asked for by trying to sign in; a facility cancelling on them is
  something not telling them would be worse than any amount of unwanted
  messaging. `OPTIONAL_KINDS` names the rest.
- **An attempt to disable a transactional kind is refused, not ignored.** A
  toggle that appears to work and does nothing is worse than one that says no,
  and the UI renders those as fixed rather than as a dead switch.
- **Turning off "you are being called" carries a warning** - it is the one
  that costs a patient their turn.
- **Preference rows exist only for opt-outs.** Absence means enabled, which
  keeps the table small and makes the default obvious.
- **History shows only what was actually sent**, and never sign-in codes - a
  code is not a message somebody received, and listing it would leave it
  readable long after it expired.

**Decisions worth keeping:**

- **The general clinic and a named clinician are separate capacity pools.**
  `provider=None` is the facility's general session - staff assign whoever is
  free, which is how booking at a health centre actually works. Booking on one
  must not consume the other, or a busy waiting room would silently close
  every clinician's list.
- **"Any available" is the default and the first option**, because naming a
  doctor narrows availability and most patients neither need to nor know whom
  to pick. When a named clinician has no slots, the empty state offers "any
  available" rather than a dead end.
- **The confirmation is the appointment screen with `?new=1`**, not a separate
  page. A one-time confirmation screen is one a patient can never get back to,
  and the reference code is exactly what they need to find again.
- **Cancelling has no confirmation dialog.** A booking nobody honours is worse
  than no booking, so cancelling is one tap with an explanation underneath.
- **`leave_by` is hidden when null**, never filled with a placeholder, and the
  UI explains which of the two reasons applies - no home location, or not
  enough queue history. A patient will act on a time they are shown.

### R5 - Care Guide (UI only; gate untouched)

- [x] Landing, dynamic follow-ups, staged progress, result
- [x] Urgency/red-flag presentation with immediate escalation
- [x] Result → service → facilities → booking
- [x] **Entry points hidden entirely when `/triage/status` reports unavailable**
- [x] Disclaimer on every step, in all three languages

**The gate was not touched.** It is still shut in every environment, and the
screen was verified in both states: unstubbed against the real 503 (zero entry
points on Home, and a typed URL explains it is awaiting a clinician), and with
intercepted responses to drive the flow itself. Opening the gate to test the
UI would have been the wrong trade.

Decisions worth keeping:

- **The result is a SERVICE, never a specialty or a condition.** The protocol
  returns a service code and nothing else, so there is no path by which a
  condition name can reach the screen. `?service=` is already the search
  screen's filter, so the result hands straight off to a filtered search.
- **The service NAME comes from the backend**, which holds all three
  languages. `t()` returns the key itself for a miss, so a client-side lookup
  would have rendered `service_dialysis` at a patient.
- **Progress counts answers rather than showing a bar.** The protocol
  branches, so the total is unknown; a bar would jump backwards when a branch
  turned out to be longer than the last.
- **Escalation is terminal in the UI as well as the engine.** No control on
  the emergency screen leads back into the flow - a patient told to seek
  emergency care must not be able to answer their way out of that advice.
- **The red-flag chip is kept despite the priming risk.** Labelling a
  screening question "urgent" may push a frightened patient toward "yes", but
  an unnecessary hospital trip is a far cheaper mistake than a missed red flag.
- **The emergency number lives in the language bundle**, not in JSX, so a
  safety-critical value is correctable without a code change.

### R6 - Facility workspace

- [x] Sidebar shell, distinct from the patient surface
- [x] Queue, keeping the keyboard-first check-in - re-verified in a browser
      after the rebuild: focus lands in the phone field on arrival and returns
      there after every submit, round trip 2.0 s against a 10 s budget
- [x] Appointments: today's list, arrive / serve / no-show, and a way back
      from a mis-tapped no-show
- [x] Doctors and Services, as a patient sees them
- [x] Reports: appointments, no-shows, median wait, service demand

**Scope decision - management screens are read-only.** The brief asked for
"doctor / service / insurance management". Built as read-only instead, because
a facility that can edit its own coverage and its clinicians' credentials is a
facility that can publish "you are covered" and unverified qualifications - the
two things rule 5 and rule 6 exist to prevent. Both screens say who to contact
instead. Changing this needs an admin approval step first (R7), not a form.

**Not built, and why:**

- **Dashboard.** The Reports screen opens on a "Today" band carrying the three
  numbers a dashboard would have shown. A second screen repeating them earns
  nothing.
- **Patients list.** A facility-wide searchable patient index is the highest
  standing privacy risk in the product and the appointment and queue screens
  already name the people actually attending today. It needs the docs/08
  access-log review designed around it before it is built, not after.
- **Schedule management.** No endpoint exists for editing `ScheduleTemplate`,
  and shipping the nav item before the endpoint would be a door onto nothing.

### R7 - Admin portal

- [x] Shell, overview, facility and provider verification queue
- [x] Care Guide monitoring, reading `TriageOutcome` aggregates only
- [x] Platform analytics: adoption, verification backlog, booking channels
- [x] Providers - verification workflow. CRUD stays in Django admin

Lives in a third Vite app, `web-admin` on port 5175, superuser-only.

**Why a third app rather than a section of the reception app.** The provider
app's entire session model is "which facility am I?" - `/staff/me` requires a
`StaffMember` row. Platform admin is the opposite: it crosses every facility
and has no facility at all. Bolting an unscoped surface onto a scoped app
would put the two permission models one routing mistake apart.

**`is_staff` is not enough; it takes a superuser.** `is_staff` only means "may
open Django admin" and gets granted to whoever needs to edit one lookup table.
Reading platform-wide figures and approving a hospital into patient-facing
search is a different privilege, and conflating them is how a lookup-table
editor ends up verifying hospitals.

**Verification requires a note, and the button stays disabled without one.**
An approval with no record of what was checked is indistinguishable from a
mis-click, and this mis-click puts a facility in front of patients. There is
no "reject" and no "unverify": rejection is a conversation, and un-verifying
would overwrite the record of who approved it. Both stay in Django admin.

**Not built, and why:**

- **Patients.** The brief listed a patients section. It was not built and the
  backend cannot serve one: `/platform/overview` returns a patient COUNT, and
  there is no endpoint that returns patient records to an admin. A
  country-wide searchable patient index is the single largest privacy exposure
  this product could create, and nothing in platform administration needs it.
  A test pins the payload shape so widening it is deliberate.
- **Appointments, queues, insurance CRUD.** Django admin already registers
  every model. Rebuilding forty change forms would add surface area and an
  audit gap; the sidebar links across to it instead.
- **Settings.** The settings that matter - the clinical gate, SMS credentials,
  aggregator allow-lists - are environment variables on purpose. A web form
  that edits them would be a way to open the triage gate by mis-click.

### R8 - Cross-cutting

- [x] Every screen: loading skeletons, empty states, error states
- [x] Care Guide shows the question it is on, never "Loading..." (R5)
- [x] Responsive: mobile, tablet, desktop - measured, no overflow at any size
- [x] Accessibility pass: focus, keyboard, labels, touch targets
- [x] rw/en/fr for every new string, key parity enforced in CI
- [x] Bundle budget: patient app 101 KB gzipped against 150 KB

**Three live regressions found by auditing rather than assuming.** All three
came from the same cause: when `index.css` became the design-system import in
R0, the old `.card`, `.field` and `.btn-primary` classes stopped existing, and
every file not touched since kept using them.

1. The provider app's check-in button rendered as plain text (fixed in R6).
2. **SignIn, Profile and Visits in the patient app, plus six components.** The
   sign-in button - the entrance to everything behind authentication - was
   unstyled text. Now measured: green, 44 px, 8 px radius.
3. `.ml-card` carries no padding where the old `.card` did, so six migrated
   cards had content flush against the border.

**Two behavioural bugs found in the same pass:**

- **Profile saved on blur with no failure surfaced.** A patient edited their
  name, the request failed, and the new value stayed on screen - identical to
  success. Now surfaced with a retry.
- **`general-medicine` was being shown to patients.** The provider API
  returned specialty CODES; one screen worked around it with a lookup against
  `/specialties`, three did not. The API now returns the code and all three
  names, the same shape `ServiceBrief` uses. Changing the type caught two of
  the three stale call sites at compile time; the third used `.join()`, which
  compiles happily on an array of objects and would have rendered
  `[object Object]` at a facility manager.

**Measured, not asserted:**

- Focus ring visible on **12/12** tab stops on the primary path
- No horizontal overflow at 390 / 820 / 1440 px on eight routes
- No unlabelled controls, no image without `alt`, every page starts at `h1`
- Language toggle was **36x26 px** - below any usable target, on a control
  present on every screen and the first thing a Kinyarwanda speaker looking at
  an English page reaches for. Now 44x44.
- Doctor cards: the name was a **20 px-tall** link and the card was not
  tappable. A stretched link makes the whole **374x133** card the target
  without adding a second link for a screen reader to announce.

**Honest limit:** `.ml-btn-sm` is 36 px. That meets WCAG 2.5.8 (AA, 24 px) but
not 2.5.5 (AAA, 44 px). It is used for secondary and inline actions; primary
actions use the full-size button at 44 px. Inline text links sit at 20 px and
are exempt under 2.5.8. Contrast was NOT machine-verified - the tokens were
chosen for it, but nothing in this pass measured contrast ratios.

## 6. Screen inventory

The brief listed 51 screens. Counting them as 51 separate routes would be
dishonest in both directions - some were folded into a screen that already
answered the question, and some were deliberately not built. So:

`+` built · `~` folded into another screen · `x` deliberately not built,
reason given · `-` genuinely outstanding

**Public (23) - 21 addressed**

`+` Homepage · `+` Find Care · `+` Map discovery · `+` Search results ·
`+` Facility profile · `+` Facility overview · `+` Facility doctors ·
`+` Doctor profile · `+` Facility services · `+` Service detail ·
`+` Facility insurance · `+` Booking · `+` Confirmation · `+` Queue tracking ·
`+` Care Guide landing · `+` Symptom assessment · `+` AI result ·
`+` AI recommended facilities · `+` Compare ·
`~` AI processing - the flow shows which question you are on; a protocol that
branches has no honest progress bar, so there is no separate screen ·
`~` Global insurance - the home screen lists insurers and links into a
filtered search; a standalone page would repeat it ·
`-` About · `-` Help

**Patient (8) - all addressed**

`+` Appointments (Visits) · `+` Appointment detail · `+` Active queue ·
`+` Notifications · `+` Profile ·
`~` Dashboard - the home screen already leads with your queue and your next
appointment when signed in ·
`~` Insurance - the insurer preference lives in Profile, one field ·
`~` Settings - language sits in Profile and message preferences in
Notifications, each next to what it affects

**Facility (10) - 6 addressed**

`+` Appointments · `+` Queue (Reception) · `+` Doctors · `+` Services ·
`+` Reports ·
`~` Insurance - shown per service on the Services screen, where a manager is
already looking at what patients see ·
`~` Dashboard - Reports opens on a "Today" band with the numbers a dashboard
would repeat ·
`x` Patients - a facility-wide searchable patient index is the largest
standing privacy exposure in the product. The appointment and queue screens
already name the people actually attending. Needs the docs/08 access-log
review designed around it FIRST ·
`x` Schedule - no endpoint exists for editing `ScheduleTemplate`; a nav item
onto nothing is worse than none ·
`x` Settings - nothing a facility may safely change about itself. Coverage and
credentials are exactly what rules 5 and 6 keep out of their hands

**Admin (10) - 9 addressed**

`+` Dashboard (Overview) · `+` Facilities (verification queue) ·
`+` Providers (verification) · `+` AI monitoring · `+` Analytics ·
`~` Appointments, `~` Queues, `~` Insurance - Django admin already registers
every model with its own audit trail; the sidebar links across rather than
rebuilding forty change forms and an audit gap ·
`x` Patients - the backend serves a patient COUNT and there is no endpoint to
build a list from. A test pins the payload shape so widening it is deliberate ·
`x` Settings - the settings that matter (the clinical gate, SMS credentials,
aggregator allow-lists) are environment variables on purpose. A web form
editing them would be a way to open the triage gate by mis-click

**Genuinely outstanding: About and Help.** Two static content pages. They need
copy in three languages that nobody has written, and inventing it would be
worse than the gap.

## 7. Rules that survive the redesign

Non-negotiable, and they predate the brief. A redesign must not quietly drop
them for visual convenience.

1. **Never invent a wait time.** Four `wait.status` values, enforced as an enum
   in the OpenAPI schema so a client that forgets one fails to compile. A
   fabricated number destroys trust permanently.
2. **Reception check-in stays under 10 seconds and keyboard-first.** The
   competitor is a paper register. Any redesign that adds a click is a
   regression.
3. **Every patient-facing feature must still fit USSD in three steps**, or
   rural users lose it. A richer web UI must not become the only way in.
4. **Phone number is identity.** Not email.
5. **The Care Guide never diagnoses**, and stays gated until a clinician signs
   off a protocol.
6. **Insurance copy says "Accepts Mutuelle", never "You are covered."** We hold
   facility-declared acceptance, not eligibility.
7. **Facility scoping is enforced centrally**, and the leak test runs against
   every staff endpoint.

## 8. Progress log

| Date | Change |
|---|---|
| 2026-08-20 | Audit complete. Five data gaps identified. Roadmap written. |
| 2026-08-20 | R0: design preset, base layer, 14 UI primitives, WaitLine + FacilityCard + Home rebuilt. Patient bundle 80 KB gz (budget 150). 21 patient + 4 provider tests green. |
| 2026-08-20 | R1 done: `providers` app, specialty-to-service mapping, 4 endpoints, `nearby?specialty=`, provider on templates and appointments. 414 backend tests, 92% coverage, 31 API operations. Journey verified live: specialty -> 3 facilities -> doctor. |
| 2026-08-20 | R2 part 1: `/search` global endpoint (14 tests), Find Care with synchronised list and map, MapLibre lazy-loaded and excluded from precache (1329 KB -> 283 KB). Fixed duplicate facilities, missing markers, and an order-dependent test suite. 444 backend tests, 92% coverage. |
| 2026-08-20 | R2 done: homepage discovery sections, search-as-you-type combobox with keyboard navigation, DoctorCard, compare, old list route retired. Care Guide entry points correctly hidden while the clinical gate is shut. 6 of 51 screens done. Patient bundle 88 KB gz. |
| 2026-08-20 | R3 part 1: per-service wait status, FacilityServiceInsurer (gap 3 closed), facility profile with five tabs. 13 new tests. 457 backend tests, 92% coverage. Insurance verified live: green only where confirmed, grey (?) everywhere else. |
| 2026-08-21 | R3 done: doctors directory with language filter, doctor profile, service detail, doctors in the nav. 13 of 51 screens. Patient bundle 92 KB gz. |
| 2026-08-21 | R4 part 1: provider-aware slots and booking (separate capacity pools), appointment detail endpoint, four-step booking flow, confirmation, full-screen queue tracking. Booking driven end to end in a browser. 469 backend tests, 93% coverage. |
| 2026-08-21 | R4 done: notification centre and preferences, honoured by the sender. Right to object from docs/08 s7 now implemented. 493 backend tests, 93% coverage. 18 of 51 screens. |
| 2026-08-21 | R6 done: facility workspace. Sidebar shell, appointments, doctors, services, reports; Reception rebuilt on the design tokens. Found and fixed a live regression - the provider app's `card` / `field` / `btn-primary` classes had been dropped when `index.css` became the design-system import, leaving the check-in button unstyled. Management screens shipped read-only on purpose (see R6). 497 backend tests, 39 API operations, provider bundle 74.7 KB gzipped. 22 of 51 screens. |
| 2026-08-21 | R5 done: Care Guide UI. Gate untouched and still shut - verified against the real 503 (no entry points, honest explanation) and with intercepted responses to drive the flow. Result routes service -> filtered search -> booking. Disclaimer on every step in rw/en/fr. 248 i18n keys per language, parity enforced by test. Patient bundle 100.5 KB gzipped (150 KB budget). 26 of 51 screens. |
| 2026-08-21 | R7 done: admin portal. Third Vite app (`web-admin`, :5175), superuser-only, backed by a new `platform_admin` Django app. Overview, verification queue, Care Guide monitoring. No patient records reachable - the backend serves a count and a test pins the payload shape. Verification requires a note. Found and fixed: the sidebar username was blank because SimpleJWT issues `user_id`, not `username`. 521 backend tests, 44 API operations, admin bundle 71.4 KB gzipped. 29 of 51 screens. |
| 2026-08-21 | R8 done: cross-cutting pass. Found three live styling regressions (patient SignIn/Profile/Visits + six components still on the dead pre-R0 classes; `.ml-card` padding) and two behavioural bugs (Profile saved on blur with failures invisible; specialty CODES shown to patients as `general-medicine`). Specialty API now returns code + three names. Measured: focus visible 12/12 tab stops, no overflow at 390/820/1440 px across eight routes, no unlabelled controls. 521 backend tests, 21 frontend tests, 257 i18n keys per language. Bundles: patient 101.2 KB, provider 74.6 KB, admin 71.4 KB gzipped. |
| 2026-08-21 | R0 closed out: component gallery at `/_gallery`, lazy-loaded and out of the precache. It immediately found two primitive bugs (Spinner collapsed to a 2px sliver outside a flex container; Button's secondary default undocumented). Contrast measured for the first time and three tokens failed - `unknown` at 2.84 on the honesty label mattered most. Palette retuned; every text/background pair across eight routes now meets WCAG AA. Speculative components (ServiceCard, Timeline, Dialog, Sheet) deliberately not built - nothing imports them. All of R0-R8 complete. |
| 2026-08-21 | **Consolidated three frontends into one.** `web-patient`, `web-provider` and `web-admin` are now `web/`, serving `/` (patients), `/workspace` (facility staff) and `/platform` (MediLink admins). One build, one origin to host, one design system copy instead of three. Sign-in is username-and-password for every user type, backed by the new `/auth/login`; the router sends people to their surface based on `session.kind`. Navbar moved to the top on every surface; the bottom nav survives for patients on small screens, because a thumb reaches the bottom of a phone and not the top. The staff surfaces are lazily loaded and left out of the service-worker precache - a patient must not download a reception desk. Patient bundle 104.9 KB gzipped; workspace 6.9 KB and platform 3.6 KB load on demand. Keyboard-first check-in re-verified after the move: focus on arrival, 2.6 s round trip, focus returns, survives navigating away and back. |
| 2026-08-21 | **Fixed a dead end found by running the whole system.** The district picker - the fallback for every patient whose browser will not give a location - rendered buttons with no click handler. They looked interactive and did nothing, making the component built to prevent a dead end into one. `/facilities/nearby` now accepts `district` as an alternative origin to `lat`/`lng`, returning that district's facilities with `distance_m: null` - null rather than zero or a centroid guess, because a number on screen is a number somebody acts on. Also removed a "Closed · Closed" stutter on every shut facility's card. 557 backend tests. |
| 2026-08-21 | **Design pass, and the roadmap checklists reconciled with reality.** At 1440px the product was a phone layout stretched into a wide window - one narrow column, no hero, no icons, headings set as form-field captions. Added a hero, a three-step elevation scale, a 20-glyph inline icon set, responsive grids, and shared `StatCard`/`BarRow`. Fixed: the bottom nav rendered on desktop; half the Reports stats had icons and half did not. |
| 2026-08-21 | **Production readiness.** Consent captured with a timestamp AND notice version; `/privacy` written from what the code does, marked as un-reviewed because it is. PII redaction on the log HANDLER, asserted by test - there was no LOGGING config at all before. `manage.py readiness` gates a deploy on the settings-level docs/08 items, and immediately found that dev settings had been silently dropping the redaction filter. Django 5.0 (EOL, 9 CVEs) -> 5.2 LTS; React Router 6 -> 7; `npm audit` now 0. Assessment written up in docs/12. |
| 2026-08-22 | **Mobile and navigation pass.** Most people reach MediLink on a phone, and the phone experience was the weakest part. Bottom nav rebuilt: five text labels in a 45px strip became icons + short labels at 57px with a safe-area inset and a tinted active plate. Top nav gained the same glyphs so the two feel like one system; the language toggle collapses to a single cycling control below `sm`, where three buttons took a third of a 360px bar. Fixed: `/doctors` overflowed horizontally at 360px (grid items default to `min-width: auto` and refused to shrink to their track); the insurer selector's empty option was labelled "change" but actually CLEARED the insurer; the MediLink home link was a 68x16 target on every screen. Home shows 3 nearby facilities on a phone and 6 once the grid has columns - a 4024px scroll became 3481px. |
| 2026-08-21 | Final end-to-end pass across all three surfaces. Found four patient screens with NO `h1` at all - the signed-out branches of Visits, Profile, Queue and Notifications returned a prompt and a button, and AppointmentDetail and the signed-in Queue never had one either. A page with no h1 gives a screen-reader user nothing to jump to and no statement of where they are. All ten patient routes now carry one. Verified: 10 patient routes, 5 provider screens, 3 admin screens all render with no page errors. |
