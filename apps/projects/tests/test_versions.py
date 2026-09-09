from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.tasks.models import Task
from apps.tasks.services import create_task

from .. import services
from ..models import Project, ProjectMembership, ProjectVersion


class ProjectVersionServiceTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="version-manager")
        self.member = User.objects.create_user(username="version-member")
        self.project = Project.objects.create(name="Projet Test")
        self.v1 = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def test_project_creation_via_service_creates_initial_version(self):
        project = services.create_project(actor=self.manager, name="Nouveau projet", project_type="individuel")

        versions = ProjectVersion.objects.filter(project=project)
        self.assertEqual(versions.count(), 1)
        self.assertEqual(versions.first().label, "v1")
        self.assertTrue(versions.first().is_current)

    def test_manager_creates_new_version_becomes_current(self):
        v1 = services.get_current_version(self.project)

        v2 = services.create_project_version(actor=self.manager, project=self.project, label="Sprint 2")

        v1.refresh_from_db()
        self.assertFalse(v1.is_current)
        self.assertTrue(v2.is_current)
        self.assertEqual(services.get_current_version(self.project), v2)

    def test_member_cannot_create_version(self):
        with self.assertRaises(services.ProjectPermissionError):
            services.create_project_version(actor=self.member, project=self.project, label="Sprint 2")

    def test_empty_label_rejected(self):
        with self.assertRaises(services.ProjectValidationError):
            services.create_project_version(actor=self.manager, project=self.project, label="   ")

    def test_task_creation_always_targets_current_version(self):
        v1 = services.get_current_version(self.project)
        task_on_v1 = create_task(actor=self.member, project=self.project, title="Tâche v1", task_type="correction")
        self.assertEqual(task_on_v1.version, v1)

        v2 = services.create_project_version(actor=self.manager, project=self.project, label="Sprint 2")
        task_on_v2 = create_task(actor=self.member, project=self.project, title="Tâche v2", task_type="correction")

        self.assertEqual(task_on_v2.version, v2)
        # La tâche déjà créée sur v1 ne bouge pas rétroactivement.
        task_on_v1.refresh_from_db()
        self.assertEqual(task_on_v1.version, v1)


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
class ProjectVersionApiTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="version-manager-api")
        self.member = User.objects.create_user(username="version-member-api")
        self.project = Project.objects.create(name="Projet Test")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.v1 = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_member_lists_versions(self):
        response = self.client.get(f"/api/v1/projects/{self.project.id}/versions/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
        labels = [item["label"] for item in response.json()]
        self.assertEqual(labels, ["v1"])

    def test_manager_creates_version_via_api(self):
        response = self.client.post(
            f"/api/v1/projects/{self.project.id}/versions/",
            {"label": "Sprint 2"},
            content_type="application/json",
            **self.as_user(self.manager),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["label"], "Sprint 2")
        self.assertTrue(response.json()["is_current"])

    def test_member_cannot_create_version_via_api(self):
        response = self.client.post(
            f"/api/v1/projects/{self.project.id}/versions/",
            {"label": "Sprint 2"},
            content_type="application/json",
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 403)

    def test_task_response_includes_version_label(self):
        task = Task.objects.create(project=self.project, version=self.v1, title="Tâche", task_type="correction")

        response = self.client.get(f"/api/v1/tasks/{task.id}/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version_label"], "v1")

    def test_task_list_filtered_by_version(self):
        v2 = ProjectVersion.objects.create(project=self.project, label="v2")
        Task.objects.create(project=self.project, version=self.v1, title="Tâche v1", task_type="correction")
        Task.objects.create(project=self.project, version=v2, title="Tâche v2", task_type="correction")

        response = self.client.get(
            "/api/v1/tasks/", {"project": str(self.project.id), "version": str(v2.id)}, **self.as_user(self.member)
        )

        titles = [item["title"] for item in response.json()]
        self.assertEqual(titles, ["Tâche v2"])
