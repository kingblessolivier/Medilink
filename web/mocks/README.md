# Mock API

A dependency-free stand-in for the Django backend, so the patient app can be
run and inspected without Postgres, PostGIS or Redis.

```bash
npm run mock:api        # serves http://localhost:8000
npm run dev             # vite proxies /api -> localhost:8000
```

## Why this exists

The full stack needs Docker, PostGIS and a working GeoDjango install. That is
the right environment for backend work and an unreasonable prerequisite for
changing a card component. It also makes some frontend states difficult to
reach on demand — in particular the four wait states, which need a facility
with enough queue samples, one with too few, one that runs no reception tool,
and one that is closed.

This server returns all four every time, plus a verified and an unverified
clinician, a facility that is closing soon, and one that cannot be booked.
Those are the states that are easy to get wrong and hard to produce by hand.

## Keeping it honest

Response shapes are taken from `backend/schema.yaml`. **A mock that drifts from
the contract is worse than no mock**, because it lets a component ship against
a shape the server never sends.

If a serializer changes, update this file in the same pull request. The
generated client (`src/api/schema.d.ts`) is the reference for what the fields
are actually called.

## What it does not do

No authentication, no writes, no persistence. Every `POST` returns 401, which
is enough to exercise the signed-out gates and nothing more. Anything touching
booking, check-in or the queue needs the real backend.
