"""Appel en interne (même processus, pas d'aller-retour HTTP) d'un endpoint
`/api/v1/...` au nom d'un utilisateur.

C'est ce qui permet au serveur MCP d'exposer « tout ce que l'API permet »
sans dupliquer une seule règle : la requête traverse exactement la même vue
DRF qu'un appel du frontend — scoping des listes, permissions par objet,
serializers, services, signaux. Seule l'authentification change : l'utilisateur
est celui du jeton OAuth du connecteur Claude, forcé via `force_authenticate`.
"""

import json
import logging
from urllib.parse import urlencode

from django.urls import Resolver404, resolve
from rest_framework.test import APIRequestFactory, force_authenticate

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1/"

# Endpoints jamais atteignables via le connecteur : flux d'authentification
# (sans objet pour un utilisateur déjà connecté, et un mot de passe n'a rien
# à faire dans une conversation) et génération de clés API (la clé en clair
# finirait dans l'historique de la conversation Claude).
DENIED_PREFIXES = (
    "accounts/login/",
    "accounts/me/change-password/",
    "accounts/password-reset/",
    "integrations/api-keys/",
)

ALLOWED_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")

# Au-delà, la réponse est tronquée : une liste non filtrée peut peser lourd
# et noierait le contexte de Claude. Le message invite à filtrer.
MAX_RESPONSE_CHARS = 60_000


class ApiCallError(Exception):
    """Appel refusé avant même d'atteindre la vue (chemin inconnu, interdit...)."""


def normalize_path(path):
    """Accepte `tasks/`, `/tasks`, `/api/v1/tasks/`... → `tasks/` (relatif à /api/v1/)."""
    path = (path or "").strip()
    if "?" in path:
        raise ApiCallError("Passer les paramètres de requête dans `query`, pas dans `path`.")
    path = path.lstrip("/")
    if path.startswith("api/v1/"):
        path = path[len("api/v1/") :]
    if not path:
        raise ApiCallError("Chemin vide.")
    if ".." in path.split("/"):
        raise ApiCallError("Chemin invalide.")
    if not path.endswith("/"):
        path += "/"
    return path


def is_denied(relative_path):
    return relative_path.startswith(DENIED_PREFIXES)


def call_api(*, user, method, path, query=None, body=None, outer_request=None):
    """Exécute l'appel et renvoie `(status_code, texte_de_la_réponse)`."""
    method = (method or "").upper()
    if method not in ALLOWED_METHODS:
        raise ApiCallError(f"Méthode non supportée : {method}.")
    relative = normalize_path(path)
    if is_denied(relative):
        raise ApiCallError("Cet endpoint n'est pas accessible depuis le connecteur Claude.")

    full_path = API_PREFIX + relative
    try:
        match = resolve(full_path)
    except Resolver404:
        raise ApiCallError(f"Aucun endpoint ne correspond à {full_path}.")

    url = full_path
    if query:
        url += "?" + urlencode({k: v for k, v in query.items() if v is not None}, doseq=True)

    extra = {}
    if outer_request is not None:
        # Hôte/schéma de la requête MCP d'origine : sans ça, la factory envoie
        # `testserver`, refusé par ALLOWED_HOSTS hors dev dès qu'une vue
        # construit une URL absolue.
        extra["HTTP_HOST"] = outer_request.get_host()
        if outer_request.is_secure():
            extra["wsgi.url_scheme"] = "https"
            extra["HTTP_X_FORWARDED_PROTO"] = "https"

    factory = APIRequestFactory()
    data = json.dumps(body) if body is not None and method != "GET" else None
    request = factory.generic(method, url, data=data or "", content_type="application/json", **extra)
    force_authenticate(request, user=user)

    try:
        response = match.func(request, *match.args, **match.kwargs)
        if hasattr(response, "render"):
            response.render()
    except Exception:
        logger.exception("Appel MCP %s %s en échec", method, full_path)
        return 500, "Erreur interne du serveur Awtodo lors de cet appel."

    return response.status_code, _response_text(response)


def _response_text(response):
    data = getattr(response, "data", None)
    if data is not None:
        text = json.dumps(data, ensure_ascii=False, default=str)
    elif getattr(response, "streaming", False):
        text = b"".join(response.streaming_content).decode("utf-8", errors="replace")
    else:
        text = response.content.decode("utf-8", errors="replace")
    if len(text) > MAX_RESPONSE_CHARS:
        text = (
            text[:MAX_RESPONSE_CHARS]
            + f"\n… [réponse tronquée à {MAX_RESPONSE_CHARS} caractères sur {len(text)} — affiner avec des filtres `query`]"
        )
    return text or "(réponse vide)"
