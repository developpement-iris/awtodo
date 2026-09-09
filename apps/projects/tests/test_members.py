from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Organisation, Team, TeamMembership, User
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import (
    ProjectPermissionError,
    ProjectValidationError,
    add_project_member,
    change_project_member_role,
    create_project,
    remove_project_member,
)


class AddProjectMemberTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.other_org = Organisation.objects.create(name="Org B")
        self.chef = User.objects.create_user(username="chef1", organisation=self.org)
        self.team = Team.objects.create(name="Équipe X", organisation=self.org, created_by=self.chef)
        TeamMembership.objects.create(team=self.team, user=self.chef)
        self.project = create_project(actor=self.chef, name="Projet", project_type="collaboratif", team=self.team)

        self.team_member = User.objects.create_user(username="teammate1", organisation=self.org)
        TeamMembership.objects.create(team=self.team, user=self.team_member)

        self.org_outsider = User.objects.create_user(
            username="orgoutsider1", organisation=self.org, email="orgoutsider1@example.com"
        )
        self.foreign_user = User.objects.create_user(username="foreign1", organisation=self.other_org)
        self.non_manager_member = User.objects.create_user(username="plainmember1", organisation=self.org)
        ProjectMembership.objects.create(project=self.project, user=self.non_manager_member, role="membre")

    def test_manager_adds_team_member_by_id(self):
        membership = add_project_member(actor=self.chef, project=self.project, user=self.team_member)

        self.assertEqual(membership.role, "membre")
        self.assertTrue(ProjectMembership.objects.filter(project=self.project, user=self.team_member).exists())

    def test_manager_adds_org_member_by_email_outside_team(self):
        membership = add_project_member(actor=self.chef, project=self.project, email="orgoutsider1@example.com")

        self.assertEqual(membership.user, self.org_outsider)

    def test_email_not_found_in_organisation_is_rejected(self):
        with self.assertRaises(ProjectValidationError):
            add_project_member(actor=self.chef, project=self.project, email="nobody@example.com")

    def test_cannot_add_user_from_other_organisation_by_id(self):
        with self.assertRaises(ProjectValidationError):
            add_project_member(actor=self.chef, project=self.project, user=self.foreign_user)

    def test_non_manager_cannot_add_member(self):
        with self.assertRaises(ProjectPermissionError):
            add_project_member(actor=self.non_manager_member, project=self.project, user=self.team_member)


class ProjectMemberRoleAndRemovalTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.chef = User.objects.create_user(username="chef2", organisation=self.org)
        self.project = create_project(actor=self.chef, name="Projet solo", project_type="individuel")
        self.member = User.objects.create_user(username="member2", organisation=self.org)
        self.member_membership = ProjectMembership.objects.create(
            project=self.project, user=self.member, role="membre"
        )

    def test_manager_promotes_member(self):
        updated = change_project_member_role(actor=self.chef, membership=self.member_membership, role="chef_de_projet")

        self.assertEqual(updated.role, "chef_de_projet")

    def test_manager_removes_member(self):
        remove_project_member(actor=self.chef, membership=self.member_membership)

        self.assertFalse(ProjectMembership.objects.filter(pk=self.member_membership.pk).exists())
        self.assertTrue(ProjectMembership.all_objects.filter(pk=self.member_membership.pk, status="removed").exists())

    def test_cannot_demote_last_manager(self):
        chef_membership = ProjectMembership.objects.get(project=self.project, user=self.chef)

        with self.assertRaises(ProjectValidationError):
            change_project_member_role(actor=self.chef, membership=chef_membership, role="membre")

    def test_cannot_remove_last_manager(self):
        chef_membership = ProjectMembership.objects.get(project=self.project, user=self.chef)

        with self.assertRaises(ProjectValidationError):
            remove_project_member(actor=self.chef, membership=chef_membership)

    def test_can_demote_manager_when_another_manager_exists(self):
        chef_membership = ProjectMembership.objects.get(project=self.project, user=self.chef)
        change_project_member_role(actor=self.chef, membership=self.member_membership, role="chef_de_projet")

        updated = change_project_member_role(actor=self.chef, membership=chef_membership, role="membre")

        self.assertEqual(updated.role, "membre")

    def test_non_manager_cannot_change_role(self):
        with self.assertRaises(ProjectPermissionError):
            change_project_member_role(actor=self.member, membership=self.member_membership, role="chef_de_projet")


class CreateProjectWithMembersTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.chef = User.objects.create_user(username="chef3", organisation=self.org)
        self.team = Team.objects.create(name="Équipe Y", organisation=self.org, created_by=self.chef)
        TeamMembership.objects.create(team=self.team, user=self.chef)
        self.teammate = User.objects.create_user(username="teammate2", organisation=self.org)
        TeamMembership.objects.create(team=self.team, user=self.teammate)
        self.outsider = User.objects.create_user(username="outsider2", organisation=self.org)

    def test_selected_team_members_are_added_at_creation(self):
        project = create_project(
            actor=self.chef,
            name="Projet collab",
            project_type="collaboratif",
            team=self.team,
            member_ids=[self.teammate],
        )

        self.assertTrue(ProjectMembership.objects.filter(project=project, user=self.teammate, role="membre").exists())

    def test_non_team_member_selection_is_rejected(self):
        with self.assertRaises(ProjectValidationError):
            create_project(
                actor=self.chef,
                name="Projet collab 2",
                project_type="collaboratif",
                team=self.team,
                member_ids=[self.outsider],
            )

    def test_member_selection_rejected_for_individual_project(self):
        with self.assertRaises(ProjectValidationError):
            create_project(
                actor=self.chef,
                name="Projet solo",
                project_type="individuel",
                member_ids=[self.teammate],
            )


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
class ProjectMemberApiTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.chef = User.objects.create_user(username="chef4", organisation=self.org)
        self.project = create_project(actor=self.chef, name="Projet API", project_type="individuel")
        self.candidate = User.objects.create_user(
            username="candidate2", organisation=self.org, email="candidate2@example.com"
        )

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_add_member_via_api(self):
        response = self.client.post(
            f"/api/v1/projects/{self.project.id}/members/",
            {"email": "candidate2@example.com"},
            content_type="application/json",
            **self.as_user(self.chef),
        )

        self.assertEqual(response.status_code, 201)
        members = response.json()["members"]
        candidate_membership = next(m for m in members if m["user"]["username"] == "candidate2")
        self.assertEqual(candidate_membership["role"], "membre")

    def test_change_role_and_remove_via_api(self):
        add_response = self.client.post(
            f"/api/v1/projects/{self.project.id}/members/",
            {"email": "candidate2@example.com"},
            content_type="application/json",
            **self.as_user(self.chef),
        )
        members = add_response.json()["members"]
        membership_id = next(m for m in members if m["user"]["username"] == "candidate2")["id"]

        role_response = self.client.post(
            f"/api/v1/projects/{self.project.id}/members/role/",
            {"membership": membership_id, "role": "chef_de_projet"},
            content_type="application/json",
            **self.as_user(self.chef),
        )
        self.assertEqual(role_response.status_code, 200)
        updated_membership = next(m for m in role_response.json()["members"] if m["id"] == membership_id)
        self.assertEqual(updated_membership["role"], "chef_de_projet")

        remove_response = self.client.post(
            f"/api/v1/projects/{self.project.id}/members/remove/",
            {"membership": membership_id},
            content_type="application/json",
            **self.as_user(self.chef),
        )
        self.assertEqual(remove_response.status_code, 200)
        remaining_ids = [m["id"] for m in remove_response.json()["members"]]
        self.assertNotIn(membership_id, remaining_ids)

    def test_project_payload_includes_members(self):
        response = self.client.get(f"/api/v1/projects/{self.project.id}/", **self.as_user(self.chef))

        self.assertEqual(response.status_code, 200)
        usernames = [m["user"]["username"] for m in response.json()["members"]]
        self.assertIn("chef4", usernames)
