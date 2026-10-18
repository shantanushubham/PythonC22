"""Django settings for the AirPay payment gateway.

Everything that changes between machines is read from the environment. The defaults
work for local development against the Postgres container in docker-compose.yml.
"""

import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: list[str]) -> list[str]:
    value = os.environ.get(name)
    if value is None:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


# --- Core ------------------------------------------------------------------------------

# DEBUG defaults to on for local work. Turn it off with DJANGO_DEBUG=0. When it is off,
# a real secret key and host list are required, so a production start cannot silently
# use the development values.
DEBUG = env_bool("DJANGO_DEBUG", True)

_DEV_SECRET_KEY = "django-insecure-dev-only-key-do-not-use-in-production"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", _DEV_SECRET_KEY if DEBUG else "")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1", "[::1]"] if DEBUG else [])

if not DEBUG:
    if not SECRET_KEY or SECRET_KEY == _DEV_SECRET_KEY:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY when DJANGO_DEBUG is off.")
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS when DJANGO_DEBUG is off.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",  # lets logout and refresh revoke tokens
    "drf_spectacular",
    # AirPay
    "core",
    "customers",
    "payments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# --- Database --------------------------------------------------------------------------

# Postgres by default, matching docker-compose.yml. DB_ENGINE=sqlite runs the project
# with no database server, which is handy for a quick look or for tests.
DB_ENGINE = os.environ.get("DB_ENGINE", "postgres").lower()

if DB_ENGINE == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "payment_gateway_db"),
            "USER": os.environ.get("POSTGRES_USER", "payment_gateway_user"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "payment_gateway_password"),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            # Keep connections open between requests instead of reconnecting each time.
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
        }
    }
elif DB_ENGINE == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    raise ImproperlyConfigured(f"DB_ENGINE must be 'postgres' or 'sqlite', got {DB_ENGINE!r}.")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Customers and passwords ------------------------------------------------------------

# The login user is a Customer (customers/models.py). This must be set before the first
# migration of a database. Changing it later needs a fresh database.
AUTH_USER_MODEL = "customers.Customer"

# Passwords are hashed with bcrypt and a random salt per password. The SHA-256 variant
# is used because plain bcrypt silently ignores everything after 72 bytes of a password.
# It is the only hasher listed, so no weaker hash can ever be created or accepted.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.BCryptSHA256PasswordHasher"]

# --- API keys ---------------------------------------------------------------------------

# HMAC pepper for API keys. When empty, a key is derived from SECRET_KEY. Set a dedicated
# value so rotating the JWT secret does not revoke every payment key.
API_KEY_PEPPER = os.environ.get("API_KEY_PEPPER", "")
API_KEY_MAX_PER_CUSTOMER = int(os.environ.get("API_KEY_MAX_PER_CUSTOMER", "20"))
API_KEY_MAX_LIFETIME_DAYS = int(os.environ.get("API_KEY_MAX_LIFETIME_DAYS", "365"))

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


# --- Django REST framework ---------------------------------------------------------------

REST_FRAMEWORK = {
    # The API speaks JSON only. The browsable HTML API is left out on purpose.
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    # Closed by default. A view that should be public says so with AllowAny.
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Every error has the same shape, the one the AirPay mock services use.
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.environ.get("API_ANON_RATE", "100/minute"),
        # Login attempts per IP address. Slows down password guessing.
        "login": os.environ.get("API_LOGIN_RATE", "10/minute"),
    },
}

# --- JWT ----------------------------------------------------------------------------------

SIMPLE_JWT = {
    # Short lived, because an access token cannot be revoked once it is issued.
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.environ.get("JWT_ACCESS_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.environ.get("JWT_REFRESH_DAYS", "7"))),
    # Every refresh returns a new refresh token and revokes the old one. A stolen refresh
    # token that is used a second time is rejected.
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "AirPay Payment Gateway API",
    "DESCRIPTION": "The AirPay payment gateway. Accepts payments and routes them to the card, "
    "UPI and netbanking services.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "TAGS": [
        {"name": "Health", "description": "Is the gateway up."},
        {"name": "Customers", "description": "Sign up and manage your account."},
        {"name": "Auth", "description": "Log in and manage JWT access and refresh tokens."},
        {"name": "API keys", "description": "Create and revoke keys used to call the payment API."},
        {"name": "Payments", "description": "Payment operations. These take an API key, not a JWT."},
    ],
    "COMPONENT_SPLIT_REQUEST": True,
}
