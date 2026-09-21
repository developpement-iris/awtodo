"""Session du 2026-09-16 : couper l'accès d'un compte (réversible), et
l'écran Paramètres (mot de passe / préférences de notification)."""

from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Organisation, User
from apps.accounts.services import (
    AccountPermissionError,
    AccountValidationError,
    authenticate_user,
    change_own_password,
    deactivate_account,
    reactivate_account,
    update_notification_preferences,
    update_planning_preferences,
)


class DeactivateAccountTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.other_org = Organisation.objects.create(name="Org B")
        self.admin = User.objects.create_user(username="admin-da", organisation=self.org, organisation_role="admin")
        self.target = User.objects.create_user(username="target-da", organisation=self.org, password="Str0ngPassw0rd!")
        self.plain_member = User.objects.create_user(username="plain-da", organisation=self.org)
        self.foreign_admin = User.objects.create_user(
            username="foreign-admin-da", organisation=self.other_org, organisation_role="admin"
        )

    def test_org_admin_deactivates_account(self):
        updated = deactivate_account(actor=self.admin, target_user=self.target)

        self.assertEqual(updated.account_status, "desactive")
        self.assertFalse(updated.is_active)

    def test_deactivated_account_cannot_authenticate(self):
        deactivate_account(actor=self.admin, target_user=self.target)

        with self.assertRaises(AccountValidationError):
            authenticate_user(username="target-da", password="Str0ngPassw0rd!")

    def test_plain_member_cannot_deactivate(self):
        with self.assertRaises(AccountPermissionError):
            deactivate_account(actor=self.plain_member, target_user=self.target)

    def test_admin_cannot_deactivate_own_account(self):
        with self.assertRaises(AccountValidationError):
            deactivate_account(actor=self.admin, target_user=self.admin)

    def test_admin_from_another_organisation_cannot_deactivate(self):
        with self.assertRaises(AccountPermissionError):
            deactivate_account(actor=self.foreign_admin, target_user=self.target)

    def test_cannot_deactivate_already_deactivated_account(self):
        deactivate_account(actor=self.admin, target_user=self.target)

        with self.assertRaises(AccountValidationError):
            deactivate_account(actor=self.admin, target_user=self.target)

    def test_reactivate_restores_access(self):
        deactivate_account(actor=self.admin, target_user=self.target)

        updated = reactivate_account(actor=self.admin, target_user=self.target)

        self.assertEqual(updated.account_status, "active")
        self.assertTrue(updated.is_active)
        authenticate_user(username="target-da", password="Str0ngPassw0rd!")  # ne lève plus

    def test_cannot_reactivate_account_that_is_not_deactivated(self):
        with self.assertRaises(AccountValidationError):
            reactivate_account(actor=self.admin, target_user=self.target)


@override_settings(
    DEBUG=True,
    REST_FRAMEWORK={
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "apps.accounts.authentication.DebugUserIdAuthentication",
            "rest_framework.authentication.SessionAuthentication",
        ],
    },
)
class DeactivateAccountApiTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.admin = User.objects.create_user(username="admin-daa", organisation=self.org, organisation_role="admin")
        self.target = User.objects.create_user(username="target-daa", organisation=self.org)

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_deactivate_then_reactivate_via_api(self):
        r = self.client.post(f"/api/v1/accounts/users/{self.target.id}/deactivate/", **self.as_user(self.admin))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["account_status"], "desactive")

        r2 = self.client.post(f"/api/v1/accounts/users/{self.target.id}/reactivate/", **self.as_user(self.admin))
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["account_status"], "active")

    def test_non_admin_cannot_deactivate_via_api(self):
        other = User.objects.create_user(username="other-daa", organisation=self.org)
        r = self.client.post(f"/api/v1/accounts/users/{self.target.id}/deactivate/", **self.as_user(other))
        self.assertEqual(r.status_code, 403)


class ChangeOwnPasswordTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.user = User.objects.create_user(username="pwd-user", organisation=self.org, password="OldPassw0rd!")

    def test_change_password_with_correct_current_password(self):
        change_own_password(actor=self.user, current_password="OldPassw0rd!", new_password="NewPassw0rd!2")

        authenticate_user(username="pwd-user", password="NewPassw0rd!2")  # ne lève pas

    def test_wrong_current_password_rejected(self):
        with self.assertRaises(AccountValidationError):
            change_own_password(actor=self.user, current_password="wrong", new_password="NewPassw0rd!2")

    def test_weak_new_password_rejected(self):
        with self.assertRaises(AccountValidationError):
            change_own_password(actor=self.user, current_password="OldPassw0rd!", new_password="123")


@override_settings(
    DEBUG=True,
    REST_FRAMEWORK={
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "apps.accounts.authentication.DebugUserIdAuthentication",
            "rest_framework.authentication.SessionAuthentication",
        ],
    },
)
class SettingsApiTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.user = User.objects.create_user(username="settings-user", organisation=self.org, password="OldPassw0rd!")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_change_password_via_api(self):
        r = self.client.post(
            "/api/v1/accounts/me/change-password/",
            {"current_password": "OldPassw0rd!", "new_password": "NewPassw0rd!2"},
            content_type="application/json",
            **self.as_user(self.user),
        )
        self.assertEqual(r.status_code, 200)

    def test_update_notification_preferences_via_api(self):
        r = self.client.patch(
            "/api/v1/accounts/me/notification-preferences/",
            {"email_notifications_enabled": False},
            content_type="application/json",
            **self.as_user(self.user),
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["email_notifications_enabled"])

    def test_me_endpoint_exposes_notification_preference(self):
        r = self.client.get("/api/v1/accounts/me/", **self.as_user(self.user))
        self.assertEqual(r.status_code, 200)
        self.assertIn("email_notifications_enabled", r.json())

    def test_update_planning_color_via_api(self):
        r = self.client.patch(
            "/api/v1/accounts/me/planning-preferences/",
            {"planning_color": "#2E6363"},
            content_type="application/json",
            **self.as_user(self.user),
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["planning_color"], "#2E6363")

    def test_invalid_planning_color_rejected(self):
        r = self.client.patch(
            "/api/v1/accounts/me/planning-preferences/",
            {"planning_color": "brique"},
            content_type="application/json",
            **self.as_user(self.user),
        )
        self.assertEqual(r.status_code, 400)


class NotificationPreferenceServiceTests(TestCase):
    def test_update_notification_preferences(self):
        org = Organisation.objects.create(name="Org A")
        user = User.objects.create_user(username="pref-user", organisation=org)

        updated = update_notification_preferences(actor=user, email_notifications_enabled=False)

        self.assertFalse(updated.email_notifications_enabled)
        user.refresh_from_db()
        self.assertFalse(user.email_notifications_enabled)


class PlanningPreferenceServiceTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.user = User.objects.create_user(username="planning-user", organisation=self.org)

    def test_update_planning_color(self):
        updated = update_planning_preferences(actor=self.user, planning_color="#7A4F9E")

        self.assertEqual(updated.planning_color, "#7A4F9E")

    def test_reset_planning_color_to_empty(self):
        update_planning_preferences(actor=self.user, planning_color="#7A4F9E")

        updated = update_planning_preferences(actor=self.user, planning_color="")

        self.assertEqual(updated.planning_color, "")

