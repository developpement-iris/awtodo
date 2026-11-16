"""Connexion Microsoft (Entra ID), session du 2026-11-16.

Le navigateur obtient un jeton d'identité par MSAL (application SPA, flux
redirection + PKCE, aucun secret) ; ce module en vérifie la signature contre
les clés publiques du tenant, puis l'audience, l'émetteur et le tenant. Seuls
les comptes du tenant configuré passent : une application « un seul tenant »
côté Entra, revérifiée ici.
"""

import jwt
from django.conf import settings

AUTHORITY = "https://login.microsoftonline.com"

_jwks_clients = {}


class MicrosoftTokenError(Exception):
    pass


def sso_config():
    tenant_id = settings.MICROSOFT_SSO_TENANT_ID
    client_id = settings.MICROSOFT_SSO_CLIENT_ID
    enabled = bool(tenant_id and client_id)
    return {
        "enabled": enabled,
        "tenant_id": tenant_id if enabled else "",
        "client_id": client_id if enabled else "",
    }


def _jwks_client(tenant_id):
    """Un client par tenant, gardé en mémoire : PyJWKClient met les clés en
    cache et ne retélécharge le jeu que si un `kid` inconnu se présente
    (rotation des clés Microsoft)."""
    client = _jwks_clients.get(tenant_id)
    if client is None:
        client = jwt.PyJWKClient(f"{AUTHORITY}/{tenant_id}/discovery/v2.0/keys", cache_keys=True, timeout=5)
        _jwks_clients[tenant_id] = client
    return client


def verify_microsoft_id_token(id_token):
    """Renvoie les revendications d'un jeton d'identité valide, sinon lève
    `MicrosoftTokenError`."""
    config = sso_config()
    if not config["enabled"]:
        raise MicrosoftTokenError("La connexion Microsoft n'est pas configurée.")
    tenant_id = config["tenant_id"]
    try:
        signing_key = _jwks_client(tenant_id).get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=config["client_id"],
            issuer=f"{AUTHORITY}/{tenant_id}/v2.0",
            options={"require": ["exp", "iat", "aud", "iss", "oid", "tid"]},
            leeway=60,
        )
    except (jwt.PyJWTError, jwt.PyJWKClientError) as exc:
        raise MicrosoftTokenError("Jeton Microsoft invalide.") from exc
    if claims.get("tid") != tenant_id:
        raise MicrosoftTokenError("Ce compte Microsoft n'appartient pas à l'organisation.")
    return claims
