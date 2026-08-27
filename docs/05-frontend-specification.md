# 05 - Frontend Specification

Two React applications, one shared API client, one shared design token set.

| App | Audience | Device | Delivery |
|---|---|---|---|
| `web-patient` | Patients | Low-end Android, 3G | Installable PWA |
| `web-provider` | Reception, facility admin | Shared clinic PC or tablet | Standard web app |

## 1. Shared foundations

```
web-*/src/
├── api/            generated types + typed fetch client
├── components/     shared UI primitives
├── hooks/
├── i18n/           rw.json · en.json · fr.json
├── lib/            formatting, dates, distance
├── routes/         one folder per screen
└── main.tsx
```

**Stack:** React 18, TypeScript, Vite, React Router, TanStack Query, Tailwind CSS.

**No component library.** MUI or Ant Design would add 300 KB+ to a bundle
downloaded over 3G, for components we will restyle anyway. Build the eight
primitives we need: `Button`, `Card`, `Badge`, `Input`, `Select`, `Sheet`,
`Spinner`, `EmptyState`.

**Types are generated, never hand-written:**

```bash
npx openapi-typescript http://localhost:8000/api/schema/ -o src/api/types.ts
```

Run it in CI. A backend field rename must break the frontend build, not the
reception desk.

## 2. Language

Kinyarwanda is the **default**, not an afterthought. English and French are
available; the toggle lives on the home screen, not buried in settings.

```
i18n/rw.json   (default, complete)
i18n/en.json
i18n/fr.json
```

Rules:

- Every string goes through `t()`. No literal user-facing text in JSX.
- Kinyarwanda words are longer than English ones. Design every button and badge
  to survive **1.4x text expansion** without breaking layout. Test in Kinyarwanda
  first; if it fits there it fits everywhere.
- Never concatenate translated fragments - use interpolation, since word order
  differs between the three languages.

## 3. Patient app - the home screen

The home screen is **state-dependent**. It answers one question: *where do I go,
and when should I leave?*

On load it calls `GET /queue/current`, which decides the state.

### State A - nothing active

```
+------------------------------------+
| Muraho, Jean          [RW]    (!)  |
| Gasabo, Kigali             change  |
+------------------------------------+
|                                    |
|   +------------------------------+ |
|   |   Find care near me          | |   <- primary action
|   +------------------------------+ |
|                                    |
|   Your cover: Mutuelle de Sante    |   <- filters everything below
|                            change  |
+------------------------------------+
|  Nearby and open now               |
|                                    |
|  +--------------------------------+|
|  | Kimironko Health Centre        ||
|  | 1.2 km - Open until 17:00      ||
|  | Accepts Mutuelle               ||
|  | Wait: about 40 min             ||
|  |                    [ Book ]    ||
|  +--------------------------------+|
|  +--------------------------------+|
|  | Remera Polyclinic              ||
|  | 2.8 km - Open until 20:00      ||
|  | Accepts Mutuelle               ||
|  | Wait not available             ||
|  +--------------------------------+|
|              See all >             |
+------------------------------------+
|  Home   Facilities  Visits  Profile|
+------------------------------------+
```

### State B - patient is in a queue (the product)

When a queue entry is active, the live card **replaces** the search hero.
Nothing may compete with it.

```
+------------------------------------+
| Kimironko Health Centre            |
+------------------------------------+
|  +--------------------------------+|
|  |                                ||
|  |    You are number              ||
|  |         8                      ||   <- huge; readable at arm's length
|  |                                ||
|  |    [########........]          ||
|  |                                ||
|  |    About 35 min to your turn   ||
|  |                                ||
|  |    Leave home by 10:15         ||   <- the actually useful line
|  |                                ||
|  |    Updated 2 min ago           ||   <- never hide staleness
|  |                                ||
|  |  [ Directions ]    [ Cancel ]  ||
|  +--------------------------------+|
+------------------------------------+
```

`Leave home by` = `now + eta_minutes - travel_minutes - buffer`, where buffer is
10 minutes. **Be conservative** - telling a patient to leave too late is far
worse than too early, so round the buffer up and the ETA down.

When `leave_by` is null (no patient location), hide that line entirely rather
than showing a placeholder.

### State C - appointment booked for today

Same card shape:

