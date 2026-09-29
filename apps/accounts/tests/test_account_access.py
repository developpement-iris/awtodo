"""Session du 2026-09-16 : couper l'accès d'un compte (réversible), et
l'écran Paramètres (mot de passe / préférences de notification)."""

from django.dispatch import Signal
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Organisation, PermissionProfile, Team, User
from apps.accounts.services import (
    AccountPermissionError,
    AccountValidationError,
    add_team_member,
    archive_permission_profile,
    assign_permission_profile,
    authenticate_user,
    change_own_password,
    create_invitation,
    create_permission_profile,
    create_team,
    deactivate_account,
    has_capability,
    is_organisation_admin,
    reactivate_account,
    rename_team,
    resend_invitation,
    unassign_permission_profile,
    update_notification_preferences,
    update_organisation_branding,
    update_planning_preferences,
)
from apps.accounts.signals import outlook_calendar_sync_enabled_activated


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
class PermissionProfileApiTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.admin = User.objects.create_user(username="admin-ppa", organisation=self.org, organisation_role="admin")
        self.member = User.objects.create_user(username="member-ppa", organisation=self.org)

    def _as(self, user):
        self.client.credentials(HTTP_X_DEBUG_USER_ID=str(user.id))

    def test_admin_creates_lists_and_assigns_profile(self):
        self._as(self.admin)
        r = self.client.post(
            "/api/v1/accounts/permission-profiles/",
            {"name": "Intégrateur", "capabilities": ["manage_integrations"]},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        profile_id = r.json()["id"]

        self._as(self.member)
        r_list = self.client.get("/api/v1/accounts/permission-profiles/")
        self.assertEqual(r_list.status_code, 200)
        self.assertEqual(len(r_list.json()), 1)

        self._as(self.admin)
        r_assign = self.client.post(
            f"/api/v1/accounts/permission-profiles/{profile_id}/assign/",
            {"user_id": str(self.member.id)},
            format="json",
        )
        self.assertEqual(r_assign.status_code, 200)
        self.assertEqual([u["id"] for u in r_assign.json()["assigned_users"]], [str(self.member.id)])

    def test_non_admin_cannot_create_profile_via_api(self):
        self._as(self.member)
        r = self.client.post(
            "/api/v1/accounts/permission-profiles/",
            {"name": "X", "capabilities": []},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_archive_profile_via_api(self):
        profile = PermissionProfile.objects.create(organisation=self.org, name="X", capabilities=[])
        self._as(self.admin)
        r = self.client.delete(f"/api/v1/accounts/permission-profiles/{profile.id}/")
        self.assertEqual(r.status_code, 204)
        profile.refresh_from_db()
        self.assertEqual(profile.status, "archived")


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


class OrganisationBrandingServiceTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.admin = User.objects.create_user(username="org-admin", organisation=self.org, organisation_role="admin")
        self.member = User.objects.create_user(username="org-member", organisation=self.org)

    def test_admin_sets_branding_colors(self):
        updated = update_organisation_branding(actor=self.admin, organisation=self.org, primary_color="#7A4F9E", secondary_color="#123456")

        self.assertEqual(updated.brand_primary_color, "#7A4F9E")
        self.assertEqual(updated.brand_secondary_color, "#123456")
        self.org.refresh_from_db()
        self.assertEqual(self.org.brand_primary_color, "#7A4F9E")

    def test_empty_string_resets_a_field_to_default(self):
        update_organisation_branding(actor=self.admin, organisation=self.org, primary_color="#7A4F9E")

        updated = update_organisation_branding(actor=self.admin, organisation=self.org, primary_color="")

        self.assertEqual(updated.brand_primary_color, "")

    def test_non_admin_cannot_set_branding(self):
        with self.assertRaises(AccountPermissionError):
            update_organisation_branding(actor=self.member, organisation=self.org, primary_color="#7A4F9E")


class PermissionProfileServiceTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.admin = User.objects.create_user(username="org-admin", organisation=self.org, organisation_role="admin")
        self.member = User.objects.create_user(username="org-member", organisation=self.org)
        self.other_org = Organisation.objects.create(name="Org B")
        self.outsider = User.objects.create_user(username="outsider", organisation=self.other_org)

    def test_admin_creates_profile_and_grants_capability(self):
        profile = create_permission_profile(
            actor=self.admin, organisation=self.org, name="Intégrateur", capabilities=["manage_integrations"]
        )
        self.assertFalse(has_capability(self.member, "manage_integrations"))

        assign_permission_profile(actor=self.admin, profile=profile, target_user=self.member)

        self.assertTrue(has_capability(self.member, "manage_integrations"))
        # N'accorde QUE cette capacité précise, jamais un statut admin complet.
        self.assertFalse(has_capability(self.member, "manage_members"))
        self.assertFalse(is_organisation_admin(self.member, self.org))

    def test_non_admin_cannot_create_profile(self):
        with self.assertRaises(AccountPermissionError):
            create_permission_profile(actor=self.member, organisation=self.org, name="X", capabilities=[])

    def test_rejects_unknown_capability(self):
        with self.assertRaises(AccountValidationError):
            create_permission_profile(actor=self.admin, organisation=self.org, name="X", capabilities=["devenir_dieu"])

    def test_archived_profile_no_longer_grants_capability(self):
        profile = create_permission_profile(
            actor=self.admin, organisation=self.org, name="Intégrateur", capabilities=["manage_integrations"]
        )
        assign_permission_profile(actor=self.admin, profile=profile, target_user=self.member)
        self.assertTrue(has_capability(self.member, "manage_integrations"))

        archive_permission_profile(actor=self.admin, profile=profile)

        self.assertFalse(has_capability(self.member, "manage_integrations"))

    def test_unassign_removes_capability(self):
        profile = create_permission_profile(
            actor=self.admin, organisation=self.org, name="Intégrateur", capabilities=["manage_integrations"]
        )
        assign_permission_profile(actor=self.admin, profile=profile, target_user=self.member)
        unassign_permission_profile(actor=self.admin, profile=profile, target_user=self.member)

        self.assertFalse(has_capability(self.member, "manage_integrations"))

    def test_cannot_assign_to_user_from_another_organisation(self):
        profile = create_permission_profile(
            actor=self.admin, organisation=self.org, name="Intégrateur", capabilities=["manage_integrations"]
        )
        with self.assertRaises(AccountValidationError):
            assign_permission_profile(actor=self.admin, profile=profile, target_user=self.outsider)

    def test_platform_admin_always_has_every_capability(self):
        platform_admin = User.objects.create_user(
            username="platform-admin", organisation=self.org, is_platform_admin=True
        )
        self.assertTrue(has_capability(platform_admin, "manage_integrations"))
        self.assertTrue(has_capability(platform_admin, "manage_members"))
        self.assertTrue(has_capability(platform_admin, "manage_branding"))

    def test_capability_grants_deactivate_account_without_org_admin_role(self):
        profile = create_permission_profile(
            actor=self.admin, organisation=self.org, name="RH", capabilities=["manage_members"]
        )
        assign_permission_profile(actor=self.admin, profile=profile, target_user=self.member)
        target = User.objects.create_user(username="to-deactivate", organisation=self.org)

        updated = deactivate_account(actor=self.member, target_user=target)

        self.assertEqual(updated.account_status, "desactive")

    def test_manage_groups_capability_allows_team_management(self):
        profile = create_permission_profile(
            actor=self.admin, organisation=self.org, name="RH", capabilities=["manage_groups"]
        )
        assign_permission_profile(actor=self.admin, profile=profile, target_user=self.member)

        team = create_team(actor=self.member, name="Support")
        self.assertEqual(team.created_by, self.member)

        renamed = rename_team(actor=self.member, team=team, name="Support N2")
        self.assertEqual(renamed.name, "Support N2")

        other = User.objects.create_user(username="to-add", organisation=self.org)
        add_team_member(actor=self.member, team=team, user=other)
        self.assertTrue(team.memberships.filter(user=other, status="active").exists())

    def test_manage_invitations_capability_allows_invite_to_any_team(self):
        profile = create_permission_profile(
            actor=self.admin, organisation=self.org, name="RH", capabilities=["manage_invitations"]
        )
        assign_permission_profile(actor=self.admin, profile=profile, target_user=self.member)
        someone_elses_team = Team.objects.create(name="Autre groupe", organisation=self.org, created_by=self.admin)

        invitation = create_invitation(actor=self.member, email="new@example.com", team=someone_elses_team)

        self.assertEqual(invitation.status, "pending")

    def test_manage_invitations_capability_allows_resend(self):
        profile = create_permission_profile(
            actor=self.admin, organisation=self.org, name="RH", capabilities=["manage_invitations"]
        )
        assign_permission_profile(actor=self.admin, profile=profile, target_user=self.member)
        invitation = create_invitation(actor=self.admin, email="resend@example.com")

        resent = resend_invitation(actor=self.member, invitation=invitation)

        self.assertEqual(resent.status, "pending")


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

    def test_update_outlook_calendar_sync_enabled(self):
        self.assertFalse(self.user.outlook_calendar_sync_enabled)

        updated = update_planning_preferences(actor=self.user, outlook_calendar_sync_enabled=True)

        self.assertTrue(updated.outlook_calendar_sync_enabled)

    def test_planning_color_and_outlook_sync_updated_independently(self):
        update_planning_preferences(actor=self.user, planning_color="#7A4F9E")

        updated = update_planning_preferences(actor=self.user, outlook_calendar_sync_enabled=True)

        self.assertEqual(updated.planning_color, "#7A4F9E")
        self.assertTrue(updated.outlook_calendar_sync_enabled)

    def test_activating_outlook_sync_emits_signal_once(self):
        catcher = _Catcher(outlook_calendar_sync_enabled_activated)
        try:
            update_planning_preferences(actor=self.user, outlook_calendar_sync_enabled=True)
            self.assertEqual(len(catcher.received), 1)
            self.assertEqual(catcher.received[0]["user"], self.user)
        finally:
            catcher.disconnect()

    def test_reactivating_outlook_sync_does_not_re_emit_signal(self):
        update_planning_preferences(actor=self.user, outlook_calendar_sync_enabled=True)
        catcher = _Catcher(outlook_calendar_sync_enabled_activated)
        try:
            update_planning_preferences(actor=self.user, outlook_calendar_sync_enabled=True)
            self.assertEqual(len(catcher.received), 0)
        finally:
            catcher.disconnect()

    def test_toggling_outlook_sync_off_does_not_emit_signal(self):
        update_planning_preferences(actor=self.user, outlook_calendar_sync_enabled=True)
        catcher = _Catcher(outlook_calendar_sync_enabled_activated)
        try:
            update_planning_preferences(actor=self.user, outlook_calendar_sync_enabled=False)
            self.assertEqual(len(catcher.received), 0)
        finally:
            catcher.disconnect()


class _Catcher:
    def __init__(self, signal: Signal):
        self.signal = signal
        self.received = []
        signal.connect(self._handler, weak=False)

    def _handler(self, sender, **kwargs):
        self.received.append(kwargs)

    def disconnect(self):
        self.signal.disconnect(self._handler)

