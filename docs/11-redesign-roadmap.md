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

### R1 - Providers and specialties (backend)

Unblocks 8+ screens. Nothing in R3 or R5 can start without it.

- [ ] `providers` app: `Specialty`, `Provider`, `ProviderSpecialty`,
      `ProviderService`, `ProviderAvailability`
- [ ] `Specialty` ↔ `ServiceType` mapping, so a recommendation reaches search
- [ ] Optional `Provider` ↔ `StaffMember` link (a doctor may have no login)
- [ ] Endpoints: `/providers`, `/providers/{slug}`,
      `/facilities/{slug}/providers`, `/specialties`
- [ ] Extend `/facilities/nearby` with a `specialty` filter
- [ ] Appointment gains an optional `provider` - "any available" stays default
- [ ] Admin, fixtures, tests

### R2 - Discovery: home, find care, map

The brief's highest priority, and the strongest screen in the product.

- [ ] Homepage: hero, universal search, location, nearby map, nearby
      facilities, doctors near you, popular services, insurance, Care Guide
- [ ] Find Care: 40/60 split, filter rail, synchronised list ↔ map
- [ ] MapLibre integration, lazy-loaded, list-first fallback
- [ ] Location: auto, manual district, map-area selection; **never blocks**
- [ ] Global search: facilities, doctors, services, grouped results
- [ ] Compare facilities (max 3, simple table, not a spreadsheet)

### R3 - Facility profile

- [ ] Header: name, type, verified, open state, distance, book, directions
- [ ] Tabs: Overview / Doctors / Services / Insurance / Appointments / Queue
- [ ] Per-service live status, honouring the four wait states
- [ ] Doctor list and profile
- [ ] Service detail
- [ ] Insurance tab with explicit `unknown` coverage

### R4 - Booking and queue

Mostly a redesign - the backend is complete.

- [ ] Booking: service → doctor → date → time → insurance → review → confirm
- [ ] Confirmation screen with reference and calendar handoff
- [ ] Queue tracking, full-screen, with `leave_by` as the hero
- [ ] Notification centre and preferences
- [ ] Patient dashboard: greeting, next appointment, active queue, actions

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

**Public (23):** — Homepage · — Find Care · — Map discovery · — Search results ·
— Facility profile · — Facility overview · — Facility doctors · — Doctor
profile · — Facility services · — Service detail · — Facility insurance ·
— Global insurance · — Booking · — Confirmation · — Queue tracking · — Care
Guide landing · — Symptom assessment · — AI processing · — AI result · — AI
recommended facilities · — Compare · — About · — Help

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
| 2026-08-20 | R0 part 1: design preset, base layer, 14 UI primitives, WaitLine + FacilityCard + Home rebuilt. Patient bundle 80 KB gz (budget 150). 21 patient + 4 provider tests green. |
