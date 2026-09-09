from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User


class BootstrapAdminCommandTests(TestCase):
    def _run(self, **env):
        out = StringIO()
        with mock.patch.dict("os.environ", env, clear=False):
            call_command("bootstrap_admin", stdout=out)
        return out.getvalue()

    def test_noop_without_env(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            call_command("bootstrap_admin", stdout=StringIO())
        self.assertFalse(User.objects.filter(is_platform_admin=True).exists())

    def test_creates_promoted_active_superuser(self):
        self._run(
            ADMIN_USERNAME="boss",
            ADMIN_EMAIL="boss@example.com",
            ADMIN_PASSWORD="Str0ng-pass-42",
        )
        user = User.objects.get(username="boss")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_platform_admin)
        self.assertEqual(user.organisation_role, "admin")
        self.assertEqual(user.account_status, "active")
        self.assertIsNotNone(user.organisation_id)
        self.assertTrue(user.check_password("Str0ng-pass-42"))

    def test_rerun_keeps_password_unless_forced(self):
        self._run(ADMIN_USERNAME="boss", ADMIN_PASSWORD="first-pass-11")
        User.objects.filter(username="boss").update(organisation_role="membre")

        self._run(ADMIN_USERNAME="boss", ADMIN_PASSWORD="other-pass-22")
        user = User.objects.get(username="boss")
        self.assertTrue(user.check_password("first-pass-11"))
        self.assertEqual(user.organisation_role, "admin")

        self._run(
            ADMIN_USERNAME="boss",
            ADMIN_PASSWORD="other-pass-22",
            ADMIN_FORCE_PASSWORD="1",
        )
        self.assertTrue(User.objects.get(username="boss").check_password("other-pass-22"))
