from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership, ProjectVersion

from ..models import Task


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
class TaskStatusFilterApiTests(APITestCase):
    """Voir docs/modeles-et-api.md > "Filtre d'état généralisé"."""

    def setUp(self):
        self.member = User.objects.create_user(username="status-filter-task-member")
        self.project = Project.objects.create(name="Projet Test")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.active_task = Task.objects.create(
            project=self.project, version=self.version, title="Active", task_type="correction", status="disponible"
        )
        self.archived_task = Task.objects.create(
            project=self.project, version=self.version, title="Archivée", task_type="correction", status="archivee"
        )
        self.rejected_task = Task.objects.create(
            project=self.project, version=self.version, title="Rejetée", task_type="correction", status="rejetee"
        )

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_archived_and_rejected_hidden_by_default(self):
        response = self.client.get("/api/v1/tasks/", **self.as_user(self.member))

        ids = [item["id"] for item in response.json()]
        self.assertIn(str(self.active_task.id), ids)
        self.assertNotIn(str(self.archived_task.id), ids)
        self.assertNotIn(str(self.rejected_task.id), ids)

    def test_archived_visible_when_explicitly_requested(self):
        response = self.client.get(
            "/api/v1/tasks/", {"status": ["archivee", "rejetee"]}, **self.as_user(self.member)
        )

        ids = [item["id"] for item in response.json()]
        self.assertNotIn(str(self.active_task.id), ids)
        self.assertIn(str(self.archived_task.id), ids)
        self.assertIn(str(self.rejected_task.id), ids)

    def test_detail_of_archived_task_still_reachable(self):
        # Le filtre par défaut ne s'applique qu'aux listes (voir
        # `ListOnlyFilterMixin`), jamais à la résolution d'un objet précis.
        response = self.client.get(f"/api/v1/tasks/{self.archived_task.id}/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