```
|   Today at 14:00                   |
|   Kimironko Health Centre          |
|   Consultation generale            |
|   Reference: ML7K2Q                |
|   [ Directions ]     [ Cancel ]    |
```

### Why each element earns its place

| Element | Justification |
|---|---|
| Location + change | Every result is distance-ranked; a wrong GPS fix must be correctable |
| Insurance chip | The core promise of the product. Set once, filters every list. Visible, not hidden in settings |
| Wait per card | The reason someone opens the app |
| Open until HH:MM | Prevents the most common wasted trip |
| "Updated 2 min ago" | Trust. A stale number that looks live destroys credibility permanently |
| Language toggle | Kinyarwanda-first users must not hunt for it |

### What must NOT be on the home screen

- **The symptom checker as a primary button.** Put it inside the search flow
  ("Not sure which doctor? >"). Prominence invites self-diagnosis instead of
  care-seeking - a clinical risk and a liability.
- **News, tips, promotions.** Nobody opens this app to browse.
- **A login wall.** Search and wait times work anonymously. Ask for the phone
  number only at the moment of booking.
- **Invented precision.** "43 minutes" implies accuracy we do not have.

## 4. Patient app - screen inventory

| Route | Screen | Phase |
|---|---|---|
| `/` | Home (states A/B/C) | 0 |
| `/search` | Filters: service, insurer, open now, radius | 0 |
| `/facility/:slug` | Detail: hours, services, insurers, wait, map link | 0 |
| `/facility/:slug/book` | Slot picker | 2 |
| `/queue/:id` | Full-screen live queue view | 2 |
| `/visits` | Past and upcoming | 2 |
| `/profile` | Name, language, insurer, home location | 2 |
| `/auth` | Phone -> OTP | 2 |
| `/triage` | Symptom router | 4 |
| `/offline` | Cached-content fallback | 1 |

## 5. PWA requirements

```json
// web-patient/public/manifest.json
{
  "name": "MediLink Rwanda",
  "short_name": "MediLink",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#0f766e",
  "lang": "rw",
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" },
    { "src": "/icon-maskable.png", "sizes": "512x512", "purpose": "maskable" }
  ]
}
```

Service worker caching strategy (Workbox via `vite-plugin-pwa`):

| Resource | Strategy | Reason |
|---|---|---|
| App shell (JS/CSS/HTML) | Precache, cache-first | Instant repeat loads |
| `/facilities/nearby` | Network-first, 24 h fallback | Fresh when online, usable when not |
| `/facilities/:slug` | Stale-while-revalidate | Detail rarely changes |
| `/queue/entries/:id` | **Network-only** | Never serve a stale queue position |
| `/insurers`, `/service-types` | Cache-first, 7 days | Change twice a year |

That `network-only` rule is important: a cached queue position is actively
harmful - it would tell a patient to stay home when they are being called.

### Performance budget

| Metric | Budget |
|---|---|
| Initial JS, gzipped | < 150 KB |
| First Contentful Paint on 3G | < 2.5 s |
| Time to Interactive on 3G | < 4 s |
| Lighthouse Performance | > 85 |

The initial-JS budget is enforced in CI by the `Bundle size budget` step in
`.github/workflows/ci.yml`: it gzips `dist/assets/index-*.js` after the build
and exits non-zero above 150 KB. No bundle-analysis plugin is installed - a
gzipped byte count is the thing the budget is actually about, and it needs no
dependency to measure. The other three rows are targets, not gates; nothing
checks them automatically.

## 6. Provider app - the reception screen

This screen decides whether MediLink succeeds. Our competitor is a paper register
and an overwhelmed receptionist. **If check-in is slower than writing a name on
paper, we have lost.**

**Target: under 10 seconds per patient, under 4 keystrokes.**

```
+---------------------------------------------------------------+
| Kimironko Health Centre        Mon 18 Aug 10:12    [Online]   |
+---------------------------------------------------------------+
|  CHECK IN                                                     |
|  Phone or appointment code                                    |
|  [ 078...                          ]  [ Check in ]  (Enter)   |
|  ( ) Walk-in, no phone                                        |
+---------------------------------------------------------------+
|  WAITING - General consultation (14)                          |
|                                                               |
|  A-042  Uwase Alice     078...456   09:40   [Call] [Serve]    |
|  A-043  Mugisha Jean    078...112   09:47   [Call] [Serve]    |
|  A-044  (walk-in) Keza  -           09:52   [Call] [Serve]    |
|                                                               |
|  CALLED (2)                                                   |
|  A-040  Niyonsaba P.    078...889   10:05   [Serve] [No show] |
+---------------------------------------------------------------+
```

