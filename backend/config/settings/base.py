"""Base settings shared by every environment."""

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
    # Phase 0 is entirely public - no accounts exist yet.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": "60/min"},
    "EXCEPTION_HANDLER": "config.exceptions.rfc7807_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "MediLink Rwanda API",
    "DESCRIPTION": "Find nearby health facilities and check insurance acceptance.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v1",
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
