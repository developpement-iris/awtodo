from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .. import services
from ..models import Project, ProjectMembership


class ProjectPermissionFlagsServiceTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.manager = User.objects.create_user(username="proj-manager")
        self.member = User.objects.create_user(username="proj-member")
        self.outsider = User.objects.create_user(username="proj-outsider")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def test_member_can_edit_notes_but_not_manage_members(self):
        flags = services.get_project_permissions(self.member, self.project)

        self.assertTrue(flags["can_edit_spec"])
        self.assertTrue(flags["can_edit_notepad"])
        self.assertFalse(flags["can_manage_members"])
        self.assertFalse(flags["can_manage_budget"])

    def test_manager_can_do_everything(self):
        flags = services.get_project_permissions(self.manager, self.project)

        self.assertTrue(flags["can_edit_spec"])
        self.assertTrue(flags["can_edit_notepad"])
        self.assertTrue(flags["can_manage_members"])
        self.assertTrue(flags["can_manage_budget"])

    def test_outsider_has_every_flag_false(self):
        flags = services.get_project_permissions(self.outsider, self.project)

        self.assertFalse(any(flags.values()))


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
class ProjectPermissionFlagsApiTests(APITestCase):
    def test_project_response_includes_permissions_object(self):
        project = Project.objects.create(name="Projet Test")
        manager = User.objects.create_user(username="proj-manager-api")
        ProjectMembership.objects.create(project=project, user=manager, role="chef_de_projet")

        response = self.client.get(f"/api/v1/projects/{project.id}/", HTTP_X_DEBUG_USER_ID=str(manager.id))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["permissions"]["can_manage_members"])
