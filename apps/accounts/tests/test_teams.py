from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Organisation, Team, TeamMembership, User
from apps.accounts.services import (
    AccountPermissionError,
    AccountValidationError,
    add_team_member,
    can_manage_team,
    create_team,
    remove_team_member,
    rename_team,
)


class CreateTeamTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.admin = User.objects.create_user(username="admin1", organisation=self.org, organisation_role="admin")
        self.chef = User.objects.create_user(
            username="chef1", organisation=self.org, organisation_role="chef_de_projet"
        )
        self.member = User.objects.create_user(username="member1", organisation=self.org, organisation_role="membre")

    def test_admin_creates_team_and_becomes_member(self):
        team = create_team(actor=self.admin, name="Équipe X")

        self.assertEqual(team.created_by, self.admin)
        self.assertEqual(team.organisation, self.org)
        self.assertTrue(TeamMembership.objects.filter(team=team, user=self.admin).exists())

    def test_chef_de_projet_can_create_team(self):
        team = create_team(actor=self.chef, name="Équipe Y")

        self.assertEqual(team.created_by, self.chef)

    def test_plain_member_cannot_create_team(self):
        with self.assertRaises(AccountPermissionError):
            create_team(actor=self.member, name="Équipe Z")


class TeamMembershipServiceTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.other_org = Organisation.objects.create(name="Org B")
        self.creator = User.objects.create_user(
            username="creator1", organisation=self.org, organisation_role="admin"
        )
        self.team = create_team(actor=self.creator, name="Équipe X")
        self.candidate = User.objects.create_user(username="candidate1", organisation=self.org)
        self.outsider = User.objects.create_user(username="outsider1", organisation=self.org)
        self.foreign_user = User.objects.create_user(username="foreign1", organisation=self.other_org)

    def test_creator_adds_member(self):
        add_team_member(actor=self.creator, team=self.team, user=self.candidate)

        self.assertTrue(TeamMembership.objects.filter(team=self.team, user=self.candidate).exists())

    def test_non_creator_cannot_add_member(self):
        with self.assertRaises(AccountPermissionError):
            add_team_member(actor=self.outsider, team=self.team, user=self.candidate)

    def test_cannot_add_member_from_other_organisation(self):
        with self.assertRaises(AccountValidationError):
            add_team_member(actor=self.creator, team=self.team, user=self.foreign_user)

    def test_creator_removes_member(self):
        add_team_member(actor=self.creator, team=self.team, user=self.candidate)

        remove_team_member(actor=self.creator, team=self.team, user=self.candidate)

        self.assertFalse(TeamMembership.objects.filter(team=self.team, user=self.candidate).exists())
        self.assertTrue(TeamMembership.all_objects.filter(team=self.team, user=self.candidate, status="removed").exists())

    def test_removed_member_can_be_re_added(self):
        add_team_member(actor=self.creator, team=self.team, user=self.candidate)
        remove_team_member(actor=self.creator, team=self.team, user=self.candidate)

        add_team_member(actor=self.creator, team=self.team, user=self.candidate)

        self.assertEqual(
            TeamMembership.all_objects.filter(team=self.team, user=self.candidate).count(), 2
        )
        self.assertTrue(TeamMembership.objects.filter(team=self.team, user=self.candidate).exists())

    def test_non_creator_cannot_remove_member(self):
        add_team_member(actor=self.creator, team=self.team, user=self.candidate)

        with self.assertRaises(AccountPermissionError):
            remove_team_member(actor=self.outsider, team=self.team, user=self.candidate)


