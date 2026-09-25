from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.plumbing import build_bearer_security_scheme_object
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .services import resolve_api_key

_SCHEME = "Api-Key"


class ApiKeyAuthentication(BaseAuthentication):
    """Authentification machine-à-machine (intégration ticketing, Power
    Automate…) — en-tête `Authorization: Api-Key <clé>`. Contrairement à
    `apps.accounts.authentication.DebugUserIdAuthentication`, reste active en
    production : c'est le mécanisme prévu pour survivre au changement
    d'hébergement (Render → AWS, voir CLAUDE.md) — seule l'URL de base
    change côté système appelant, jamais ce header.

    Résout vers le `service_account` (`User.is_service_account=True`, un par
    organisation) de la clé — `request.user` se comporte alors exactement
    comme le compte de service simulé aujourd'hui via `X-Debug-User-Id` en
    dev (voir `IncidentViewSet.create`), sans changement nécessaire ailleurs
    dans le code."""

    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith(f"{_SCHEME} "):
            return None
        raw_key = header[len(_SCHEME) + 1 :].strip()
        if not raw_key:
            return None

        api_key = resolve_api_key(raw_key)
        if api_key is None:
            raise AuthenticationFailed("Clé API invalide ou révoquée.")
        return (api_key.service_account, None)

    def authenticate_header(self, request):
        # Sans ça, DRF renvoie 403 (« pas de credentials fournies ») plutôt
        # que 401 (« credentials fournies mais invalides ») pour une clé
        # inconnue/révoquée — même convention que `TokenAuthentication`.
        return _SCHEME


class ApiKeyScheme(OpenApiAuthenticationExtension):
    """Fait apparaître le schéma `Authorization: Api-Key <clé>` dans le
    Swagger généré (`/api/schema/swagger-ui/`) — sans ça, drf-spectacular
    ignore silencieusement `ApiKeyAuthentication` (aucun
    `OpenApiAuthenticationExtension` enregistré par défaut pour une classe
    maison) et les tiers qui lisent la doc pour s'intégrer (ticketing, Power
    Automate — voir CLAUDE.md > Stack technique) ne verraient jamais que ce
    moyen d'authentification existe."""

    target_class = "apps.integrations.authentication.ApiKeyAuthentication"
    name = "apiKeyAuth"

    def get_security_definition(self, auto_schema):
        return build_bearer_security_scheme_object(header_name="Authorization", token_prefix=_SCHEME)
