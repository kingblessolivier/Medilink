# 09 - Roadmap and Milestones

## 1. The principle behind this ordering

The pitch describes a patient app. Building the patient app first produces a
polished product with **no data in it**, because live queue positions only exist
once a receptionist is entering patients into our system.

So the build order is:

```
Phase 0  Directory        - needs no hospital partnership at all
Phase 1  Provider tool    - creates the data
Phase 2  Patient app      - reads the data
Phase 3  USSD / WhatsApp  - widens reach
Phase 4  Triage           - last, and only if the gates in doc 08 are met
```

Each phase must be **independently useful**. If funding or the team stops after
any phase, what exists must still help somebody.

## 2. Phase 0 - Facility Directory (4-6 weeks)

**Goal:** answer "which facilities are near me, open now, and accept my
insurance?" with no hospital integration whatsoever.

This phase is what gets you in the door with hospitals. Walking into a health
centre with a working directory that already lists them is a completely different
conversation from walking in with slides.

### Scope

| Item | Detail |
|---|---|
| Backend | `facilities`, `insurance` apps; `/facilities/nearby`, `/facilities/{slug}` |
| Data | 50+ field-verified Kigali facilities with real coordinates |
| Admin | Django admin configured for facility verification |
| Frontend | Patient PWA: home (state A), search, facility detail |
| Languages | Kinyarwanda, English, French |
| Out of scope | Accounts, booking, queue, USSD, maps |

### Non-obvious critical path

**Facility data collection is field work, and it is the longest task in this
phase.** Visiting facilities, recording GPS coordinates, confirming opening hours
and insurance acceptance takes weeks of walking. Start it in **week 1**, in
parallel with development, using a paper or spreadsheet template.

Also start in week 1, because they take months: **USSD shortcode application**,
**business registration**, and **NCSA data controller registration**.

### Definition of done

- [ ] 50+ facilities loaded, each with a coordinate verified on-site
- [x] Nearby search returns correct distances (asserted against known pairs)
- [x] `EXPLAIN ANALYZE` shows an Index Scan, not a Seq Scan - fixed
      2026-08-23; it was a Seq Scan until then. See docs/04.
- [ ] Insurance filter works for Mutuelle, RSSB and MMI
- [ ] Opening hours correct, including lunch breaks
- [x] All four `wait.status` values render (all will be `not_reported` here)
- [ ] Works offline with cached results
- [ ] Loads in under 3 s on a real 3G connection on a real low-end Android phone
- [ ] Ten real patients have used it and been interviewed

That final item is the real gate. Not "it works", but "ten strangers used it and
told us what was wrong".

## 3. Phase 1 - Provider tool and one pilot facility (6-10 weeks)

**Goal:** one real facility runs reception check-in through MediLink for a full
working week.

### Choosing the pilot - do not pick CHUK

A referral hospital has committees, procurement processes, and no appetite for
risk from a student team. Pick:

- a **district health centre** or a **private polyclinic**,
- with a **named champion** - one person who wants this to work,
- with 50-200 patients a day (enough data, small enough to recover from mistakes),
- and reachable in under 30 minutes, because you will visit constantly.

### Scope

| Item | Detail |
|---|---|
| Backend | `queueing`, `patients`; check-in, call, serve, board, sync |
| Frontend | Provider reception screen, offline-capable |
| Ops | Staff accounts, facility profile management |
| Data | `ServiceTimeStat` accumulation begins |
| Out of scope | Patient-side queue view (nothing to show until data exists) |

### The week before go-live

1. **Sit at the reception desk for a full day and observe.** Count patients, time
   the paper process, note every interruption. Your design assumptions will be
   wrong; find out now.
2. **Record the baseline.** Arrival time and consultation start time for every
   patient, for at least three days. Without this number you can never prove the
   50% improvement, and funders will ask for it.
3. **Train the receptionists in person**, and leave a one-page guide in
   Kinyarwanda taped to the desk.
4. **Be physically present for the first three days.** Not on a phone - in the room.

### Definition of done

- [ ] Median check-in time under 10 seconds, measured with a stopwatch
- [ ] Five consecutive working days with no reversion to paper
- [ ] Full offline operation verified by unplugging the network mid-shift
- [ ] `ServiceTimeStat` has 20+ samples per service and hour
- [ ] Receptionists say it is faster than paper - in their words, recorded
- [ ] Baseline wait times documented

**Do not proceed to Phase 2 until the reception tool survives a week unaided.**
The patient app is worthless on top of an abandoned provider tool.

## 4. Phase 2 - Patient app (6-8 weeks)

**Goal:** deliver the sentence the whole product exists for - *"You are number 8.
Leave home by 10:15."*

### Scope

| Item | Detail |
|---|---|
| Auth | Phone + OTP |
| Booking | Slot templates, `/appointments`, cancellation |
| Queue | Patient live view, ETA, `leave_by` |
| Notifications | SMS: leave now, called, appointment reminders |
| Frontend | Home states B and C, queue screen, visits, profile |
| Optional | Map view behind a "Show map" toggle |

### The hardest problems in this phase

**ETA accuracy.** The first estimates will be wrong. Ship conservatively - round
the buffer up and the estimate down - and use `eta_confidence` to widen the
language rather than pretending to precision. "Roughly 30-50 min" is honest;
"38 minutes" is not.

