"""Réglages pour la phase de déploiement intermédiaire (Render + Supabase).

Voir docs/deploiement-intermediaire.md. Ce fichier est la cible Render :
Render lance le service avec DJANGO_SETTINGS_MODULE=config.settings.staging.

config/settings/production.py reste volontairement réservé au futur
déploiement AWS/RDS (toujours bloqué, voir CLAUDE.md) — ne pas y reporter
la config Render/Supabase ci-dessous.
"""

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, env

DEBUG = False

SECRET_KEY = env("DJANGO_SECRET_KEY")


def _clean_host(value):
    """Tolère une valeur collée avec le schéma ou un slash final
    (`https://awtodo.onrender.com/`) au lieu du hostname nu attendu."""
    return value.replace("https://", "").replace("http://", "").strip().strip("/")


# `RENDER_EXTERNAL_HOSTNAME` est injecté automatiquement par Render (ex.
# "awtodo.onrender.com") : le host est donc autorisé sans config manuelle.
# `DJANGO_ALLOWED_HOSTS` reste accepté en plus (domaine custom, etc.).
ALLOWED_HOSTS = [_clean_host(h) for h in env.list("DJANGO_ALLOWED_HOSTS", default=[]) if h.strip()]
_render_host = env("RENDER_EXTERNAL_HOSTNAME", default="").strip()
if _render_host and _render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_render_host)

# Render termine le TLS sur son proxy et pose X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Requis par Django pour l'admin et toute requête POST cross-origin en HTTPS.
CSRF_TRUSTED_ORIGINS = [
    f"https://{_clean_host(o)}" for o in env.list("CSRF_TRUSTED_ORIGINS", default=[]) if o.strip()
]
if _render_host:
    _render_origin = f"https://{_render_host}"
    if _render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_render_origin)


# --- Base de données : Supabase (Postgres) --------------------------------
# DATABASE_URL au format postgres://user:pass@host:5432/postgres fourni par
# Supabase (Project Settings > Database > Connection string > URI).
# Supabase EXIGE le SSL : sans sslmode=require la connexion échoue de façon
# peu explicite.
# CONN_MAX_AGE=0 : Supabase route souvent via un pooler pgbouncer (port 6543,
# mode transaction) qui n'aime pas les connexions persistantes Django ni les
# curseurs côté serveur. Sur le plan gratuit / faible trafic, ré-ouvrir la
# connexion à chaque requête est sans conséquence et évite ces pièges.
DATABASES = {
    "default": {
        **env.db("DATABASE_URL"),
        "CONN_MAX_AGE": 0,
        "DISABLE_SERVER_SIDE_CURSORS": True,
    },
}
DATABASES["default"].setdefault("OPTIONS", {})
DATABASES["default"]["OPTIONS"]["sslmode"] = "require"


# --- Statiques + frontend React (servis par Django via WhiteNoise) --------
# Pas de S3 dans cette phase (bloqué, réservé AWS). WhiteNoise sert :
#  - les statiques Django/DRF/admin (collectstatic -> STATIC_ROOT) sous /static/
#  - le build Vite du frontend (frontend/dist) directement à la racine
# ⚠️ Les médias uploadés (MEDIA) ne persistent PAS entre deux déploiements
#    sur le disque éphémère de Render. Limite connue et acceptée pour la
#    phase de test — voir docs/deploiement-intermediaire.md.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],  # noqa: F405
]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

_FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
WHITENOISE_ROOT = _FRONTEND_DIST
WHITENOISE_INDEX_FILE = True

# Fallback SPA : les routes client (/docs/<token>, etc.) renvoient index.html.
SPA_INDEX_FILE = _FRONTEND_DIST / "index.html"


# --- CORS ----------------------------------------------------------------
# Frontend servi par Django = même origine, CORS inutile en principe.
# Laissé pilotable par env pour un client externe pendant les tests.
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])


# --- Email -------------------------------------------------------------
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL", default="Awtodo <no-reply@awtodo.local>"
)

# Même domaine que l'API (Django sert le front) : défaut = le host Render.
FRONTEND_BASE_URL = env(
    "FRONTEND_BASE_URL",
    default=(f"https://{_render_host}" if _render_host else "http://localhost:8000"),
)


# --- Logs sur stdout (récupérés par Render) -----------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
