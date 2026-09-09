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
