"""Standalone server-rendered frontend settings.

This project owns browser sessions and templates only. Marketplace records,
identity, notifications, escrow, and support operations remain in the API.
"""
from pathlib import Path
import os

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent
ENVIRONMENT = config("ENVIRONMENT", default="development")
DEBUG = config("DEBUG", default=ENVIRONMENT != "production", cast=bool)
SECRET_KEY = config("SECRET_KEY", default="dev-only-change-me-before-deployment")  # nosec B105: documented development placeholder; production rejects it
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="http://localhost,http://127.0.0.1", cast=Csv())

# Ngrok tunnels: the public hostname changes every time the tunnel restarts, so
# development accepts any ngrok subdomain instead of forcing an .env edit (and a
# CSRF failure on every form post) after each restart. Production stays explicit.
NGROK_HOSTS = (".ngrok-free.app", ".ngrok-free.dev", ".ngrok.app", ".ngrok.dev", ".ngrok.io")
NGROK_ORIGINS = tuple("https://*" + suffix for suffix in NGROK_HOSTS)
if ENVIRONMENT != "production":
    ALLOWED_HOSTS = list(ALLOWED_HOSTS) + [h for h in NGROK_HOSTS if h not in ALLOWED_HOSTS]
    CSRF_TRUSTED_ORIGINS = list(CSRF_TRUSTED_ORIGINS) + [
        o for o in NGROK_ORIGINS if o not in CSRF_TRUSTED_ORIGINS
    ]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "frontend.apps.frontendConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Compress HTML and JSON on the way out: pages are text, and a 10x smaller
    # body is the difference between a snappy page and a slow one on mobile data.
    "django.middleware.gzip.GZipMiddleware",
    # Sits in front of WhiteNoise: WhiteNoise answers a static request without
    # calling anything after it, so the cache header has to be extended on the
    # way out of a middleware that wraps it (see frontend/middleware.py).
    "frontend.middleware.StaticCacheMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "frontend.security_middleware.SecurityHeadersMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "frontend.middleware.PageTimingMiddleware",
]

# Local review harness only. A sandboxed preview frame (or any embedded
# browser) posts with ``Origin: null``, which CSRF can never trust; this shim
# rewrites that header to the host the request reached. It follows DEBUG: a
# DEBUG server accepts those posts out of the box, and it is refused outright
# when DEBUG is off, so production cannot use it. Cookies stay SameSite=Lax,
# so a foreign site still cannot ride along.
_sandboxed_origin = config("ALLOW_SANDBOXED_ORIGIN", default=DEBUG, cast=bool)
if _sandboxed_origin and not DEBUG:
    raise RuntimeError(
        "ALLOW_SANDBOXED_ORIGIN is a local-review switch; never set it with DEBUG off."
    )
if _sandboxed_origin:
    MIDDLEWARE.insert(0, "frontend.security_middleware.SandboxedOriginMiddleware")

ROOT_URLCONF = "frontend.urls"
WSGI_APPLICATION = "frontend.wsgi.application"
ASGI_APPLICATION = "frontend.asgi.application"

# Production loads each template once. Without the cached loader a debug server
# re-reads and re-compiles every {% include %} in every row, which makes console
# pages several times slower than they are in production. Django forbids the
# app-directories shortcut alongside explicit loaders, so the loader list spells
# both loaders out. Set TEMPLATE_UNCACHED=1 while editing templates if needed.
_TEMPLATE_CACHE = not config("TEMPLATE_UNCACHED", default=False, cast=bool)
_TEMPLATE_OPTIONS = {
    "context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "frontend.context_processors.notifications",
        "frontend.context_processors.unread_messages",
    ],
}
if _TEMPLATE_CACHE:
    _TEMPLATE_OPTIONS["loaders"] = [(
        "django.template.loaders.cached.Loader",
        [
            "django.template.loaders.filesystem.Loader",
            "django.template.loaders.app_directories.Loader",
        ],
    )]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": not _TEMPLATE_CACHE,
        "OPTIONS": _TEMPLATE_OPTIONS,
    },
]
# Only local UI state lives here. User accounts remain on the API.
SESSION_DB_PATH = Path(config("frontend_SESSION_DB", default="frontend_sessions.sqlite3"))
if not SESSION_DB_PATH.is_absolute():
    SESSION_DB_PATH = BASE_DIR / SESSION_DB_PATH
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(SESSION_DB_PATH),
    }
}

# Conversation media (audio/video descriptions) is validated at 30 MB by the API.
# Django only counts non-file POST fields here; large files spool to disk.
DATA_UPLOAD_MAX_MEMORY_SIZE = 32 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STATICFILES_BACKEND = (
    "django.contrib.staticfiles.storage.StaticFilesStorage"
    if DEBUG
    else "whitenoise.storage.CompressedManifestStaticFilesStorage"
)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": STATICFILES_BACKEND},
}

# A page asks the browser for ~24 static files before it can paint. Django's
# development static handler answers each one with no ETag and no Cache-Control,
# so every visit re-downloads every file. WhiteNoise answers them with an ETag
# and a cache header from the same source tree. It only takes over when the
# server is started with --nostatic; without that flag runserver keeps doing the
# old thing, so this cannot break a start command that has not been updated.
if DEBUG:
    WHITENOISE_USE_FINDERS = True   # serve straight from static/, no collectstatic
    WHITENOISE_AUTOREFRESH = True   # pick up an edited file without a restart
    # Dev: cache static files for ten minutes instead of re-asking for all
    # nineteen on every page. Versioned URLs carry the file's own stamp, so an
    # edited stylesheet or script gets a new address and is fetched immediately.
    WHITENOISE_MAX_AGE = 600
    WHITENOISE_INDEX_FILE = False

