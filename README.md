# MediLink Rwanda

A multi-channel platform that makes healthcare access predictable: find a nearby
facility, confirm it accepts your insurance, book a slot, and track the queue
remotely so you leave home at the right time.

**Sector:** Health · **Country:** Rwanda · **Status:** Phases 0-2 built, Phase 3 next

---

## The core promise

> **"You are number 8. Leave home by 10:15."**

Every subsystem in this project exists to produce that one sentence, and to
deliver it to a patient on a smartphone, a feature phone, or WhatsApp.

## The problem

Patients at Rwandan health facilities wait 3-4 hours to be seen. Surveys in
Gasabo, Nyarugenge and Kicukiro found people arriving at 6 a.m. and being
attended to in the late afternoon. The gap is not that patients lack knowledge
of what they need - it is that they have **no access to three facts before
they travel**:

1. Is the service available at this facility?
2. Does this facility accept my insurance (Mutuelle, RSSB/RAMA, MMI)?
3. How long will I wait?

## The architectural insight

MediLink is **two-sided**. There is no external API that publishes "you are
number 47" - that number only exists because a receptionist entered patients
into our system as they arrived.

```
  Provider side (the foundation)          Patient side (the visible part)
  ------------------------------          -------------------------------
  Reception check-in screen        --->    Live queue position
  Slot / schedule configuration    --->    Bookable appointments
  Insurance acceptance settings    --->    "They accept your Mutuelle"
```

The patient app is a **read view of provider-entered data**. Building the
patient app first produces a beautiful app with no data in it. This dictates
the build order in [docs/09-roadmap-and-milestones.md](docs/09-roadmap-and-milestones.md).

## Technology

| Layer          | Choice                                  |
| -------------- | --------------------------------------- |
| Backend        | Django 5 + Django REST Framework        |
| Database       | PostgreSQL 16 + PostGIS 3.4             |
| Cache / jobs   | Redis 7 + Celery                        |
| Provider app   | React 18 + Vite + TypeScript            |
| Patient app    | React 18 + Vite + TypeScript (PWA)      |
| Notifications  | SMS (primary) + Web Push (secondary)    |
| USSD           | Africa's Talking (or equivalent aggregator) |
| WhatsApp       | Meta WhatsApp Business Cloud API        |

## Documentation

| # | Document | What it covers |
|---|----------|----------------|
| 01 | [System Architecture](docs/01-system-architecture.md) | Components, boundaries, request flows, deployment |
| 02 | [Data Model](docs/02-data-model.md) | Entities, schema, Django models, indexes |
| 03 | [API Specification](docs/03-api-specification.md) | Every endpoint, request/response, errors |
| 04 | [Nearby Facilities](docs/04-nearby-facilities.md) | **The geo-search feature, end to end** |
| 05 | [Frontend Specification](docs/05-frontend-specification.md) | Screens, states, components, routing |
| 06 | [USSD & WhatsApp Channels](docs/06-channels-ussd-whatsapp.md) | Session handling, menu trees, webhooks |
| 07 | [Development Setup](docs/07-development-setup.md) | Docker, Windows/WSL2, env vars, seed data |
| 08 | [Security & Compliance](docs/08-security-and-compliance.md) | Rwanda Law 058/2021, health data handling |
| 09 | [Roadmap & Milestones](docs/09-roadmap-and-milestones.md) | Phase 0-4, definitions of done |
| 10 | [Testing Strategy](docs/10-testing-strategy.md) | Unit, integration, geo, USSD, field testing |

## Status

**Phases 0, 1 and 2 are implemented and running.** Phases 3-4 are specified in
the docs but not yet built.

| Component | State |
|---|---|
| **Phase 0** `facilities` + `insurance`, geo search, Django admin verification | Done |
| **Phase 0** Patient PWA: home (state A), search, facility detail, rw/en/fr | Done |
| **Phase 1** `patients`, `staff`, `queueing`: check-in, board, transitions, offline sync | Done |
| **Phase 1** Live ETA from rolling median service statistics | Done |
| **Phase 1** Provider reception app: keyboard-first check-in, offline queue | Done |
| **Phase 2** Patient auth: phone + SMS code, tokens separate from staff identity | Done |
| **Phase 2** `scheduling`: slot templates, booking with capacity locking, cancellation | Done |
| **Phase 2** `notifications`: SMS leave-now, called, appointment reminders | Done |
| **Phase 2** `leave_by` - the sentence the product exists for | Done |
| **Phase 2** Patient app: home states B and C, booking, visits, profile | Done |
| **Phase 3** USSD and WhatsApp | Not built |
| **Phase 4** Triage | Not built, and gated on docs/08 section 8 |
| Backend test suite | 133 tests, 91% coverage |
| Bundles | patient 79 KB, provider 62 KB gzipped (budget 150 KB) |
| Facility data | 25 seed facilities, **coordinates approximate - not field verified** |

