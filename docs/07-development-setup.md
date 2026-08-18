# 07 - Development Setup

## 1. Read this first: GeoDjango on Windows

GeoDjango requires the native **GDAL**, **GEOS** and **PROJ** libraries. Installing
these directly on Windows via OSGeo4W is a genuine time sink and a recurring
source of "works on my machine" failures across a team.

**Run the backend in Docker or WSL2. Do not install GDAL natively on Windows.**

| Approach | Verdict |
|---|---|
| Docker Desktop + WSL2 backend | **Recommended** - identical for everyone |
| WSL2 Ubuntu, native Python | Good - `apt install gdal-bin libgdal-dev` just works |
| Native Windows + OSGeo4W | Avoid - expect to lose days to DLL paths |

The React apps run fine natively on Windows. Only the Django backend needs Linux.

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
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U medilink"]
      interval: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    ports: ["6380:6379"]

  mailhog:                      # catches OTP emails in development
    image: mailhog/mailhog
    ports: ["8025:8025"]

volumes:
  pgdata:
```

```bash
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml ps      # all healthy?
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

```bash
sudo apt update
sudo apt install -y python3.12-venv binutils libproj-dev gdal-bin libgdal-dev

cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## 6. `requirements.txt`

```
Django==5.0.*
djangorestframework==3.15.*
djangorestframework-simplejwt==5.3.*
drf-spectacular==0.27.*
psycopg[binary]==3.1.*
django-cors-headers==4.3.*
django-environ==0.11.*
celery==5.3.*
redis==5.0.*
django-redis==5.4.*
phonenumbers==8.13.*
```

```
# requirements-dev.txt
pytest==8.*
pytest-django==4.8.*
pytest-cov==5.*
factory-boy==3.3.*
freezegun==1.4.*
ruff==0.4.*
django-debug-toolbar==4.3.*
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

DATABASE_URL=postgis://medilink:medilink@localhost:5432/medilink
REDIS_URL=redis://localhost:6380/0

CELERY_BROKER_URL=redis://localhost:6380/1

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
cd web-patient
npm install
npm run dev            # http://localhost:5173

cd ../web-provider
npm install
npm run dev            # http://localhost:5174
```

```ts
// web-patient/vite.config.ts
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

That third row costs hours if you do not know it: the container starts fine and
runs the code copied in at **build** time, so edits appear to have no effect.

## 13. Definition of "environment is working"

```bash
python manage.py check                      # no issues
python manage.py migrate --check            # no pending migrations
pytest                                       # all green
curl "localhost:8000/api/v1/facilities/nearby?lat=-1.9536&lng=30.0606"
```

That last command must return real Kigali facilities with sane `distance_m`
values. If distances look wrong, stop and fix the coordinate order before
writing anything else - the bug is silent and it poisons everything downstream.