**No-shows for booked slots.** A booking that nobody honours is worse than no
booking, because it teaches patients not to trust the system. Send a reminder at
24 h and 2 h, and make cancellation one tap.

**Walk-ins versus appointments.** Real reception desks interleave both. Decide
the policy with the facility - typically appointments are inserted at their slot
time rather than at the end - and make it visible so nobody feels cheated.

### Definition of done

- [ ] 100+ patients have tracked a queue remotely
- [ ] ETA within +/- 15 minutes for 70% of entries
- [ ] "Leave now" SMS delivered exactly once per entry (verified in production data)
- [ ] Booked-appointment no-show rate under 20%
- [ ] Median wait at the pilot facility measurably lower than baseline
- [ ] Patient interviews: at least 10, recorded

## 5. Phase 3 - USSD and WhatsApp (4-6 weeks, gated on the shortcode)

**Goal:** the product works without a smartphone.

This phase is **blocked on the shortcode application started in Phase 0**. If it
has not arrived, build against the sandbox and ship WhatsApp first.

### Scope

Full menu tree from [06-channels-ussd-whatsapp.md](06-channels-ussd-whatsapp.md):
nearby, book, my queue, insurance, language - plus WhatsApp interactive lists and
approved template messages.

### Definition of done

- [ ] Every USSD screen under 160 GSM-7 characters, in all three languages
- [ ] "My queue" reachable in one step
- [ ] Any feature reachable in three steps or fewer
- [ ] Backend failure returns a friendly `END`, never a blank screen
- [ ] Tested on a real feature phone with a real SIM on both MTN and Airtel
- [ ] WhatsApp templates approved by Meta
- [ ] 50+ sessions from real users outside the team

## 6. Phase 4 - Triage (only if the gates are met)

**Goal:** reduce unnecessary referrals to major hospitals.

**Status: the engineering is done and the feature is switched off.**

The engine, protocol schema, validator and API all exist. Every endpoint returns
503 because `apps/triage/gate.py` requires a recorded clinician sign-off, and
none exists. That is the intended state, not an unfinished one.

**No clinical protocol ships with the codebase.** Routing rules are a clinical
artefact; a licensed clinician authors them against the schema in
`apps/triage/protocols/README.md`, and validates with:

```bash
python manage.py check_triage_protocol <file>
```

Structural validation is not clinical review. What remains before this can be
turned on is entirely human work:

- [ ] A clinician authors a protocol from a published, citable triage protocol
- [ ] A licensed clinician reviews and signs off that specific version
- [ ] Ministry of Health and Rwanda FDA consulted on classification
- [ ] Disclaimer wording reviewed in all three languages
- [ ] The four `TRIAGE_*` settings configured with the sign-off record

If those cannot be completed, the product ships without a symptom checker and
loses nothing essential. That is the recommended outcome unless there is a
clinician actively on the team.

## 7. Scaling beyond the pilot

Each new facility is a **sales and training task**, not an engineering one.
Engineering's job is to make onboarding cheap:

- Self-service facility profile setup in the provider app
- A one-page printed guide in Kinyarwanda
- Remote staff-account creation
- A dashboard showing each facility its own median wait, week over week

That last item is how a facility decides to keep using MediLink. Build it before
you have twenty facilities, not after.

## 8. Measurement plan

The pitch commits to specific numbers. Each needs an owner and a method.

| Claim | Metric | Method | Honest caveat |
|---|---|---|---|
| 50% wait reduction | Median arrival-to-consultation minutes | Baseline before Phase 1 vs. after Phase 2, same facility, same weekdays | Confounded by staffing changes and seasonality; report the confound |
| 1.5 h saved per patient | Median time saved per visit | Derived from the above | Only counts patients who used remote tracking |
| No-show revenue recovered | No-show rate before vs. after | Facility records | Requires the facility to share revenue data |
| 30% more flow to local facilities | Share of visits by facility level | Our own booking data | We only see MediLink users, not total system flow - **do not claim system-wide effect from our own data alone** |

Be rigorous here. A carefully measured 22% improvement is far more credible to a
funder or a ministry than an unsourced 50%.

## 9. Timeline summary

| Phase | Duration | Cumulative | Gate to proceed |
|---|---|---|---|
| 0 - Directory | 4-6 weeks | ~6 weeks | 50 verified facilities, 10 patient interviews |
| 1 - Provider tool | 6-10 weeks | ~16 weeks | 5 unaided days at the pilot |
| 2 - Patient app | 6-8 weeks | ~24 weeks | 100 tracked queues, measured wait reduction |
| 3 - Channels | 4-6 weeks | ~30 weeks | Shortcode live, real-device testing passed |
| 4 - Triage | 6+ weeks | ~36 weeks | All compliance gates met |

Roughly **seven to nine months** to the full scope with a small team - assuming
the shortcode and registrations, started in week 1, arrive on time.

## 10. The three risks that decide whether this works

**Hospital adoption is the whole game.** The competitor is a paper register and an
overwhelmed receptionist. If check-in is slower than writing a name on paper,
nothing else in this document matters.

**The symptom checker is regulated territory.** Treat it as optional scope with
hard gates, never as a headline feature.

**Data protection is an architectural constraint, not a launch task.** Hosting
location, data minimisation and facility scoping must be decided before code is
written; retrofitting them means migrating production health data.
