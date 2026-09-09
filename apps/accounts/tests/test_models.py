import uuid

from django.test import TestCase

from apps.accounts.models import Team, TeamMembership, User


class TeamActiveManagerTests(TestCase):
    def test_active_manager_filters_by_status(self):
        team = Team.objects.create(name="Équipe Test")

        self.assertIn(team, Team.objects.active())

        team.status = "archive"
        team.save()

        self.assertNotIn(team, Team.objects.active())
        self.assertIn(team, Team.all_objects.all())


class UserModelTests(TestCase):
    def test_user_has_uuid_primary_key(self):
        user = User.objects.create_user(username="bob")

        self.assertIsInstance(user.id, uuid.UUID)

    def test_user_can_belong_to_multiple_teams(self):
        user = User.objects.create_user(username="carol")
        team_a = Team.objects.create(name="Équipe A")
        team_b = Team.objects.create(name="Équipe B")

        TeamMembership.objects.create(team=team_a, user=user)
        TeamMembership.objects.create(team=team_b, user=user)

        self.assertEqual(user.team_memberships.filter(status="active").count(), 2)