# The frontend always calls the independent API over HTTP. Never use in-process routing here.
ARTISAN_API_BASE_URL = config(
    "ARTISAN_API_BASE_URL",
    default="http://127.0.0.1:8000/api/v1",
).rstrip("/")
ARTISAN_API_ROOT_URL = config(
    "ARTISAN_API_ROOT_URL",
    default=ARTISAN_API_BASE_URL.removesuffix("/api/v1"),
).rstrip("/")
ARTISAN_API_TIMEOUT = config("ARTISAN_API_TIMEOUT", default=20, cast=int)
ARTISAN_API_TRANSPORT = "http"
# If ARTISAN_API_BASE_URL points at a public address (an ngrok tunnel) while the
# API is running on this machine, every page pays an internet round trip per
# API call. When that address stops answering, pages fall back to
# ARTISAN_API_LOCAL_URL for a minute and log one line saying so.
ARTISAN_API_FALLBACK_LOCAL = config("ARTISAN_API_FALLBACK_LOCAL", default=True, cast=bool)
ARTISAN_API_LOCAL_URL = config("ARTISAN_API_LOCAL_URL", default="http://127.0.0.1:8000")
# Any page slower than this is logged with its split between API time and
# render time, so a slow page names itself instead of being guessed at.
SLOW_PAGE_LOG_MS = config("SLOW_PAGE_LOG_MS", default=500, cast=int)

SESSION_ENGINE = "django.contrib.sessions.backends.db"
# Two projects share one host in local testing (8080 for the site, 8000 for the
# API) and cookies ignore the port: with the default names, opening the API in
# the same browser overwrites this site's "sessionid"/"csrftoken", and the next
# form POST fails CSRF with "token from POST incorrect". Distinct names keep the
# two projects' cookies apart on one host and on a shared production domain.
SESSION_COOKIE_NAME = config(
    "SESSION_COOKIE_NAME", default="artisan_frontend_session"
)
CSRF_COOKIE_NAME = config("CSRF_COOKIE_NAME", default="artisan_frontend_csrf")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = config(
    "SESSION_COOKIE_SAMESITE",
    default="None" if ENVIRONMENT == "production" else "Lax",
)
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=ENVIRONMENT == "production", cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=ENVIRONMENT == "production", cast=bool)
CSRF_COOKIE_SAMESITE = "Lax"
# A page left open across a sign-in sends an out-of-date token. Say that plainly
# instead of showing Django's raw 403 page.
CSRF_FAILURE_VIEW = "frontend.csrf_failure.csrf_failure"
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=ENVIRONMENT == "production", cast=bool)
SECURE_CONTENT_TYPE_NOSNIFF = True
# Same-origin requests keep sending their full address (Django reads it for the
# "back to where you were" links and CSRF referer checks); every other site
# gets no Referer at all. `no-referrer` here would silence both.
SECURE_REFERRER_POLICY = "same-origin"
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False, cast=bool)
SECURE_HSTS_PRELOAD = config("SECURE_HSTS_PRELOAD", default=False, cast=bool)
TRUST_PROXY_SSL_HEADER = config("TRUST_PROXY_SSL_HEADER", default=ENVIRONMENT == "production", cast=bool)
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https") if TRUST_PROXY_SSL_HEADER else None
)
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_RESOURCE_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_CSP_ENABLED = config("SECURE_CSP_ENABLED", default=ENVIRONMENT == "production", cast=bool)
SECURE_CSP = config(
    "SECURE_CSP",
    default="default-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data: https:; font-src 'self' data:; style-src 'self'; script-src 'self'; object-src 'none'",
)

if ENVIRONMENT == "production":
    if DEBUG:
        raise RuntimeError("DEBUG must be False in production.")
    if len(SECRET_KEY) < 50 or SECRET_KEY == "dev-only-change-me-before-deployment":  # nosec B105: reject this development-only placeholder in production
        raise RuntimeError("Set a unique SECRET_KEY (50+ characters) for production.")
    if not config("ALLOWED_HOSTS", default="").strip() or not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise RuntimeError("Set explicit, non-wildcard ALLOWED_HOSTS for production.")
    if not config("CSRF_TRUSTED_ORIGINS", default="").strip() or not CSRF_TRUSTED_ORIGINS:
        raise RuntimeError("Set the exact HTTPS CSRF_TRUSTED_ORIGINS for production.")
    if any(not origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS):
        raise RuntimeError("All production CSRF_TRUSTED_ORIGINS must use HTTPS.")
    if not SESSION_COOKIE_SECURE or not CSRF_COOKIE_SECURE or not SECURE_SSL_REDIRECT:
        raise RuntimeError("Secure session/CSRF cookies and HTTPS redirects must be enabled in production.")
    if SESSION_COOKIE_SAMESITE.lower() != "none":
        raise RuntimeError("Production Apple web callbacks require SESSION_COOKIE_SAMESITE=None.")
    if SECURE_HSTS_SECONDS < 1:
        raise RuntimeError("SECURE_HSTS_SECONDS must be enabled in production after HTTPS is verified.")
    if not ARTISAN_API_BASE_URL.startswith("https://") or not ARTISAN_API_ROOT_URL.startswith("https://"):
        raise RuntimeError("ARTISAN_API_BASE_URL and ARTISAN_API_ROOT_URL must use HTTPS in production.")

STATICFILES_STORAGE = STATICFILES_BACKEND

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": config("LOG_LEVEL", default="INFO")},
}
