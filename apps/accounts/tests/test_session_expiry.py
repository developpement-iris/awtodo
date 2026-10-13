from django.test import override_settings
from rest_framework.test import APITestCase


class InvalidTokenStatusTests(APITestCase):
    """Le frontend détecte une session expirée sur un 401 (`authFetch`) — un
    jeton refusé ne doit pas répondre 403, réservé aux actions interdites."""

    @override_settings(DEBUG=False)
    def test_invalid_jwt_returns_401(self):
        response = self.client.get("/api/v1/projects/", HTTP_AUTHORIZATION="Bearer abc.def.ghi")
        self.assertEqual(response.status_code, 401)
