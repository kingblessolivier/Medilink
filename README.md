# MediLink Rwanda

A multi-channel platform that makes healthcare access predictable: find a nearby
facility, confirm it accepts your insurance, book a slot, and track the queue
remotely so you leave home at the right time.

**Sector:** Health · **Country:** Rwanda · **Status:** Phase 0 (in development)

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

**Phase 0 (Facility Directory) is implemented and running.** Phases 1-4 are
specified in the docs but not yet built.

| Component | State |
|---|---|
| `facilities` + `insurance` apps, migrations, Django admin | Done |
| `GET /facilities/nearby`, `/facilities/{slug}`, `/insurers`, `/service-types`, `/districts` | Done |
| Patient PWA: home (state A), search, facility detail, rw/en/fr | Done |
| Backend test suite | 24 tests, all passing |
| Frontend bundle | 71 KB gzipped (budget 150 KB) |
| Facility data | 25 seed facilities, **coordinates approximate - not field verified** |

The last row is the gate on Phase 0. See
[backend/fixtures/README.md](backend/fixtures/README.md) for the verification
procedure.

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
# 3. Patient app
cd web-patient && npm install && npm run dev           # http://localhost:5173
```

Verify the whole stack in one command:

```bash
curl "http://localhost:8000/api/v1/facilities/nearby?lat=-1.9536&lng=30.0606&insurer=mutuelle"
```

It must return Kigali facilities with sane `distance_m` values. If distances
look wrong, stop and fix the coordinate order before writing anything else -
`Point()` takes longitude first, and the bug is silent.

Useful URLs: `/admin/` (facility verification), `/api/docs/` (Swagger UI).

## Repository layout

```
medilink/
├── backend/                    # Django project
│   ├── config/                 # settings, urls, celery app
│   └── apps/
│       ├── facilities/         # directory, geo search, verification
│       ├── insurance/          # insurers, facility acceptance
│       ├── scheduling/         # slot templates, appointments
│       ├── queueing/           # check-in, live position, ETA
│       ├── patients/           # phone-based identity
│       ├── gateway/            # USSD + WhatsApp webhooks
│       ├── notifications/      # SMS, web push, Celery tasks
│       └── triage/             # Phase 4, rule-based symptom router
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
