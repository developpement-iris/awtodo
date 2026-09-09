from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Team, TeamMembership, User
from apps.common.audit import get_audit_log
from apps.incidents.models import Incident
from apps.incidents.services import resolve_incident, start_incident


class IncidentAuditServiceTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Équipe Test Audit")
        self.member = User.objects.create_user(username="member-incident-audit")
        TeamMembership.objects.create(team=self.team, user=self.member)
        self.incident = Incident.objects.create(team=self.team, title="Panne réseau")

    def test_start_incident_logs_status_with_display_label(self):
        start_incident(actor=self.member, incident=self.incident)

        entry = get_audit_log(self.incident).get(field_name="status")
        self.assertEqual(entry.old_value, "Signalé")
        self.assertEqual(entry.new_value, "En cours")

    def test_two_transitions_produce_two_entries_in_order(self):
        start_incident(actor=self.member, incident=self.incident)
        resolve_incident(actor=self.member, incident=self.incident)

        entries = list(get_audit_log(self.incident))
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].new_value, "En cours")
        self.assertEqual(entries[1].new_value, "Résolu")


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
class IncidentAuditApiTests(APITestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Équipe Test Audit API")
        self.member = User.objects.create_user(username="member-incident-audit-api")
        TeamMembership.objects.create(team=self.team, user=self.member)
        self.incident = Incident.objects.create(team=self.team, title="Panne réseau")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_detail_includes_audit_log(self):
        self.client.post(f"/api/v1/incidents/{self.incident.id}/start/", **self.as_user(self.member))

        response = self.client.get(f"/api/v1/incidents/{self.incident.id}/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
        audit_log = response.json()["audit_log"]
        self.assertEqual(len(audit_log), 1)
        self.assertEqual(audit_log[0]["field_name"], "status")
        self.assertEqual(audit_log[0]["new_value"], "En cours")
