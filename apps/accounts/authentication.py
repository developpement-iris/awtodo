from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.authentication import BaseAuthentication

from .models import User


class DebugUserIdAuthentication(BaseAuthentication):
    """Identification factice via en-tête, en attendant le SSO réel (voir CLAUDE.md).
    Volontairement inerte dès que DEBUG=False, y compris si l'en-tête est présent."""

    def authenticate(self, request):
        if not settings.DEBUG:
            return None

        user_id = request.headers.get("X-Debug-User-Id")
        if not user_id:
            return None

        try:
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError, ValidationError):
            return None

        return (user, None)

    def authenticate_header(self, request):
        # DRF ne lit cet en-tête que sur la PREMIÈRE classe d'authentification
        # de la liste (celle-ci) : sans lui, un jeton JWT expiré/invalide
        # répondait 403 au lieu de 401, et le frontend ne pouvait pas
        # distinguer "session expirée" de "action interdite" (session du
        # 2026-10-09). Même valeur que `JWTAuthentication`.
        return 'Bearer realm="api"'
