import json
import secrets
from urllib.parse import urlencode

from django.contrib.auth import login
from django.core import signing
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.crypto import constant_time_compare
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider.oauth2_backends import get_oauthlib_core

from apps.accounts.services import AccountValidationError, authenticate_user, login_with_microsoft
from apps.accounts.sso import AUTHORITY, MicrosoftTokenError, sso_config, verify_microsoft_id_token

from .protocol import PARSE_ERROR, error_response, handle_message

MCP_SCOPE = "mcp"

# Session Django ouverte par la page de connexion OAuth : ne sert qu'à
# enchaîner sur l'écran de consentement, inutile de la garder ouverte.
LOGIN_SESSION_SECONDS = 15 * 60


@method_decorator(csrf_exempt, name="dispatch")
class McpView(View):
    """Endpoint MCP (`POST /mcp`), protégé par un jeton OAuth émis par
    django-oauth-toolkit. Pas de flux SSE (GET) : toutes les réponses sont du
    JSON direct."""

    http_method_names = ["post", "get", "delete", "options"]

    def post(self, request):
        user, challenge = _authenticate(request)
        if user is None:
            return challenge

        try:
            payload = json.loads(request.body or b"")
        except ValueError:
            return JsonResponse(error_response(None, PARSE_ERROR, "JSON invalide."), status=400)

        if isinstance(payload, list):
            responses = [r for r in (handle_message(m, user=user, request=request) for m in payload) if r is not None]
            if not responses:
                return HttpResponse(status=202)
            return JsonResponse(responses, safe=False)

        response = handle_message(payload, user=user, request=request)
        if response is None:
            return HttpResponse(status=202)
        return JsonResponse(response)

    def get(self, request):
        return HttpResponse(status=405, headers={"Allow": "POST"})

    def delete(self, request):
        return HttpResponse(status=405, headers={"Allow": "POST"})


def _authenticate(request):
    """`(user, None)` si le jeton est valide, sinon `(None, réponse 401)`."""
    valid, oauth_request = get_oauthlib_core().verify_request(request, scopes=[MCP_SCOPE])
    user = getattr(oauth_request, "user", None) if valid else None
    if user is not None and user.is_active and user.account_status == "active" and not user.is_service_account:
        return user, None

    metadata_url = request.build_absolute_uri("/.well-known/oauth-protected-resource/mcp")
    challenge = f'Bearer resource_metadata="{metadata_url}", scope="{MCP_SCOPE}"'
    if request.headers.get("Authorization"):
        challenge += ', error="invalid_token"'
    response = JsonResponse({"error": "Authentification requise."}, status=401)
    response["WWW-Authenticate"] = challenge
    return None, response


class McpLoginView(View):
    """Connexion par identifiant/mot de passe Awtodo, étape du parcours OAuth
    (avant l'écran de consentement). Page servie par Django, pas par le
    frontend React : le frontend s'authentifie par JWT, alors que l'écran
    d'autorisation de django-oauth-toolkit attend une session Django."""

    template_name = "mcp/login.html"

    def get(self, request):
        return _render_login(request, next_url=_safe_next(request))

    def post(self, request):
        next_url = _safe_next(request)
        username = request.POST.get("username", "").strip()
        try:
            user = authenticate_user(username=username, password=request.POST.get("password", ""))
        except AccountValidationError as exc:
            return _render_login(request, next_url=next_url, error=str(exc), username=username)
        if user.is_service_account:
            return _render_login(request, next_url=next_url, error="Identifiants invalides.")
        return _open_session(request, user, next_url)


