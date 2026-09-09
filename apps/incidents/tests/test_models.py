from django.test import TestCase

from apps.accounts.models import Team
from apps.incidents.models import Incident
from apps.projects.models import Project


class IncidentTeamOnlyModelTests(TestCase):
    def test_incident_can_be_created_with_team_and_no_project(self):
        team = Team.objects.create(name="Équipe Modèle")

        incident = Incident.objects.create(team=team, title="Panne réseau")

        self.assertIsNone(incident.project)
        self.assertEqual(incident.team, team)


class IncidentActiveManagerTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")

    def test_active_manager_filters_by_status(self):
        incident = Incident.objects.create(project=self.project, title="Erreur 500 en prod")

        self.assertIn(incident, Incident.objects.active())
        self.assertIn(incident, Incident.objects.all())

        incident.status = "archive"
        incident.save()

        self.assertNotIn(incident, Incident.objects.active())
        self.assertIn(incident, Incident.all_objects.all())