Two gates remain open and neither is code. Facility coordinates must be
captured on site before a facility is marked verified - see
[backend/fixtures/README.md](backend/fixtures/README.md). And a pilot facility
must run reception unaided for five working days, with a stopwatch baseline
recorded first, or the wait-time reduction cannot be proved. See
[docs/09](docs/09-roadmap-and-milestones.md).

### Notifications in development

`ConsoleSMSBackend` prints messages instead of sending them, so no developer
machine ever texts a real patient. Production refuses to start with it: see
`config/settings/prod.py`. Send what is due with:

```bash
python manage.py send_due_notifications      # cron every minute during the pilot
```

## Branching

`dev` is where work lands, via pull request. `main` is deployment only.

```bash
git switch dev && git pull
git switch -c feat/my-change
# ... work ...
gh pr create --base dev
```

## Quick start

Requires Docker Desktop and Node 20. **Do not install GDAL natively on
Windows** - run the backend in Docker or WSL2. See
[docs/07-development-setup.md](docs/07-development-setup.md).

```bash
# 1. Infrastructure
docker compose -f infra/docker-compose.yml up -d       # postgis :5432, redis :6380

# 2. Backend (in WSL2, or via the backend Dockerfile)
cd backend
cp .env.example .env
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py loaddata fixtures/insurers.json fixtures/service_types.json fixtures/kigali_facilities.json
python manage.py seed_demo          # development data - prints a warning, read it
python manage.py createsuperuser
python manage.py runserver
```

```bash
# 3. Frontends
cd web-patient  && npm install && npm run dev          # http://localhost:5173
cd web-provider && npm install && npm run dev          # http://localhost:5174
```

The provider app needs a staff account. Create one after `createsuperuser`:

```bash
python manage.py shell -c "
from django.contrib.auth.models import User
from apps.facilities.models import Facility
from apps.staff.models import StaffMember
u, _ = User.objects.get_or_create(username='reception')
u.set_password('choose-a-password'); u.save()
StaffMember.objects.update_or_create(
    user=u,
    defaults={'facility': Facility.objects.first(), 'role': 'receptionist'},
)"
```

Verify the whole stack in one command:

```bash
curl "http://localhost:8000/api/v1/facilities/nearby?lat=-1.9536&lng=30.0606&insurer=mutuelle"
```

It must return Kigali facilities with sane `distance_m` values. If distances
look wrong, stop and fix the coordinate order before writing anything else -
`Point()` takes longitude first, and the bug is silent.

Useful URLs: `/admin/` (facility verification), `/api/docs/` (Swagger UI).

### API contract

`backend/schema.yaml` is committed and is the single source of truth for both
frontends. Never hand-write TypeScript API types:

```bash
cd backend && python manage.py spectacular --file schema.yaml --fail-on-warn
cd ../web-patient  && npm run gen:api
cd ../web-provider && npm run gen:api
```

CI regenerates all three and fails on any diff, so a backend rename breaks the
build rather than the reception desk.

## Repository layout

```
medilink/
├── backend/                    # Django project
│   ├── config/                 # settings, urls, celery app
│   └── apps/
│       ├── facilities/         # directory, geo search, verification
│       ├── insurance/          # insurers, facility acceptance
│       ├── patients/           # phone-based identity
│       ├── staff/              # facility scoping and roles
│       ├── queueing/           # check-in, live position, ETA, offline sync
│       ├── scheduling/         # slot templates, booking, cancellation
│       ├── notifications/      # SMS dispatch, reminders, scheduled tasks
│       ├── gateway/            # Phase 3 - USSD + WhatsApp webhooks
│       └── triage/             # Phase 4 - rule-based symptom router
├── web-provider/               # React - reception desk & facility admin
├── web-patient/                # React PWA - patient-facing
├── infra/                      # docker-compose, deployment
└── docs/                       # this documentation set
```

## Non-negotiable design rules

1. **Never invent a wait time.** If a facility does not report live queue data,
   display "Wait time not available". A fabricated number destroys trust
   permanently and cannot be recovered.
2. **Every feature must fit USSD in <= 3 steps**, or rural users do not have it.
3. **Reception check-in must take under 10 seconds.** Our competitor is a paper
   register and an overwhelmed receptionist.
4. **Phone number is identity.** Not email. One patient, three channels, one row.
5. **The symptom checker never diagnoses.** It routes, and it always offers a
   red-flag escalation path.
