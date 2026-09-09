from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Organisation, User
from apps.projects.models import Project, ProjectMembership, ProjectVersion

from .. import services
from ..models import Task


class AssignedTasksForAdminServiceTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.admin = User.objects.create_user(username="wf-admin", organisation=self.org, organisation_role="admin")
        self.plain_member = User.objects.create_user(username="wf-plain", organisation=self.org)
        self.target = User.objects.create_user(username="wf-target", organisation=self.org)
        self.other_org_admin = User.objects.create_user(
            username="wf-other-admin", organisation=Organisation.objects.create(name="Org B"), organisation_role="admin"
        )

        # Deux projets, dont un où l'admin n'est pas membre — voir
        # docs/organisation-et-comptes.md > exception assumée.
        self.project_a = Project.objects.create(name="Projet A", organisation=self.org)
        self.project_b = Project.objects.create(name="Projet B", organisation=self.org)
        ProjectMembership.objects.create(project=self.project_a, user=self.admin, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project_a, user=self.target, role="membre")
        ProjectMembership.objects.create(project=self.project_b, user=self.target, role="membre")
        version_a = ProjectVersion.objects.create(project=self.project_a, label="v1", is_current=True)
        version_b = ProjectVersion.objects.create(project=self.project_b, label="v1", is_current=True)
        self.task_a = Task.objects.create(
            project=self.project_a, version=version_a, title="Tâche A", task_type="correction", assignee=self.target
        )
        self.task_b = Task.objects.create(
            project=self.project_b, version=version_b, title="Tâche B", task_type="correction", assignee=self.target
        )

    def test_admin_sees_assigned_tasks_across_all_projects(self):
        tasks = list(services.get_assigned_tasks_for_admin(actor=self.admin, target_user=self.target))

        self.assertIn(self.task_a, tasks)
        self.assertIn(self.task_b, tasks)  # admin n'est pas membre de project_b — exception assumée

    def test_plain_member_cannot_use_workload_view(self):
        with self.assertRaises(services.TaskPermissionError):
            services.get_assigned_tasks_for_admin(actor=self.plain_member, target_user=self.target)

    def test_admin_of_other_organisation_cannot_see(self):
        with self.assertRaises(services.TaskPermissionError):
            services.get_assigned_tasks_for_admin(actor=self.other_org_admin, target_user=self.target)


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
class AssignedTasksForAdminApiTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.admin = User.objects.create_user(username="wf-admin-api", organisation=self.org, organisation_role="admin")
        self.plain_member = User.objects.create_user(username="wf-plain-api", organisation=self.org)
        self.target = User.objects.create_user(username="wf-target-api", organisation=self.org)
        self.project = Project.objects.create(name="Projet", organisation=self.org)
        version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        ProjectMembership.objects.create(project=self.project, user=self.target, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=version, title="Tâche", task_type="correction", assignee=self.target
        )

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_admin_gets_assigned_tasks(self):
        response = self.client.get(f"/api/v1/tasks/assigned-to/{self.target.id}/", **self.as_user(self.admin))

        self.assertEqual(response.status_code, 200)
        titles = [item["title"] for item in response.json()]
        self.assertEqual(titles, ["Tâche"])

    def test_plain_member_forbidden(self):
        response = self.client.get(f"/api/v1/tasks/assigned-to/{self.target.id}/", **self.as_user(self.plain_member))

        self.assertEqual(response.status_code, 403)
