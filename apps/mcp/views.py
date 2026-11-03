import json

from django.contrib.auth import login
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider.oauth2_backends import get_oauthlib_core

from apps.accounts.services import AccountValidationError, authenticate_user

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
        return render(request, self.template_name, {"next": self._next(request)})

    def post(self, request):
        next_url = self._next(request)
        username = request.POST.get("username", "").strip()
        try:
            user = authenticate_user(username=username, password=request.POST.get("password", ""))
        except AccountValidationError as exc:
            return render(request, self.template_name, {"next": next_url, "error": str(exc), "username": username}, status=400)
        if user.is_service_account:
            return render(request, self.template_name, {"next": next_url, "error": "Identifiants invalides."}, status=400)

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        request.session.set_expiry(LOGIN_SESSION_SECONDS)
        return redirect(next_url)

    @staticmethod
    def _next(request):
        candidate = request.POST.get("next") or request.GET.get("next") or ""
        if candidate and url_has_allowed_host_and_scheme(candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return candidate
        return "/"
