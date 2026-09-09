from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.audit import get_audit_log
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task
from apps.tasks.services import rename_task, start_task, validate_task


class TaskAuditServiceTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.manager = User.objects.create_user(username="manager-audit")
        self.member = User.objects.create_user(username="member-audit")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Titre initial", task_type="correction"
        )

    def test_rename_task_logs_title_change(self):
        rename_task(actor=self.member, task=self.task, title="Nouveau titre")

        entries = list(get_audit_log(self.task))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].field_name, "title")
        self.assertEqual(entries[0].old_value, "Titre initial")
        self.assertEqual(entries[0].new_value, "Nouveau titre")
        self.assertEqual(entries[0].actor, self.member)

    def test_validate_task_logs_status_with_display_label(self):
        validate_task(actor=self.manager, task=self.task)

        entry = get_audit_log(self.task).get(field_name="status")
        self.assertEqual(entry.old_value, "En attente de validation")
        self.assertEqual(entry.new_value, "Disponible")


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
class TaskAuditApiTests(APITestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.member = User.objects.create_user(username="member-audit-api")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Titre initial", task_type="correction"
        )

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_detail_includes_audit_log(self):
        self.client.post(
            f"/api/v1/tasks/{self.task.id}/rename/", {"title": "Titre modifié"}, **self.as_user(self.member)
        )

        response = self.client.get(f"/api/v1/tasks/{self.task.id}/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
        audit_log = response.json()["audit_log"]
        self.assertEqual(len(audit_log), 1)
        self.assertEqual(audit_log[0]["field_name"], "title")
        self.assertEqual(audit_log[0]["new_value"], "Titre modifié")