Requirements:

- **Keyboard-first.** Focus starts in the phone field. Enter checks in. The
  receptionist should never need the mouse for the common path.
- **Optimistic UI.** The row appears immediately; reconcile when the server
  responds. Never make a receptionist wait for a round trip.
- **Offline banner** switches `[Online]` to `[Offline - 4 pending]` and keeps
  every action working against IndexedDB.
- **Large touch targets** (minimum 44 px) - this may run on a tablet.
- **No confirmation dialogs** on check-in. Provide undo instead.

### Offline queue implementation

```ts
// web-provider/src/lib/offlineQueue.ts
type PendingAction = {
  key: string                  // uuid, doubles as Idempotency-Key
  type: "check_in" | "call" | "serve" | "skip"
  clientRecordedAt: string     // ISO - the server orders by this
  payload: unknown
}

// 1. Write to IndexedDB first
// 2. Optimistically update the TanStack Query cache
// 3. Attempt POST; on failure leave it pending
// 4. On 'online' event, POST /queue/sync with all pending actions
// 5. Clear each action only after a per-item success in the response
```

`clientRecordedAt` is what preserves fairness: a receptionist offline for ten
minutes must not push their patients behind everyone checked in since.

## 7. Provider app - remaining screens

| Route | Screen | Phase |
|---|---|---|
| `/` | Reception / queue board | 1 |
| `/schedule` | Slot templates per service and weekday | 2 |
| `/appointments` | Day view, mark arrived / no-show | 2 |
| `/facility` | Profile: hours, services, insurers accepted | 1 |
| `/staff` | Manage staff accounts (admin role only) | 1 |
| `/reports` | Daily volume, median wait, no-show rate | 3 |

The `/reports` screen is how a facility justifies keeping MediLink. Show them the
number that matters: median wait this week versus the week before.

## 8. Accessibility

Not optional - a large share of users are elderly patients.

- Minimum body text 16 px; the queue number at 64 px or larger.
- Contrast ratio 4.5:1 minimum; verify in bright outdoor daylight, which is the
  real usage condition.
- Every interactive element reachable by keyboard, with a visible focus ring.
- Icons always accompanied by text labels, never alone.
- `aria-live="polite"` on the queue position so screen readers announce changes.
- Never encode meaning in colour alone - "open" needs a word, not just green.

## 9. Design tokens

```css
:root {
  --color-primary:  #0f766e;   /* teal-700  - actions */
  --color-success:  #15803d;   /* green-700 - open, accepted */
  --color-warning:  #b45309;   /* amber-700 - closing soon */
  --color-danger:   #b91c1c;   /* red-700   - emergency, cancel */
  --color-muted:    #6b7280;   /* grey-500  - unavailable, stale */

  --text-base: 1rem;
  --text-queue-number: 4rem;

  --radius: 0.75rem;
  --touch-min: 44px;
}
```

`--color-muted` is the colour of "Wait not available". Unknown data must look
visually quieter than known data, so a patient can tell the difference at a
glance without reading.

## 10. Frontend definition of done

- [x] Every user-facing string in all three language files
- [x] Layout survives Kinyarwanda text at 1.4x English length - checked at
      360/390/768/1440 px across five screens in `rw`: no page overflow and no
      text escaping its box.
- [x] All four `wait.status` values have a distinct, tested rendering
- [x] Home screen renders correctly in states A, B and C
- [x] Geolocation denied path reaches the district picker
- [~] Bundle within the performance budget on a 3G throttle. Splitting the
      fourteen secondary patient routes out of the cold load took the main
      bundle from 384 KB to 329 KB (117 -> 106 KB gzipped) and first heading
      from **11.6 s to 2.4-3.0 s** on 3G with a 4x CPU throttle. Left
      unticked deliberately: the figure varies to 10 s on a genuinely cold
      start, and docs/09 asks for a REAL low-end phone, which this is not.
- [x] Reception check-in completes in under 10 s with keyboard only
- [x] Reception works fully with the network disabled, and syncs on reconnect
- [ ] Tested on a real low-end Android device, not only the emulator
