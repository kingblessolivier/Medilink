# 07 - Development Setup

## 1. Read this first: GeoDjango on Windows

GeoDjango requires the native **GDAL**, **GEOS** and **PROJ** libraries. Installing
these directly on Windows via OSGeo4W is a genuine time sink and a recurring
source of "works on my machine" failures across a team.

**Run the backend in Docker or WSL2 unless you have a reason not to.** Native
Windows is supported and documented in section 1a - it is a deliberate choice
with two known traps, not the default.

| Approach | Verdict |
|---|---|
| Docker Desktop + WSL2 backend | **Recommended** - identical for everyone |
| WSL2 Ubuntu, native Python | Good - `apt install gdal-bin libgdal-dev` just works |
| Native Windows + OSGeo4W | Works, and is written down below - but you own the DLL paths |

The React apps run fine natively on Windows. Only the Django backend needs Linux
libraries.

### 1a. Native Windows, if you want it

This used to say "avoid, expect to lose days". It does work, and the two things
that actually cost the time are both recorded here, so it should not cost them
again. Docker remains the recommendation because it is identical for everyone;
this is for when you want a debugger attached to Django without WSL in the way.

```powershell
py -3.12 -m venv .venv          # 3.12, not 3.14 - Django 5.2 does not support 3.14
.venv\Scripts\activate
pip install -r backend\requirements-dev.txt
```

There is **no GDAL wheel on PyPI for Windows** - `pip install GDAL` reports
`from versions: none`. OSGeo4W is the supported source. Installing only the
`gdal` package pulls GEOS and PROJ with it:

```powershell
.\osgeo4w-setup.exe -q -k -r -A -s https://download.osgeo.org/osgeo4w/v2/ -P gdal -R $env:LOCALAPPDATA\OSGeo4W
```

**Trap 1: the DLL is found by name, and the name will not match.** Django 5.2
probes for `gdal310` down to `gdal301`. OSGeo4W currently ships `gdal313`, so
the library is installed, on your PATH, and still "not found". Putting it on
PATH does not help - the name is the problem. Give the full path in
`backend/.env` instead (gitignored, because this is a fact about one machine):

```bash
GDAL_LIBRARY_PATH=C:/Users/<you>/AppData/Local/OSGeo4W/bin/gdal313.dll
GEOS_LIBRARY_PATH=C:/Users/<you>/AppData/Local/OSGeo4W/bin/geos_c.dll
```

**Trap 2: those two lines will break the container if you let them.** Compose
loads the same `backend/.env` through `env_file`, so a Windows path reaches the
Linux container, and the API dies on import with `cannot open shared object
file`. `infra/docker-compose.yml` blanks both in its `environment:` block to
stop that. If you add any other machine-specific path to `.env`, ask what it
does inside the container.

**Ports.** The stack publishes Postgres on **55432** and Redis on **56379**, not
5432 and 6379. This is not arbitrary: a developer machine with PostgreSQL
installed natively already has `postgres.exe` on 5432, and it wins the port
while Docker still reports 5432 as published - so `localhost:5432` silently
reaches the wrong database and fails with `password authentication failed`,
which reads like a bad password rather than a bad server. Redis had the same
problem with other projects on 6379 and 6380. Point `.env` at the published
ports:

```bash
DATABASE_URL=postgis://medilink:medilink@localhost:55432/medilink
REDIS_URL=redis://localhost:56379/0
```

Verify with `python manage.py check`, then `python manage.py migrate --check`,
then hit `/api/v1/facilities/nearby?lat=-1.94&lng=30.06` - that one endpoint
exercises GDAL, PostGIS and the Redis cache together, so a 200 means the whole
chain is wired.

## 2. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Docker Desktop | latest | WSL2 backend enabled |
| Python | 3.11 or 3.12 | Inside WSL2/container |
| Node.js | 20 LTS | Native Windows is fine |
| Git | latest | |

## 3. Infrastructure

```yaml
# infra/docker-compose.yml
services:
  db:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_DB: medilink
      POSTGRES_USER: medilink
      POSTGRES_PASSWORD: medilink
    ports: ["55432:5432"]     # 55432 on the host - see section 1a
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U medilink"]
      interval: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    ports: ["56379:6379"]     # 6379 and 6380 are usually taken

  mailhog:                      # catches OTP emails in development
    image: mailhog/mailhog
    ports: ["8025:8025"]

volumes:
  pgdata:
```

```bash
# Brings up all three: postgis, redis, and the API on :8000.
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml ps      # all healthy?

# First time only - copy the example env. The compose file overrides
# DATABASE_URL and REDIS_URL to the service hostnames, so the localhost
# values in the example are only for a native WSL2 run.
cp backend/.env.example backend/.env
```