def _safe_next(request, candidate=None):
    if candidate is None:
        candidate = request.POST.get("next") or request.GET.get("next") or ""
    if candidate and url_has_allowed_host_and_scheme(candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return candidate
    return "/"


def _render_login(request, *, next_url, error=None, username=""):
    context = {
        "next": next_url,
        "error": error,
        "username": username,
        "microsoft_enabled": sso_config()["enabled"],
        "microsoft_url": f"{reverse('oauth2_provider:mcp-sso-microsoft')}?{urlencode({'next': next_url})}",
    }
    return render(request, McpLoginView.template_name, context, status=400 if error else 200)


def _open_session(request, user, next_url):
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.set_expiry(LOGIN_SESSION_SECONDS)
    return redirect(next_url)


# Connexion Microsoft sur la page OAuth du connecteur (session du 2026-11-20).
# Flux `id_token` + `form_post` contre l'application Entra du SSO (plateforme
# Web, « Jetons d'ID » cochée) : aucun secret. Microsoft renvoie le jeton par
# un POST venu de son domaine, sans le cookie de session (SameSite=Lax) : l'état
# (page de retour + nonce) voyage donc signé dans `state`, et un cookie
# SameSite=None lie le parcours au navigateur qui l'a lancé.
SSO_STATE_SALT = "apps.mcp.sso"
SSO_STATE_MAX_AGE = 10 * 60
SSO_NONCE_COOKIE = "mcp_sso_nonce"


class McpMicrosoftStartView(View):
    """`GET /o/sso/microsoft/` : redirige vers la page de connexion Microsoft."""

    def get(self, request):
        config = sso_config()
        next_url = _safe_next(request)
        if not config["enabled"]:
            return _render_login(request, next_url=next_url, error="La connexion Microsoft n'est pas configurée.")

        nonce = secrets.token_urlsafe(24)
        params = {
            "client_id": config["client_id"],
            "response_type": "id_token",
            "response_mode": "form_post",
            "redirect_uri": request.build_absolute_uri(reverse("oauth2_provider:mcp-sso-microsoft-callback")),
            "scope": "openid profile email",
            "state": signing.dumps({"next": next_url, "nonce": nonce}, salt=SSO_STATE_SALT),
            "nonce": nonce,
        }
        response = redirect(f"{AUTHORITY}/{config['tenant_id']}/oauth2/v2.0/authorize?{urlencode(params)}")
        secure = request.is_secure()
        response.set_cookie(
            SSO_NONCE_COOKIE,
            nonce,
            max_age=SSO_STATE_MAX_AGE,
            httponly=True,
            secure=secure,
            samesite="None" if secure else "Lax",
        )
        return response


@method_decorator(csrf_exempt, name="dispatch")
class McpMicrosoftCallbackView(View):
    """`POST /o/sso/microsoft/callback/` : reçoit le jeton d'identité, ouvre la
    session Django et reprend le parcours OAuth (écran de consentement)."""

    http_method_names = ["post"]

    def post(self, request):
        try:
            state = signing.loads(request.POST.get("state", ""), salt=SSO_STATE_SALT, max_age=SSO_STATE_MAX_AGE)
        except signing.BadSignature:
            return _render_login(request, next_url="/", error="Connexion Microsoft expirée ou invalide, recommencez.")
        next_url = _safe_next(request, state.get("next", ""))

        if request.POST.get("error"):
            return self._fail(request, next_url, "Connexion Microsoft annulée ou refusée.")

        nonce = state.get("nonce", "")
        if not constant_time_compare(request.COOKIES.get(SSO_NONCE_COOKIE, ""), nonce):
            return self._fail(request, next_url, "Connexion Microsoft expirée ou invalide, recommencez.")

        try:
            claims = verify_microsoft_id_token(request.POST.get("id_token", ""))
            if not constant_time_compare(claims.get("nonce", ""), nonce):
                raise MicrosoftTokenError("Jeton Microsoft invalide.")
            user = login_with_microsoft(claims)
        except (MicrosoftTokenError, AccountValidationError) as exc:
            return self._fail(request, next_url, str(exc))
        if user.is_service_account:
            return self._fail(request, next_url, "Ce compte ne peut pas se connecter.")

        response = _open_session(request, user, next_url)
        response.delete_cookie(SSO_NONCE_COOKIE)
        return response

    @staticmethod
    def _fail(request, next_url, error):
        response = _render_login(request, next_url=next_url, error=error)
        response.delete_cookie(SSO_NONCE_COOKIE)
        return response
