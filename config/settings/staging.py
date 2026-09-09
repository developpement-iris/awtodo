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

# Ex. "awtodo.onrender.com" (nom exact du service Render une fois créé).
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

# Render termine le TLS sur son proxy et pose X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Ex. ["https://awtodo.onrender.com"] — requis par Django pour l'admin et
# toute requête POST cross-origin sur un domaine HTTPS.
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])


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

# Même domaine que l'API maintenant que Django sert le front.
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL")


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