class TeamManagementOverrideTests(TestCase):
    """"Administrateur du groupe" (session du 2026-08-07) : le créateur, mais
    aussi un admin d'organisation ou de plateforme, même sans être le
    créateur — voir `_is_team_manager` (services.py)."""

    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.creator = User.objects.create_user(
            username="creator2", organisation=self.org, organisation_role="chef_de_projet"
        )
        self.team = create_team(actor=self.creator, name="Équipe Override")
        self.org_admin = User.objects.create_user(
            username="orgadmin1", organisation=self.org, organisation_role="admin"
        )
        self.platform_admin = User.objects.create_user(
            username="platformadmin1", organisation=self.org, is_platform_admin=True
        )
        self.candidate = User.objects.create_user(username="candidate2", organisation=self.org)

    def test_org_admin_can_add_member_without_being_creator(self):
        add_team_member(actor=self.org_admin, team=self.team, user=self.candidate)

        self.assertTrue(TeamMembership.objects.filter(team=self.team, user=self.candidate).exists())

    def test_platform_admin_can_remove_member_without_being_creator(self):
        add_team_member(actor=self.creator, team=self.team, user=self.candidate)

        remove_team_member(actor=self.platform_admin, team=self.team, user=self.candidate)

        self.assertFalse(TeamMembership.objects.filter(team=self.team, user=self.candidate).exists())

    def test_org_admin_can_rename_without_being_creator(self):
        renamed = rename_team(actor=self.org_admin, team=self.team, name="Nouveau nom")

        self.assertEqual(renamed.name, "Nouveau nom")

    def test_creator_can_rename(self):
        renamed = rename_team(actor=self.creator, team=self.team, name="Renommé par créateur")

        self.assertEqual(renamed.name, "Renommé par créateur")

    def test_plain_member_cannot_rename(self):
        with self.assertRaises(AccountPermissionError):
            rename_team(actor=self.candidate, team=self.team, name="Interdit")

    def test_rename_requires_name(self):
        with self.assertRaises(AccountValidationError):
            rename_team(actor=self.creator, team=self.team, name="")

    def test_cannot_rename_to_existing_name(self):
        other_team = create_team(actor=self.creator, name="Équipe Existante")

        with self.assertRaises(AccountValidationError):
            rename_team(actor=self.creator, team=other_team, name="Équipe Override")

    def test_can_manage_team_flag(self):
        self.assertTrue(can_manage_team(self.creator, self.team))
        self.assertTrue(can_manage_team(self.org_admin, self.team))
        self.assertTrue(can_manage_team(self.platform_admin, self.team))
        self.assertFalse(can_manage_team(self.candidate, self.team))
        self.assertFalse(can_manage_team(None, self.team))


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
class TeamApiTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.admin = User.objects.create_user(username="admin2", organisation=self.org, organisation_role="admin")
        self.member = User.objects.create_user(username="member2", organisation=self.org, organisation_role="membre")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_admin_creates_team_via_api(self):
        response = self.client.post(
            "/api/v1/accounts/teams/",
            {"name": "Équipe API"},
            **self.as_user(self.admin),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["created_by"], str(self.admin.id))

    def test_member_cannot_create_team_via_api(self):
        response = self.client.post(
            "/api/v1/accounts/teams/",
            {"name": "Équipe API 2"},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 403)

    def test_creator_adds_and_removes_member_via_api(self):
        create_response = self.client.post(
            "/api/v1/accounts/teams/", {"name": "Équipe API 3"}, **self.as_user(self.admin)
        )
        team_id = create_response.json()["id"]

        add_response = self.client.post(
            f"/api/v1/accounts/teams/{team_id}/members/",
            {"user": str(self.member.id)},
            **self.as_user(self.admin),
        )
        self.assertEqual(add_response.status_code, 201)
        self.assertIn(str(self.member.id), [m["id"] for m in add_response.json()["members"]])

        remove_response = self.client.post(
            f"/api/v1/accounts/teams/{team_id}/members/remove/",
            {"user": str(self.member.id)},
            **self.as_user(self.admin),
        )
        self.assertEqual(remove_response.status_code, 200)
        self.assertNotIn(str(self.member.id), [m["id"] for m in remove_response.json()["members"]])

    def test_team_response_includes_can_manage_flag(self):
        response = self.client.post("/api/v1/accounts/teams/", {"name": "Équipe Flag"}, **self.as_user(self.admin))

        self.assertTrue(response.json()["can_manage"])

    def test_creator_renames_team_via_api(self):
        create_response = self.client.post(
            "/api/v1/accounts/teams/", {"name": "Équipe Origine"}, **self.as_user(self.admin)
        )
        team_id = create_response.json()["id"]

        response = self.client.patch(
            f"/api/v1/accounts/teams/{team_id}/rename/",
            {"name": "Équipe Renommée"},
            content_type="application/json",
            **self.as_user(self.admin),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Équipe Renommée")

    def test_member_cannot_rename_team_via_api(self):
        create_response = self.client.post(
            "/api/v1/accounts/teams/", {"name": "Équipe Origine 2"}, **self.as_user(self.admin)
        )
        team_id = create_response.json()["id"]

        response = self.client.patch(
            f"/api/v1/accounts/teams/{team_id}/rename/",
            {"name": "Tentative"},
            content_type="application/json",
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 403)
