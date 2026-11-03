"""Briques OAuth 2.1 propres au connecteur Claude, au-dessus de django-oauth-toolkit."""

import json

from django.conf import settings
from oauth2_provider.views import AuthorizationView, DynamicClientRegistrationManagementView


class AllowlistedRedirectDCRPermission:
    """Enregistrement dynamique de client (RFC 7591) ouvert sans compte —
    claude.ai s'enregistre tout seul à l'ajout du connecteur — mais limité aux
    URL de retour de `MCP_OAUTH_ALLOWED_REDIRECT_URIS`.

    Sans cette restriction, n'importe qui pourrait enregistrer un client
    pointant vers son propre site et envoyer un lien d'autorisation à un
    collègue : le code d'autorisation partirait chez lui."""

    def has_permission(self, request):
        try:
            data = json.loads(request.body or b"{}")
        except ValueError:
            return False
        uris = data.get("redirect_uris") if isinstance(data, dict) else None
        if not isinstance(uris, list) or not uris:
            return False
        allowed = set(settings.MCP_OAUTH_ALLOWED_REDIRECT_URIS)
        return all(isinstance(uri, str) and uri in allowed for uri in uris)


class ReadOnlyClientManagementView(DynamicClientRegistrationManagementView):
    """Gestion RFC 7592 d'un client enregistré, sans modification (PUT) :
    elle permettrait de changer les URL de retour après coup, en contournant
    `AllowlistedRedirectDCRPermission`. Consultation et désinscription seules."""

    http_method_names = ["get", "delete", "options"]


class McpAuthorizationView(AuthorizationView):
    """Écran de consentement. Seul ajout : la CSP de la page autorise le
    formulaire à rediriger vers claude.ai — Chrome applique `form-action` aux
    redirections qui suivent un envoi de formulaire, et la CSP globale
    (`apps.common.middleware`) s'arrête à 'self'."""

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        origins = sorted({_origin(uri) for uri in settings.MCP_OAUTH_ALLOWED_REDIRECT_URIS})
        response["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            f"frame-ancestors 'none'; base-uri 'self'; form-action 'self' {' '.join(origins)}"
        )
        return response


def _origin(uri):
    scheme, _, rest = uri.partition("://")
    return f"{scheme}://{rest.split('/', 1)[0]}"
