from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership

from ..models import Incident


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
class IncidentStatusFilterApiTests(APITestCase):
    """Voir docs/modeles-et-api.md > "Filtre d'état généralisé"."""

    def setUp(self):
        self.member = User.objects.create_user(username="status-filter-incident-member")
        self.project = Project.objects.create(name="Projet Test")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.active_incident = Incident.objects.create(project=self.project, title="Signalé", status="signale")
        self.archived_incident = Incident.objects.create(project=self.project, title="Archivé", status="archive")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_archived_hidden_by_default(self):
        response = self.client.get("/api/v1/incidents/", **self.as_user(self.member))

        ids = [item["id"] for item in response.json()]
        self.assertIn(str(self.active_incident.id), ids)
        self.assertNotIn(str(self.archived_incident.id), ids)

    def test_archived_visible_when_explicitly_requested(self):
        response = self.client.get("/api/v1/incidents/", {"status": "archive"}, **self.as_user(self.member))

        ids = [item["id"] for item in response.json()]
        self.assertNotIn(str(self.active_incident.id), ids)
        self.assertIn(str(self.archived_incident.id), ids)

    def test_detail_of_archived_incident_still_reachable(self):
        response = self.client.get(f"/api/v1/incidents/{self.archived_incident.id}/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
