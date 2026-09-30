from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Organisation, Team, TeamMembership, User
from apps.incidents.services import create_incident, start_incident
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import (
    ProjectPermissionError,
    add_project_member,
    create_project,
    get_project_history,
    get_scoped_history,
)
from apps.tasks.services import create_task, rename_task


class ProjectHistoryServiceTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.chef = User.objects.create_user(username="chef-hist", organisation=self.org)
        self.team = Team.objects.create(name="Équipe", organisation=self.org, created_by=self.chef)
        TeamMembership.objects.create(team=self.team, user=self.chef)
        self.project = create_project(actor=self.chef, name="Projet", project_type="collaboratif", team=self.team)
        self.member = User.objects.create_user(username="member-hist", organisation=self.org)
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def test_task_creation_and_rename_appear_in_project_history(self):
        task = create_task(actor=self.chef, project=self.project, title="Corriger le bug", task_type="correction")
        rename_task(actor=self.chef, task=task, title="Corriger le vrai bug")

        entries = list(get_project_history(actor=self.chef, project=self.project))
        verbs = [e.verb for e in entries]
        self.assertIn("created", verbs)
        self.assertIn("field_changed", verbs)
        self.assertTrue(all(e.project_id == self.project.id for e in entries))

    def test_project_creation_itself_is_logged(self):
        entries = get_project_history(actor=self.chef, project=self.project)
        self.assertTrue(entries.filter(verb="created").exists())

    def test_plain_member_cannot_view_project_history(self):
        with self.assertRaises(ProjectPermissionError):
            get_project_history(actor=self.member, project=self.project)


class ScopedHistoryServiceTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.org_admin = User.objects.create_user(username="org-admin-h", organisation=self.org, organisation_role="admin")
        self.group_admin = User.objects.create_user(username="group-admin-h", organisation=self.org)
        self.chef = User.objects.create_user(username="chef-h", organisation=self.org)
        self.plain_member = User.objects.create_user(username="plain-h", organisation=self.org)

        self.team = Team.objects.create(name="Équipe H", organisation=self.org, created_by=self.group_admin)
        TeamMembership.objects.create(team=self.team, user=self.group_admin)
        TeamMembership.objects.create(team=self.team, user=self.chef)
        TeamMembership.objects.create(team=self.team, user=self.plain_member)

        self.project = create_project(actor=self.chef, name="Projet H", project_type="collaboratif", team=self.team)
        ProjectMembership.objects.create(project=self.project, user=self.plain_member, role="membre")

        # Un 2e projet, hors du groupe ci-dessus, pour vérifier qu'il reste
        # invisible aux scopes plus étroits.
        self.other_team = Team.objects.create(name="Autre équipe", organisation=self.org, created_by=self.org_admin)
        TeamMembership.objects.create(team=self.other_team, user=self.org_admin)
        self.other_chef = User.objects.create_user(username="other-chef-h", organisation=self.org)
        TeamMembership.objects.create(team=self.other_team, user=self.other_chef)
        self.other_project = create_project(
            actor=self.other_chef, name="Projet autre groupe", project_type="collaboratif", team=self.other_team
        )

        self.task = create_task(actor=self.chef, project=self.project, title="Tâche H", task_type="correction")

    def test_org_admin_sees_everything(self):
        entries = get_scoped_history(actor=self.org_admin)
        project_ids = set(entries.values_list("project_id", flat=True))
        self.assertIn(self.project.id, project_ids)
        self.assertIn(self.other_project.id, project_ids)

    def test_group_admin_sees_only_their_group(self):
        entries = get_scoped_history(actor=self.group_admin)
        project_ids = set(entries.values_list("project_id", flat=True))
        self.assertIn(self.project.id, project_ids)
        self.assertNotIn(self.other_project.id, project_ids)

    def test_project_manager_sees_their_project_and_own_actions(self):
        entries = get_scoped_history(actor=self.chef)
        project_ids = set(entries.values_list("project_id", flat=True))
        self.assertIn(self.project.id, project_ids)
        self.assertNotIn(self.other_project.id, project_ids)

    def test_plain_member_sees_only_their_own_actions(self):
        rename_task(actor=self.plain_member, task=self.task, title="Renommée par le membre")

        entries = get_scoped_history(actor=self.plain_member)
        self.assertTrue(entries.filter(actor=self.plain_member).exists())
        # N'a jamais vu la création de la tâche (faite par le chef, pas lui) —
        # seulement ses propres actions, pas tout le projet.
        creation_entries_seen = entries.filter(verb="created", project=self.project)
        self.assertFalse(creation_entries_seen.filter(actor=self.chef).exists())

    def test_incident_without_project_appears_for_group_admin(self):
        incident = create_incident(title="Panne", team=self.team, actor=self.group_admin)
        start_incident(actor=self.group_admin, incident=incident)

        entries = get_scoped_history(actor=self.group_admin)
        content_type_models = set(entries.values_list("content_type__model", flat=True))
        self.assertIn("incident", content_type_models)
        self.assertTrue(entries.filter(team=self.team, project__isnull=True).exists())


@override_settings(
    DEBUG=True,
    REST_FRAMEWORK={
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
        "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.DebugUserIdAuthentication"],
    },
)
class ProjectHistoryApiTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.chef = User.objects.create_user(username="chef-api-h", organisation=self.org)
        self.team = Team.objects.create(name="Équipe API", organisation=self.org, created_by=self.chef)
        TeamMembership.objects.create(team=self.team, user=self.chef)
        self.project = create_project(actor=self.chef, name="Projet API", project_type="collaboratif", team=self.team)
        self.member = User.objects.create_user(username="member-api-h", organisation=self.org)
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def _as(self, user):
        self.client.credentials(HTTP_X_DEBUG_USER_ID=str(user.id))

    def test_manager_can_view_project_history_via_api(self):
        self._as(self.chef)
        r = self.client.get(f"/api/v1/projects/{self.project.id}/history/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any(e["verb"] == "created" for e in r.json()))

    def test_member_cannot_view_project_history_via_api(self):
        self._as(self.member)
        r = self.client.get(f"/api/v1/projects/{self.project.id}/history/")
        self.assertEqual(r.status_code, 403)

    def test_export_returns_csv(self):
        self._as(self.chef)
        r = self.client.get("/api/v1/projects/history/export/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "text/csv")
        content = r.content.decode()
        self.assertIn("Date,Acteur,Type d'entité", content)
        self.assertIn("Projet API", content)