Use the **`postgis/postgis` image, not plain `postgres`.** Adding PostGIS to a
stock Postgres image afterwards is more work than it looks.

## 4. Backend, containerised (recommended)

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        binutils libproj-dev gdal-bin libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

`binutils`, `libproj-dev` and `gdal-bin` are exactly what GeoDjango needs. Omit
any of them and Django raises `OSError: could not find the GDAL library` at
import time.

## 5. Backend, WSL2 native (faster iteration)

> **This section is WSL2 or Linux only** - the `apt` packages below do not
> exist on Windows. For native Windows see section 1a, which covers the same
> ground with OSGeo4W.
>
> One symptom is worth knowing either way: if a `pip install` aborts part-way
> it leaves the venv empty, and the next command fails with
> `ModuleNotFoundError: No module named 'django'`. That message is about the
> half-finished install, not about GDAL - check `pip list` before chasing
> native libraries.
>
> `docker compose -f infra/docker-compose.yml up -d` brings up the database,
> Redis and the API together. Edits are bind-mounted, so the reloader picks
> them up without a rebuild - the iteration speed is the same.

```bash
sudo apt update
sudo apt install -y python3.12-venv binutils libproj-dev gdal-bin libgdal-dev

cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_accounts   # one account per user type
python manage.py runserver
```

## 6. Dependencies

[`backend/requirements.txt`](../backend/requirements.txt) and
[`backend/requirements-dev.txt`](../backend/requirements-dev.txt) are the
source of truth. They are deliberately **not** duplicated here.

A copy in a document drifts silently, and the drift is dangerous rather than
merely untidy: this section used to pin `Django==5.0.*`, which reached end of
life carrying nine advisories. Anyone who trusted the document over the file
would have installed the vulnerable version on purpose.

Every dependency is pinned to an exact version, not a range. `5.0.*` resolves
to something different on Tuesday than it did on Monday, which means a build
that passed cannot be reproduced.

Check them with:

```bash
docker compose -f infra/docker-compose.yml exec api pip-audit
```

## 7. Settings

```python
# backend/config/settings/base.py
import environ

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

DATABASES = {
    "default": {
        **env.db("DATABASE_URL"),
        "ENGINE": "django.contrib.gis.db.backends.postgis",   # not postgresql
    }
}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django.contrib.gis",                 # required for PointField
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "apps.facilities",
    "apps.insurance",
    "apps.patients",
    "apps.scheduling",
    "apps.queueing",
    "apps.notifications",
    "apps.gateway",
]

TIME_ZONE = "Africa/Kigali"
USE_TZ = True

LANGUAGE_CODE = "rw"
LANGUAGES = [("rw", "Kinyarwanda"), ("en", "English"), ("fr", "Francais")]

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL"),
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "300/min",
        "otp": "3/15min",
    },
}
```

Two settings that cause real bugs if wrong:

- **`ENGINE` must be `django.contrib.gis.db.backends.postgis`.** With the plain
  `postgresql` backend, `PointField` fails at migration time with a confusing
  error.
- **`TIME_ZONE = "Africa/Kigali"` with `USE_TZ = True`.** Store UTC, render CAT.
  Opening hours are naive local times and are compared against
  `timezone.localtime()`, never `datetime.now()`.

## 8. Environment variables

```bash
# .env.example
SECRET_KEY=change-me-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DATABASE_URL=postgis://medilink:medilink@localhost:55432/medilink
REDIS_URL=redis://localhost:56379/0

CELERY_BROKER_URL=redis://localhost:56379/1

# Identity
NATIONAL_ID_PEPPER=change-me-and-never-rotate-casually

# Channels - blank in development, sandbox values in staging
USSD_SHARED_SECRET=
USSD_ALLOWED_IPS=
SMS_API_KEY=
SMS_SENDER_ID=MEDILINK
WA_VERIFY_TOKEN=
WA_APP_SECRET=
WA_PHONE_NUMBER_ID=

# Behaviour
MIN_SERVICE_TIME_SAMPLES=20
DEFAULT_SEARCH_RADIUS_M=5000
LEAVE_BY_BUFFER_MINUTES=10
```

`.env` is git-ignored. `.env.example` is committed and must list every key, with
placeholder values only.

## 9. Frontend

```bash
cd web
npm install
npm run dev            # http://localhost:5173

```

