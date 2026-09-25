from django.test import RequestFactory, TestCase

from apps.accounts.models import Organisation, User
from apps.integrations.authentication import ApiKeyAuthentication
from apps.integrations.services import generate_api_key, revoke_api_key


class ApiKeyAuthenticationTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org")
        self.admin = User.objects.create(username="admin", organisation=self.org, organisation_role="admin")
        self.factory = RequestFactory()
        self.auth = ApiKeyAuthentication()

    def _request(self, header_value=None):
        headers = {"HTTP_AUTHORIZATION": header_value} if header_value else {}
        return self.factory.get("/api/v1/incidents/", **headers)

    def test_no_header_returns_none(self):
        self.assertIsNone(self.auth.authenticate(self._request()))

    def test_wrong_scheme_returns_none(self):
        self.assertIsNone(self.auth.authenticate(self._request("Bearer sometoken")))

    def test_valid_key_authenticates_as_service_account(self):
        api_key, raw_key = generate_api_key(actor=self.admin, organisation=self.org, name="GLPI")
        result = self.auth.authenticate(self._request(f"Api-Key {raw_key}"))
        self.assertIsNotNone(result)
        user, _ = result
        self.assertEqual(user.id, api_key.service_account_id)
        self.assertTrue(user.is_service_account)

    def test_unknown_key_raises(self):
        from rest_framework.exceptions import AuthenticationFailed

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(self._request("Api-Key awt_not-a-real-key"))

    def test_revoked_key_raises(self):
        from rest_framework.exceptions import AuthenticationFailed

        api_key, raw_key = generate_api_key(actor=self.admin, organisation=self.org, name="GLPI")
        revoke_api_key(actor=self.admin, api_key=api_key)
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(self._request(f"Api-Key {raw_key}"))
