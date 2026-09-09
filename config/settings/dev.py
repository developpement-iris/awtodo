from corsheaders.defaults import default_headers

from .base import *  # noqa: F401,F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Backend console par défaut (aucun envoi réel, contenu affiché dans le
# terminal `manage.py runserver`) — voir CLAUDE.md > "Roadmap macro" >
# validation reportée au déploiement (déliverabilité réelle, domaine
# d'expédition, DKIM/SPF... ça, ça attend toujours le déploiement).
# Pour recevoir de vrais emails de test (boîte sandbox type Mailtrap) sans
# attendre le déploiement AWS, créer un `.env` à la racine du projet à
# partir de `.env.example` et renseigner EMAIL_BACKEND=...smtp.EmailBackend
# + les identifiants SMTP — 100% local, ne touche à rien côté
# staging/production (jamais copier ces valeurs dans ces fichiers).
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=2525)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Awtodo <no-reply@awtodo.local>")

# Origine du frontend, pour construire une URL absolue (pas juste un chemin
# relatif) dans les emails d'invitation — voir
# apps/accounts/services.py::_send_invitation_email. Port Vite par défaut
# (5173) ; à ajuster dans `.env` si le front tourne ailleurs.
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://localhost:5173")

# API ouverte en dev uniquement, pour pouvoir tester le frontend sans SSO
# câblé. À remplacer par le SSO/JWT réel avant staging — ne jamais copier
# ce réglage dans base.py/staging.py/production.py.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
}

CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]

# django-cors-headers n'autorise par défaut qu'un jeu standard de headers.
# Le front envoie systématiquement X-Debug-User-Id dès qu'un utilisateur de
# démo est sélectionné (voir CLAUDE.md — mécanisme d'identification
# temporaire) : sans cette ligne, le preflight CORS le rejette et TOUTES les
# requêtes échouent silencieusement côté navigateur (curl ne le voit jamais,
# car curl n'est pas soumis à CORS).
CORS_ALLOW_HEADERS = [*default_headers, "x-debug-user-id"]