```ts
// web/vite.config.ts
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: manifestConfig,
      workbox: {
        runtimeCaching: [
          {
            urlPattern: /\/api\/v1\/facilities\/nearby/,
            handler: "NetworkFirst",
            options: {
              cacheName: "nearby",
              expiration: { maxAgeSeconds: 86400 },
            },
          },
          {
            urlPattern: /\/api\/v1\/queue\/entries/,
            handler: "NetworkOnly",        // never serve a stale position
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
})
```

The Vite proxy avoids CORS entirely in development. Configure
`django-cors-headers` for staging and production only.

## 10. Generating the API client

```bash
# From backend, with the server running
python manage.py spectacular --file ../schema.yaml

# From each frontend
npx openapi-typescript ../schema.yaml -o src/api/types.ts
```

Add to `package.json`:

```json
{ "scripts": { "gen:api": "openapi-typescript ../schema.yaml -o src/api/types.ts" } }
```

Run `gen:api` in CI and fail the build on any diff, so a stale client is caught
before merge.

## 11. Seed data

```bash
python manage.py loaddata fixtures/insurers.json fixtures/service_types.json fixtures/kigali_facilities.json
python manage.py seed_demo
```

`seed_demo` is a custom management command that attaches plausible opening
hours, services and insurers to the fixture facilities and marks them verified,
so a developer sees a live-looking app on first run rather than an empty one.
It prints a warning every time, because the coordinates it verifies are
approximate. Never run it against production. See `backend/fixtures/README.md`.

**Facility fixtures need real coordinates.** Collect them by walking to each
facility with a phone; a plausible-looking made-up coordinate produces a demo
that ranks facilities wrongly and hides bugs in the geo query.

## 12. Common problems

| Symptom | Cause | Fix |
|---|---|---|
| `OSError: could not find the GDAL library` | Native libs missing | Use Docker or `apt install gdal-bin libgdal-dev` |
| `type "geography" does not exist` | PostGIS extension not created | Run the `CreateExtension("postgis")` migration |
| Every facility 10,000 km away | `Point(lat, lng)` argument order | Use `Point(lng, lat)` |
| Radius of 5000 returns the whole country | Field is `geometry`, not `geography` | Set `geography=True` |
| Nearby search is slow with 300 rows | Missing GIST index | Add the index migration from doc 02 |
| Opening hours off by two hours | `datetime.now()` used | Use `timezone.localtime()` |
| Blank USSD screen | Exception escaped the handler | Wrap in try/except returning `END` |
| Duplicate "Leave now" SMS | Overlapping beat tasks | Rely on the `Notification` unique constraint |
| `OSError: No translation files found for default language rw` | `LANGUAGE_CODE = "rw"`; Django ships no Kinyarwanda catalog | Keep `LANGUAGE_CODE = "en-us"` (it only governs the admin). Patient-facing Kinyarwanda lives in the React bundle and the `name_rw` columns |
| `loaddata`: `null value in column "created_at"` | `loaddata` performs raw saves, which skip `auto_now_add` / `auto_now` | Include `created_at` and `updated_at` in the fixture rows |
| `docker run -v` mount silently ignored on Windows; container runs stale baked-in code | Git Bash rewrites `/app` to `C:/Program Files/Git/app` | Prefix the command with `MSYS_NO_PATHCONV=1`, and pass the host path via `pwd -W` |
| ~25 tests fail in a full run but pass when run alone, many asserting `429` | pytest-django resolves settings as `--ds` → `DJANGO_SETTINGS_MODULE` env var → ini option, so the compose service's exported `config.settings.dev` **beat** the ini setting. Dev settings mean Redis cache and live throttling, so one shared IP spends the rate-limit budget | Already fixed: `addopts` in `backend/pyproject.toml` passes `--ds=config.settings.test`, which wins over the environment. Do not remove it as "redundant" |

That third row costs hours if you do not know it: the container starts fine and
runs the code copied in at **build** time, so edits appear to have no effect.

## 13. Definition of "environment is working"

On Windows, run all four **inside the container** — there is no supported
native GDAL path on this machine, and the compose stack is the whole
environment:

```bash
cd infra && docker compose up -d --build
docker compose exec api python manage.py check          # no issues
docker compose exec api python manage.py migrate --check # no pending migrations
docker compose exec api pytest                           # 585 passed, 94% cover
docker compose exec api curl "localhost:8000/api/v1/facilities/nearby?lat=-1.9536&lng=30.0606"
```

Verified on 2026-08-24: 585 passed in 69 s, 94% coverage. If your run reports
fewer, check the settings-module row in section 12 before assuming a
regression.

That last command must return real Kigali facilities with sane `distance_m`
values. If distances look wrong, stop and fix the coordinate order before
writing anything else - the bug is silent and it poisons everything downstream.
