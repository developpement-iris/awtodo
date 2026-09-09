from django.test import RequestFactory, TestCase, override_settings

from apps.accounts.authentication import DebugUserIdAuthentication
from apps.accounts.models import User


class DebugUserIdAuthenticationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice")
        self.factory = RequestFactory()

    @override_settings(DEBUG=True)
    def test_header_identifies_user_when_debug_true(self):
        request = self.factory.get("/", HTTP_X_DEBUG_USER_ID=str(self.user.id))

        result = DebugUserIdAuthentication().authenticate(request)

        self.assertIsNotNone(result)
        self.assertEqual(result[0], self.user)

    @override_settings(DEBUG=True)
    def test_missing_header_returns_none_when_debug_true(self):
        request = self.factory.get("/")

        result = DebugUserIdAuthentication().authenticate(request)

        self.assertIsNone(result)

    @override_settings(DEBUG=True)
    def test_unknown_user_id_returns_none_when_debug_true(self):
        request = self.factory.get("/", HTTP_X_DEBUG_USER_ID="not-a-real-uuid")

        result = DebugUserIdAuthentication().authenticate(request)

        self.assertIsNone(result)

    @override_settings(DEBUG=False)
    def test_header_is_ignored_when_debug_false(self):
        request = self.factory.get("/", HTTP_X_DEBUG_USER_ID=str(self.user.id))

        result = DebugUserIdAuthentication().authenticate(request)

        self.assertIsNone(result)
