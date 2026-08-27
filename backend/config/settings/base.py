"""Base settings shared by every environment."""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    DEFAULT_SEARCH_RADIUS_M=(int, 5000),
    MIN_SERVICE_TIME_SAMPLES=(int, 20),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # GeoDjango - required for PointField
    "django.contrib.gis",
    # Third party
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    # Local - Phase 0
    "apps.facilities",
    "apps.insurance",
    # Local - Phase 1
    "apps.patients",
    "apps.staff",
    "apps.queueing",
    # Local - Phase 2
    "apps.scheduling",
    "apps.notifications",
    "apps.platform_admin",
    "apps.accounts",
    # Local - Phase 3
    "apps.gateway",
    # Local - Phase 4
    "apps.triage",
    # Redesign R1
    "apps.providers",
    # Redesign R2
    "apps.search",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ENGINE must be the postgis backend, not django.db.backends.postgresql.
# With the plain backend, PointField fails at migration time.
DATABASES = {
    "default": {
        **env.db("DATABASE_URL"),
        "ENGINE": "django.contrib.gis.db.backends.postgis",
    }
}

# Where to find the native GDAL and GEOS libraries, when they are not on a
# path Django already searches.
#
# **Only Windows needs these.** The Docker image installs libgdal through apt,
# where the versioned soname is exactly what Django probes for. The container
# does NOT get to inherit these: compose reads the same `backend/.env` through
# `env_file`, so it blanks both in its `environment:` block - otherwise the
# API tries to dlopen a `C:\` path and dies on import. On Windows there is no GDAL
# wheel on PyPI - OSGeo4W is the supported route - and it installs
# `gdal313.dll`, while Django 5.2 only probes the names `gdal310` down to
# `gdal301`. The DLL is present and still not found, so the path has to be
# given explicitly rather than put on PATH.
#
# Set both in `backend/.env`, which is gitignored, because the location is a
# fact about one machine and not about this project:
#
#     GDAL_LIBRARY_PATH=C:/OSGeo4W/bin/gdal313.dll
#     GEOS_LIBRARY_PATH=C:/OSGeo4W/bin/geos_c.dll
#
# Unset is the normal case and means "search the usual places".
if _gdal := env("GDAL_LIBRARY_PATH", default=""):
    GDAL_LIBRARY_PATH = _gdal
if _geos := env("GEOS_LIBRARY_PATH", default=""):
    GEOS_LIBRARY_PATH = _geos

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/0"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# LANGUAGE_CODE governs Django's OWN interface strings - effectively just the
# admin, which MediLink ops staff use. Django ships no Kinyarwanda catalog, so
# setting it to "rw" raises OSError at startup.
#
# The patient-facing default language IS Kinyarwanda; that is handled where it
# actually matters - the React i18n bundle, and the name_rw/name_en/name_fr
# columns on ServiceType. Do not "fix" this back to "rw" without first adding
# locale/rw/LC_MESSAGES/django.po.
LANGUAGE_CODE = "en-us"

# Languages MediLink itself serves content in. Kinyarwanda first.
LANGUAGES = [
    ("rw", "Kinyarwanda"),
    ("en", "English"),
    ("fr", "Francais"),
]
PATIENT_DEFAULT_LANGUAGE = "rw"
TIME_ZONE = "Africa/Kigali"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    # Patient-facing discovery is public; staff endpoints opt in with
    # IsAuthenticated + IsFacilityStaff.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    # Patient tokens are checked first and are structurally separate from
    # staff users: a PatientPrincipal has no `staffmember`, so it can never
    # satisfy IsFacilityStaff even if a view forgets to check.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.patients.auth.PatientJWTAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    # Staff hammer these endpoints all day; patients do not. The patient
    # queue view is polled every 20 s, which is 3/min per entry.
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "600/min",
        "otp": "3/15min",
        # Password guessing, kept off the general anon bucket so ordinary
        # browsing cannot spend an attacker's budget or vice versa.
        "signin": "10/min",
    },
    "EXCEPTION_HANDLER": "config.exceptions.rfc7807_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),  # covers a full shift
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "MediLink Rwanda API",
    "DESCRIPTION": "Nearby facilities, insurance acceptance, and live queues.",
    "VERSION": "0.2.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    # Two different fields are called "status". Without explicit names,
    # drf-spectacular invents a hash suffix (StatusC95Enum) that can change
    # between runs and churn the committed schema.yaml.
    "ENUM_NAME_OVERRIDES": {
        "WaitStatusEnum": "apps.facilities.wait.ALL_STATUSES",
        "QueueEntryStatusEnum": "apps.queueing.models.QueueEntry.Status",
    },
}

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

