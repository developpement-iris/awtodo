from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Team, TeamMembership, User
from apps.incidents.models import Incident
from apps.projects.models import Project, ProjectMembership


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
class IncidentApiTests(APITestCase):
    def test_list_returns_active_incidents(self):
        project = Project.objects.create(name="Projet Test")
        member = User.objects.create_user(username="member-incident-list")
        ProjectMembership.objects.create(project=project, user=member, role="membre")
        incident = Incident.objects.create(project=project, title="Erreur 500 en prod")

        response = self.client.get("/api/v1/incidents/", HTTP_X_DEBUG_USER_ID=str(member.id))

        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()]
        self.assertIn(str(incident.id), ids)


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
class IncidentLifecycleApiTests(APITestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Équipe Test")
        self.member = User.objects.create_user(username="alice")
        self.outsider = User.objects.create_user(username="bob")
        TeamMembership.objects.create(team=self.team, user=self.member)
        self.project = Project.objects.create(name="Projet Test", project_type="collaboratif", team=self.team)
        # Requis en plus de la TeamMembership : le scoping des listes (voir
        # CLAUDE.md > "Scoping des listes par appartenance") repose sur
        # `ProjectMembership`, pas sur l'appartenance au groupe — sans elle,
        # `self.member` ne verrait même pas l'incident (404) avant que la
        # règle d'autorisation propre aux incidents (basée sur le groupe) ait
        # l'occasion de s'appliquer.
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def make_incident(self, status="signale"):
        return Incident.objects.create(project=self.project, title="Erreur 500 en prod", status=status)

    def test_member_creates_incident(self):
        response = self.client.post(
            "/api/v1/incidents/",
            {"project": str(self.project.id), "title": "Erreur 500 en prod"},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "signale")

    def test_outsider_cannot_create_incident(self):
        response = self.client.post(
            "/api/v1/incidents/",
            {"project": str(self.project.id), "title": "Erreur 500 en prod"},
            **self.as_user(self.outsider),
        )

        self.assertEqual(response.status_code, 403)

    def test_member_starts_incident(self):
        incident = self.make_incident("signale")

        response = self.client.post(f"/api/v1/incidents/{incident.id}/start/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "en_cours")

    def test_outsider_cannot_start_incident(self):
        # 404, pas 403 : sans ProjectMembership, l'outsider sort du queryset
        # scopé avant même la vérification d'autorisation (voir CLAUDE.md >
        # "Scoping des listes par appartenance").
        incident = self.make_incident("signale")

        response = self.client.post(f"/api/v1/incidents/{incident.id}/start/", **self.as_user(self.outsider))

        self.assertEqual(response.status_code, 404)

    def test_start_from_wrong_status_returns_400(self):
        incident = self.make_incident("en_cours")

        response = self.client.post(f"/api/v1/incidents/{incident.id}/start/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 400)

    def test_member_resolves_incident(self):
        incident = self.make_incident("en_cours")

        response = self.client.post(f"/api/v1/incidents/{incident.id}/resolve/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "resolu")

    def test_member_archives_incident(self):
        incident = self.make_incident("resolu")

        response = self.client.post(f"/api/v1/incidents/{incident.id}/archive/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "archive")

    def test_detail_includes_comments(self):
        incident = self.make_incident()
        self.client.post(
            f"/api/v1/incidents/{incident.id}/comments/",
            {"content": "Premier commentaire"},
            **self.as_user(self.member),
        )

        response = self.client.get(f"/api/v1/incidents/{incident.id}/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
        comments = response.json()["comments"]
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["content"], "Premier commentaire")
        self.assertEqual(comments[0]["author"]["id"], str(self.member.id))

    def test_member_can_add_comment(self):
        incident = self.make_incident()

        response = self.client.post(
            f"/api/v1/incidents/{incident.id}/comments/",
            {"content": "On regarde ça"},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["content"], "On regarde ça")

    def test_outsider_cannot_add_comment(self):
        incident = self.make_incident()

        response = self.client.post(
            f"/api/v1/incidents/{incident.id}/comments/",
            {"content": "Je ne devrais pas pouvoir"},
            **self.as_user(self.outsider),
        )

        # 404, pas 403 : même raison que test_outsider_cannot_start_incident.
        self.assertEqual(response.status_code, 404)

    def test_member_updates_incident_description(self):
        incident = self.make_incident()

        response = self.client.post(
            f"/api/v1/incidents/{incident.id}/update-description/",
            {"description": "Description corrigée"},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["description"], "Description corrigée")

    def test_outsider_cannot_update_incident_description(self):
        incident = self.make_incident()

        response = self.client.post(
            f"/api/v1/incidents/{incident.id}/update-description/",
            {"description": "Description corrigée"},
            **self.as_user(self.outsider),
        )

        # 404, pas 403 : même raison que test_outsider_cannot_start_incident.
        self.assertEqual(response.status_code, 404)

    def test_member_claims_incident(self):
        incident = self.make_incident()

        response = self.client.post(f"/api/v1/incidents/{incident.id}/claim/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["assigned_to"], str(self.member.id))

    def test_outsider_cannot_claim_incident(self):
        incident = self.make_incident()

        response = self.client.post(f"/api/v1/incidents/{incident.id}/claim/", **self.as_user(self.outsider))

        # 404, pas 403 : même raison que test_outsider_cannot_start_incident.
        self.assertEqual(response.status_code, 404)

    def test_assignee_can_change_priority(self):
        incident = self.make_incident()
        self.client.post(f"/api/v1/incidents/{incident.id}/claim/", **self.as_user(self.member))

        response = self.client.post(
            f"/api/v1/incidents/{incident.id}/update-priority/",
            {"priority": "critique"},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["priority"], "critique")

    def test_non_assignee_non_admin_cannot_change_priority(self):
        other_member = User.objects.create_user(username="alice-2")
        TeamMembership.objects.create(team=self.team, user=other_member)
        ProjectMembership.objects.create(project=self.project, user=other_member, role="membre")
        incident = self.make_incident()
        self.client.post(f"/api/v1/incidents/{incident.id}/claim/", **self.as_user(self.member))

        response = self.client.post(
            f"/api/v1/incidents/{incident.id}/update-priority/",
            {"priority": "critique"},
            **self.as_user(other_member),
        )

        self.assertEqual(response.status_code, 403)


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
class IncidentServiceAccountApiTests(APITestCase):
    def setUp(self):
        self.service_account = User.objects.create_user(username="api.ticketing-test", is_service_account=True)
        self.project = Project.objects.create(name="Projet Test", project_type="collaboratif")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_service_account_creates_incident_without_membership(self):
        response = self.client.post(
            "/api/v1/incidents/",
            {"project": str(self.project.id), "title": "Ticket créé automatiquement"},
            **self.as_user(self.service_account),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "signale")


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
class IncidentTeamOnlyApiTests(APITestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Équipe Inbox")
        self.member = User.objects.create_user(username="inbox-member")
        self.outsider = User.objects.create_user(username="inbox-outsider")
        self.platform_admin = User.objects.create_user(username="inbox-admin", is_platform_admin=True)
        TeamMembership.objects.create(team=self.team, user=self.member)
        self.destination_project = Project.objects.create(
            name="Destination", project_type="collaboratif", team=self.team
        )
        ProjectMembership.objects.create(project=self.destination_project, user=self.member, role="membre")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def make_team_only_incident(self, status="signale"):
        return Incident.objects.create(team=self.team, title="Panne réseau", status=status)

    def test_member_creates_team_only_incident(self):
        response = self.client.post(
            "/api/v1/incidents/",
            {"team": str(self.team.id), "title": "Panne réseau"},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIsNone(body["project"])
        self.assertEqual(body["team"], str(self.team.id))

    def test_create_without_project_or_team_is_rejected(self):
        response = self.client.post(
            "/api/v1/incidents/", {"title": "Panne réseau"}, **self.as_user(self.member)
        )

        self.assertEqual(response.status_code, 400)

    def test_inbox_visible_to_team_member(self):
        incident = self.make_team_only_incident()

        response = self.client.get("/api/v1/incidents/inbox/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()]
        self.assertIn(str(incident.id), ids)

    def test_inbox_empty_for_non_member(self):
        self.make_team_only_incident()

        response = self.client.get("/api/v1/incidents/inbox/", **self.as_user(self.outsider))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_inbox_visible_to_platform_admin(self):
        incident = self.make_team_only_incident()

        response = self.client.get("/api/v1/incidents/inbox/", **self.as_user(self.platform_admin))

        ids = [item["id"] for item in response.json()]
        self.assertIn(str(incident.id), ids)

    def test_assigned_incident_never_appears_in_inbox(self):
        incident = self.make_team_only_incident()
        assign_response = self.client.post(
            f"/api/v1/incidents/{incident.id}/assign-project/",
            {"project": str(self.destination_project.id)},
            **self.as_user(self.member),
        )
        self.assertEqual(assign_response.status_code, 200)

        inbox_response = self.client.get("/api/v1/incidents/inbox/", **self.as_user(self.member))
        list_response = self.client.get(
            f"/api/v1/incidents/?project={self.destination_project.id}", **self.as_user(self.member)
        )

        self.assertNotIn(str(incident.id), [item["id"] for item in inbox_response.json()])
        self.assertIn(str(incident.id), [item["id"] for item in list_response.json()])

    def test_assign_project_success_clears_team(self):
        incident = self.make_team_only_incident()

        response = self.client.post(
            f"/api/v1/incidents/{incident.id}/assign-project/",
            {"project": str(self.destination_project.id)},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["project"], str(self.destination_project.id))
        self.assertIsNone(body["team"])

    def test_assign_project_forbidden_if_not_member_of_destination(self):
        incident = self.make_team_only_incident()
        other_project = Project.objects.create(name="Autre projet")

        response = self.client.post(
            f"/api/v1/incidents/{incident.id}/assign-project/",
            {"project": str(other_project.id)},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 403)

    def test_assign_project_rejected_if_already_assigned(self):
        incident = Incident.objects.create(project=self.destination_project, title="Déjà rattaché")

        response = self.client.post(
            f"/api/v1/incidents/{incident.id}/assign-project/",
            {"project": str(self.destination_project.id)},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 400)
