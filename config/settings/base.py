from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)

_env_file = BASE_DIR / ".env"
if _env_file.exists():
    environ.Env.read_env(str(_env_file))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-dev-key-change-me")

DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    "apps.common",
    "apps.accounts",
    "apps.projects",
    "apps.tasks",
    "apps.incidents",
    "apps.budgeting",
    "apps.integrations",
    "apps.notifications",
    "apps.documentation",
    "apps.planning",
    "apps.communication",
]

MIDDLEWARE = [
    # En tout premier : doit rester le middleware le plus externe pour
    # s'appliquer même aux réponses court-circuitées par WhiteNoise (fichiers
    # statiques) plus bas dans la pile — voir apps/common/middleware.py.
    "apps.common.middleware.SecurityHeadersMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
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


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": env.db(
        "DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
    ),
}


AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "fr-fr"

TIME_ZONE = "Europe/Paris"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"

# WhiteNoise ajoute par défaut `Access-Control-Allow-Origin: *` sur TOUS les
# fichiers statiques (pensé pour les polices chargées depuis un autre
# domaine) — inutile ici, les polices sont déjà auto-hébergées sur le même
# domaine que le frontend (voir CLAUDE.md > "Stack technique"). C'est la
# cause du CORS wildcard sur les assets relevé par l'audit ZAP du
# 2026-09-21 (ex. /favicon-32.png), pas une config CORS applicative.
WHITENOISE_ALLOW_ALL_ORIGINS = False

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Django REST Framework
# API ouverte à des intégrations externes (ticketing, Power Automate) : le
# throttling ci-dessous est une protection applicative de base contre les
# abus, pas une protection anti-DDoS complète (qui relève de la couche
# infra AWS — WAF/Shield — hors périmètre de ce repo).
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # DebugUserIdAuthentication s'auto-désactive si DEBUG=False (voir la
    # classe elle-même) : sûr à lister ici même pour base.py/production.py.
    # JWTAuthentication (session du 2026-08-06, voir CLAUDE.md > "Stack
    # technique" > Auth) volontairement après le header debug : ce dernier
    # garde la priorité s'il est présent, cohérent avec son usage de bascule
    # rapide en test — la connexion réelle par mot de passe reste l'unique
    # mécanisme utilisable une fois DEBUG=False.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.DebugUserIdAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "20/min",
        "user": "100/min",
    },
    # Sûr par défaut : explicite plutôt que de laisser le AllowAny implicite
    # de DRF. Assoupli uniquement dans config/settings/dev.py.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
}

# Durée de vie généreuse délibérée (session du 2026-08-06) : aucune logique
# de rafraîchissement silencieux côté frontend dans cette passe (voir
# CLAUDE.md > "Stack technique" > Auth) — se reconnecter manuellement après
# expiration suffit pour l'instant plutôt que d'ajouter un intercepteur de
# retry. `rest_framework_simplejwt` n'a pas besoin d'être dans INSTALLED_APPS
# pour ce périmètre (pas de blacklist de tokens).
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Awtodo API",
    "DESCRIPTION": "API de gestion de projets, tâches et incidents d'Awtodo.",
    "VERSION": "1.0.0",
}

# Restrictif par défaut ; assoupli en dev, à renseigner via env pour un
# frontend déployé en staging/production.
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

# Réinitialisation de mot de passe en "lien direct" (voir
# docs/organisation-et-comptes.md > "Réinitialisation de mot de passe" >
# mode test). `True` = pas d'email envoyé, l'endpoint /password-reset/request/
# renvoie directement le chemin `/reset-password/<token>/` pour que le
# frontend y redirige. Réservé à la phase de test (pas de fournisseur
# transactionnel branché) — assumé sans enjeu de sécurité tant que le
# nombre d'utilisateurs se compte sur les doigts d'une main. Faux par
# défaut : dès qu'un vrai ESP sera câblé en production, l'email reprend la
# main sans rien changer d'autre. Activé dans `dev.py` et `staging.py`.
PASSWORD_RESET_DIRECT_LINK = env.bool("PASSWORD_RESET_DIRECT_LINK", default=False)

# Celery — pas de broker Redis provisionné pour l'instant (session du
# 2026-09-22, synchronisation Outlook). `CELERY_TASK_ALWAYS_EAGER=True`
# exécute une tâche immédiatement, dans le même processus qui l'a déclenchée,
# sans passer par un broker — la tâche reste écrite comme une vraie tâche
# Celery (`@shared_task`, déclenchée par `.delay(...)` après
# `transaction.on_commit`), prête à basculer en réellement asynchrone
# (Redis + `celery -A config worker`) en repassant ce réglage à False une
# fois `CELERY_BROKER_URL` renseigné, sans toucher au code métier. Chaque
# tâche (voir `apps.planning.tasks`) avale ses propres erreurs : un incident
# de synchro externe ne doit jamais faire échouer l'action Awtodo qui l'a
# déclenché, y compris en mode eager où une exception non rattrapée
# remonterait dans la requête HTTP.
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="memory://")
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=True)
CELERY_TASK_EAGER_PROPAGATES = env.bool("CELERY_TASK_EAGER_PROPAGATES", default=False)
