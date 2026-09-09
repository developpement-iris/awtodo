from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Team, TeamMembership, User
from apps.projects.models import Project, ProjectMembership

from .. import services
from ..models import Incident


class IncidentPermissionFlagsServiceTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.member = User.objects.create_user(username="incident-member")
        self.outsider = User.objects.create_user(username="incident-outsider")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def make_incident(self, status="signale"):
        return Incident.objects.create(project=self.project, title="Incident", status=status)

    def test_reported_incident_flags_for_member(self):
        incident = self.make_incident("signale")

        flags = services.get_incident_permissions(self.member, incident)

        self.assertTrue(flags["can_start"])
        self.assertFalse(flags["can_resolve"])
        self.assertFalse(flags["can_archive"])
        self.assertTrue(flags["can_comment"])

    def test_in_progress_incident_flags(self):
        incident = self.make_incident("en_cours")

        flags = services.get_incident_permissions(self.member, incident)

        self.assertFalse(flags["can_start"])
        self.assertTrue(flags["can_resolve"])

    def test_resolved_incident_flags(self):
        incident = self.make_incident("resolu")

        flags = services.get_incident_permissions(self.member, incident)

        self.assertFalse(flags["can_resolve"])
        self.assertTrue(flags["can_archive"])

    def test_outsider_has_every_flag_false(self):
        incident = self.make_incident("signale")

        flags = services.get_incident_permissions(self.outsider, incident)

        self.assertFalse(any(flags.values()))

    def test_flag_matches_real_transition_outcome(self):
        incident = self.make_incident("signale")
        self.assertTrue(services.can_start_incident(self.member, incident))
        services.start_incident(actor=self.member, incident=incident)  # ne lève pas

        incident2 = self.make_incident("signale")
        self.assertFalse(services.can_start_incident(self.outsider, incident2))
        with self.assertRaises(services.IncidentPermissionError):
            services.start_incident(actor=self.outsider, incident=incident2)


class IncidentPermissionFlagsForTeamOnlyIncidentTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Équipe Test Permissions")
        self.member = User.objects.create_user(username="team-incident-member")
        self.outsider = User.objects.create_user(username="team-incident-outsider")
        TeamMembership.objects.create(team=self.team, user=self.member)

    def make_incident(self, status="signale"):
        return Incident.objects.create(team=self.team, title="Panne réseau", status=status)

    def test_team_member_can_assign_project_flag_true_when_unassigned(self):
        incident = self.make_incident()

        flags = services.get_incident_permissions(self.member, incident)

        self.assertTrue(flags["can_assign_project"])

    def test_outsider_has_every_flag_false(self):
        incident = self.make_incident()

        flags = services.get_incident_permissions(self.outsider, incident)

        self.assertFalse(any(flags.values()))

    def test_can_assign_project_false_once_incident_has_a_project(self):
        project = Project.objects.create(name="Destination")
        ProjectMembership.objects.create(project=project, user=self.member, role="membre")
        incident = self.make_incident()
        services.assign_incident_to_project(actor=self.member, incident=incident, project=project)

        flags = services.get_incident_permissions(self.member, incident)

        self.assertFalse(flags["can_assign_project"])


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
class IncidentPermissionFlagsApiTests(APITestCase):
    def test_incident_response_includes_permissions_object(self):
        project = Project.objects.create(name="Projet Test")
        member = User.objects.create_user(username="incident-member-api")
        ProjectMembership.objects.create(project=project, user=member, role="membre")
        incident = Incident.objects.create(project=project, title="Incident")

        response = self.client.get(f"/api/v1/incidents/{incident.id}/", HTTP_X_DEBUG_USER_ID=str(member.id))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["permissions"]["can_start"])
