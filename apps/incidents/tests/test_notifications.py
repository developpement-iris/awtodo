from django.test import TestCase

from apps.accounts.models import Team, TeamMembership, User
from apps.incidents.models import Incident
from apps.incidents.services import add_comment
from apps.incidents.signals import incident_commented


class IncidentSignalsTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Équipe Test Notif")
        self.member = User.objects.create_user(username="member-incident-notif")
        TeamMembership.objects.create(team=self.team, user=self.member)
        self.incident = Incident.objects.create(team=self.team, title="Panne réseau")

    def test_add_comment_sends_incident_commented_signal(self):
        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        incident_commented.connect(handler)
        try:
            comment = add_comment(actor=self.member, incident=self.incident, content="Je regarde")
        finally:
            incident_commented.disconnect(handler)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["incident"], self.incident)
        self.assertEqual(received[0]["comment"], comment)
        self.assertEqual(received[0]["actor"], self.member)