# --- MediLink domain settings ------------------------------------------------

# Rwanda bounding box. Any coordinate outside this is rejected as invalid,
# which catches desktop IP-geolocation and VPN users before they reach the DB.
RWANDA_BOUNDS = {"lat": (-2.92, -1.02), "lng": (28.80, 30.95)}

DEFAULT_SEARCH_RADIUS_M = env("DEFAULT_SEARCH_RADIUS_M")
MAX_SEARCH_RADIUS_M = 50000
SEARCH_EXPANSION_STEPS_M = (5000, 10000, 25000, 50000)
MIN_RESULTS_BEFORE_EXPANDING = 3

# Never publish a wait estimate derived from fewer samples than this.
MIN_SERVICE_TIME_SAMPLES = env("MIN_SERVICE_TIME_SAMPLES")

# Pepper for national-ID hashing. Never stored in the database, so a dump
# alone cannot brute-force the short, structured ID space. See docs/08.
NATIONAL_ID_PEPPER = env("NATIONAL_ID_PEPPER", default="")

# --- Phase 2 ------------------------------------------------------------------

OTP_LIFETIME = timedelta(minutes=5)
OTP_MAX_ATTEMPTS = 5

# Minutes of slack added when telling a patient to set off. Rounded generously
# on purpose: leaving too early costs a few minutes in a waiting room, leaving
# too late costs the patient their place in the queue.
LEAVE_BY_BUFFER_MINUTES = env.int("LEAVE_BY_BUFFER_MINUTES", default=10)

# ConsoleSMSBackend prints instead of sending, so no developer machine ever
# texts a real patient. Production must set this to a real gateway.
SMS_BACKEND = env("SMS_BACKEND", default="apps.notifications.sms.ConsoleSMSBackend")
SMS_SENDER_ID = env("SMS_SENDER_ID", default="MEDILINK")

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=env("REDIS_URL", default=""))
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TIMEZONE = TIME_ZONE

# The version of the privacy notice a patient agrees to at registration,
# recorded against their consent. Bump it when the notice changes materially -
# a later revision does not retroactively become what somebody agreed to, and
# this is how you find who needs asking again. See docs/08 section 6.
# Patient identifiers are scrubbed on the way OUT, on the handler, so it
# applies to third-party loggers too. See config/logging.py for why this is a
# filter rather than a rule people are asked to remember.
from config.logging import LOGGING  # noqa: E402,F401

PRIVACY_NOTICE_VERSION = env("PRIVACY_NOTICE_VERSION", default="2026-08")
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)

# --- Phase 3: USSD and WhatsApp ----------------------------------------------

# Blank in development runs against the aggregator sandbox. Production
# refuses unauthenticated webhooks - see apps/gateway/security.py.
USSD_SHARED_SECRET = env("USSD_SHARED_SECRET", default="")
USSD_ALLOWED_IPS = env.list("USSD_ALLOWED_IPS", default=[])

WA_VERIFY_TOKEN = env("WA_VERIFY_TOKEN", default="")
WA_APP_SECRET = env("WA_APP_SECRET", default="")
WA_ACCESS_TOKEN = env("WA_ACCESS_TOKEN", default="")
WA_PHONE_NUMBER_ID = env("WA_PHONE_NUMBER_ID", default="")

# --- Phase 4: triage ---------------------------------------------------------

# The symptom checker is UNAVAILABLE unless all four of these are set.
# Anything that routes patients toward or away from care carries clinical
# liability, so the gate is enforced in code rather than trusted to a
# checklist. See apps/triage/gate.py and docs/08 section 8.
#
# Do not set these to make tests pass or to demo the feature. They are a
# record that a named, licensed clinician reviewed a specific protocol
# version and signed it off.
TRIAGE_PROTOCOL_VERSION = env("TRIAGE_PROTOCOL_VERSION", default="")
TRIAGE_APPROVED_BY = env("TRIAGE_APPROVED_BY", default="")
TRIAGE_APPROVED_ON = env("TRIAGE_APPROVED_ON", default="")
TRIAGE_PROTOCOL_FILE = env("TRIAGE_PROTOCOL_FILE", default="")
