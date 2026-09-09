from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .. import services
from ..models import Project, ProjectMembership


class ProjectLifecycleServiceTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="lifecycle-manager")
        self.member = User.objects.create_user(username="lifecycle-member")
        self.project = Project.objects.create(name="Projet Test")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def test_manager_closes_active_project(self):
        services.close_project(actor=self.manager, project=self.project)

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, "cloture")

    def test_member_cannot_close_project(self):
        with self.assertRaises(services.ProjectPermissionError):
            services.close_project(actor=self.member, project=self.project)

    def test_cannot_close_already_closed_project(self):
        services.close_project(actor=self.manager, project=self.project)

        with self.assertRaises(services.ProjectValidationError):
            services.close_project(actor=self.manager, project=self.project)

    def test_manager_reopens_closed_project(self):
        services.close_project(actor=self.manager, project=self.project)

        services.reopen_project(actor=self.manager, project=self.project)

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, "actif")

    def test_cannot_reopen_active_project(self):
        with self.assertRaises(services.ProjectValidationError):
            services.reopen_project(actor=self.manager, project=self.project)

    def test_permission_flags_reflect_status(self):
        active_flags = services.get_project_permissions(self.manager, self.project)
        self.assertTrue(active_flags["can_close"])
        self.assertFalse(active_flags["can_reopen"])

        services.close_project(actor=self.manager, project=self.project)

        closed_flags = services.get_project_permissions(self.manager, self.project)
        self.assertFalse(closed_flags["can_close"])
        self.assertTrue(closed_flags["can_reopen"])


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
class ProjectLifecycleApiTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="lifecycle-manager-api")
        self.member = User.objects.create_user(username="lifecycle-member-api")
        self.project = Project.objects.create(name="Projet Test")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_manager_closes_project_via_api(self):
        response = self.client.post(f"/api/v1/projects/{self.project.id}/close/", **self.as_user(self.manager))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "cloture")

    def test_member_cannot_close_project_via_api(self):
        response = self.client.post(f"/api/v1/projects/{self.project.id}/close/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 403)

    def test_manager_reopens_project_via_api(self):
        self.client.post(f"/api/v1/projects/{self.project.id}/close/", **self.as_user(self.manager))

        response = self.client.post(f"/api/v1/projects/{self.project.id}/reopen/", **self.as_user(self.manager))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "actif")
