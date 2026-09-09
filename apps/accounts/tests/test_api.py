from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Team, TeamMembership, User


@override_settings(REST_FRAMEWORK={"DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"]})
class UserApiTests(APITestCase):
    def test_list_returns_users(self):
        user = User.objects.create_user(username="bob")

        response = self.client.get("/api/v1/accounts/users/")

        self.assertEqual(response.status_code, 200)
        usernames = [item["username"] for item in response.json()]
        self.assertIn(user.username, usernames)

    def test_user_payload_includes_teams(self):
        user = User.objects.create_user(username="carol")
        team = Team.objects.create(name="Équipe Test")
        TeamMembership.objects.create(team=team, user=user)

        response = self.client.get("/api/v1/accounts/users/")

        payload = next(item for item in response.json() if item["username"] == "carol")
        self.assertEqual(payload["teams"], [str(team.id)])


@override_settings(REST_FRAMEWORK={"DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"]})
class TeamApiTests(APITestCase):
    def test_list_returns_teams(self):
        team = Team.objects.create(name="Équipe Test")

        response = self.client.get("/api/v1/accounts/teams/")

        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.json()]
        self.assertIn(team.name, names)
