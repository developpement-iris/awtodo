from datetime import date

from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task
from apps.tasks.services import InvalidTransitionError, TaskPermissionError, update_task_deadline


class UpdateTaskDeadlineServiceTests(TestCase):
    """Retour direct : "changer/supprimer une date d'échéance sur une
    tâche, droit propre au rôle chef de projet" — à la différence du
    titre/description/temps estimé (tout membre), réservé au chef de
    projet."""

    def setUp(self):
        self.project = Project.objects.create(name="Projet Test Échéance")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.manager = User.objects.create_user(username="manager-deadline")
        self.member = User.objects.create_user(username="member-deadline")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Corriger le bug", task_type="correction"
        )

    def test_manager_can_set_deadline(self):
        update_task_deadline(actor=self.manager, task=self.task, deadline="2026-12-31")

        self.assertEqual(self.task.deadline, date(2026, 12, 31))

    def test_manager_can_clear_deadline(self):
        update_task_deadline(actor=self.manager, task=self.task, deadline="2026-12-31")

        update_task_deadline(actor=self.manager, task=self.task, deadline=None)

        self.assertIsNone(self.task.deadline)

    def test_manager_can_clear_deadline_with_empty_string(self):
        update_task_deadline(actor=self.manager, task=self.task, deadline="2026-12-31")

        update_task_deadline(actor=self.manager, task=self.task, deadline="")

        self.assertIsNone(self.task.deadline)

    def test_plain_member_cannot_set_deadline(self):
        with self.assertRaises(TaskPermissionError):
            update_task_deadline(actor=self.member, task=self.task, deadline="2026-12-31")

    def test_invalid_date_format_rejected(self):
        with self.assertRaises(InvalidTransitionError):
            update_task_deadline(actor=self.manager, task=self.task, deadline="not-a-date")


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
class UpdateTaskDeadlineApiTests(APITestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test Échéance API")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.manager = User.objects.create_user(username="manager-deadline-api")
        self.member = User.objects.create_user(username="member-deadline-api")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Corriger le bug", task_type="correction"
        )

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_manager_updates_deadline_via_api(self):
        response = self.client.post(
            f"/api/v1/tasks/{self.task.id}/update-deadline/",
            {"deadline": "2026-12-31"},
            **self.as_user(self.manager),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deadline"], "2026-12-31")
        self.assertTrue(response.json()["permissions"]["can_edit_deadline"])

    def test_member_forbidden_via_api(self):
        response = self.client.post(
            f"/api/v1/tasks/{self.task.id}/update-deadline/",
            {"deadline": "2026-12-31"},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 403)

    def test_member_permission_flag_is_false(self):
        response = self.client.get(f"/api/v1/tasks/{self.task.id}/", **self.as_user(self.member))

        self.assertFalse(response.json()["permissions"]["can_edit_deadline"])
