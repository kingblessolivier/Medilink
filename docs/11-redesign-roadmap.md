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

### R0 - Design system foundations `IN PROGRESS`

- [x] `design/tailwind-preset.js` - colour, type, radius, shadow, spacing
- [x] `design/base.css` - base layer, component classes, reduced-motion
- [x] Wired into both apps via Tailwind `presets` + `postcss-import`
- [x] Primitives in `web-patient/src/ui`: Button, Spinner, Field, TextInput,
      Select, Chip, Card, Skeleton, CardSkeleton, ListSkeleton, EmptyState,
      ErrorState, Notice, Tabs
- [x] `WaitLine` rebuilt on the `unknown` palette - the honesty rule made visual
- [x] `FacilityCard` rebuilt: distance, open state, insurance, wait, actions
- [x] Home rebuilt on the system, with the B/C/A state ordering explicit
- [ ] Copy `src/ui` into web-provider (currently patient-only)
- [ ] Remaining healthcare components: DoctorCard, ServiceCard, InsuranceBadge,
      AvailabilityPicker, MapMarker, Timeline
- [ ] Dialog / Sheet primitives
- [ ] Component gallery route for visual regression by eye

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

- [ ] Landing, symptom entry, dynamic follow-ups, staged progress, result
- [ ] Urgency/red-flag presentation with immediate escalation
- [ ] Result → specialty → doctors → facilities → insurance → booking
- [ ] **Entry points hidden entirely when `/triage/status` reports unavailable**
- [ ] Disclaimer on every step, in all three languages

### R6 - Facility workspace

- [ ] Sidebar shell, distinct from the patient surface
- [ ] Dashboard with operational metrics
- [ ] Appointments, queue (keep the keyboard-first check-in - it is measured
      and it works), patients
- [ ] Doctor / service / insurance / schedule management
- [ ] Reports: appointments, no-shows, median wait, service demand

### R7 - Admin portal

- [ ] Shell, dashboard, facility verification queue
- [ ] Patients, providers, appointments, queues, insurance
- [ ] AI monitoring, reading `TriageOutcome` aggregates only - never answers
- [ ] Platform analytics and settings

### R8 - Cross-cutting

- [ ] Every screen: loading skeletons, empty states, error states
- [ ] AI processing shows real stages, never "Loading..."
- [ ] Responsive: desktop, tablet, mobile - re-laid out, not shrunk
- [ ] Mobile bottom nav: Home / Find Care / Care Guide / Appointments / Profile
- [ ] Accessibility pass: contrast, focus, keyboard, screen-reader, touch
- [ ] rw/en/fr for every new string, key parity enforced in CI
- [ ] Bundle budget: patient app stays under 150 KB gzipped

## 6. Screen inventory

51 screens. `—` not started, `~` in progress, `✓` done.

**Public (23):** ✓ Homepage · ✓ Find Care · ✓ Map discovery · ✓ Search results ·
✓ Facility profile · ✓ Facility overview · ✓ Facility doctors · ✓ Doctor
profile · ✓ Facility services · ✓ Service detail · ✓ Facility insurance ·
— Global insurance · — Booking · — Confirmation · — Queue tracking · — Care
Guide landing · — Symptom assessment · — AI processing · — AI result · — AI
recommended facilities · ✓ Compare · — About · — Help

**Patient (8):** — Dashboard · — Appointments · — Appointment detail · — Active
queue · — Notifications · — Profile · — Insurance · — Settings

**Facility (10):** — Dashboard · — Appointments · — Queue · — Patients ·
— Doctors · — Services · — Insurance · — Schedule · — Reports · — Settings

**Admin (10):** — Dashboard · — Facilities · — Patients · — Providers ·
— Appointments · — Queues · — Insurance · — AI monitoring · — Analytics ·
— Settings

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
