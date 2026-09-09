from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Team, TeamMembership, User
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task


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
class ProjectApiTests(APITestCase):
    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_list_returns_active_projects(self):
        project = Project.objects.create(name="Projet Test")
        member = User.objects.create_user(username="member-list")
        ProjectMembership.objects.create(project=project, user=member, role="membre")

        response = self.client.get("/api/v1/projects/", **self.as_user(member))

        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()]
        self.assertIn(str(project.id), ids)

    def test_list_includes_task_progress_counts(self):
        project = Project.objects.create(name="Projet Test")
        version = ProjectVersion.objects.create(project=project, label="v1", is_current=True)
        member = User.objects.create_user(username="member-progress")
        ProjectMembership.objects.create(project=project, user=member, role="membre")
        Task.objects.create(project=project, version=version, title="Active", task_type="correction", status="disponible")
        Task.objects.create(project=project, version=version, title="Terminée", task_type="correction", status="archivee")
        Task.objects.create(project=project, version=version, title="Rejetée", task_type="correction", status="rejetee")

        response = self.client.get("/api/v1/projects/", **self.as_user(member))

        payload = next(item for item in response.json() if item["id"] == str(project.id))
        self.assertEqual(payload["tasks_total"], 2)
        self.assertEqual(payload["tasks_done"], 1)

    def test_project_without_tasks_has_zero_counts(self):
        project = Project.objects.create(name="Projet vide")
        member = User.objects.create_user(username="member-empty")
        ProjectMembership.objects.create(project=project, user=member, role="membre")

        response = self.client.get("/api/v1/projects/", **self.as_user(member))

        payload = next(item for item in response.json() if item["id"] == str(project.id))
        self.assertEqual(payload["tasks_total"], 0)
        self.assertEqual(payload["tasks_done"], 0)


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
class ProjectCreateApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice")
        self.team = Team.objects.create(name="Équipe Test")
        TeamMembership.objects.create(team=self.team, user=self.user)

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_create_individual_project(self):
        response = self.client.post(
            "/api/v1/projects/",
            {"name": "Projet solo", "project_type": "individuel"},
            **self.as_user(self.user),
        )

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()["team"])
        self.assertEqual(response.json()["tasks_total"], 0)
        self.assertEqual(response.json()["tasks_done"], 0)

    def test_create_collaborative_project_with_team(self):
        response = self.client.post(
            "/api/v1/projects/",
            {"name": "Projet collab", "project_type": "collaboratif", "team": str(self.team.id)},
            **self.as_user(self.user),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["team"], str(self.team.id))
        self.assertEqual(response.json()["team_name"], self.team.name)

    def test_create_collaborative_project_without_team_returns_400(self):
        response = self.client.post(
            "/api/v1/projects/",
            {"name": "Projet collab", "project_type": "collaboratif"},
            **self.as_user(self.user),
        )

        self.assertEqual(response.status_code, 400)

    def test_create_without_debug_header_is_rejected(self):
        response = self.client.post("/api/v1/projects/", {"name": "Projet solo", "project_type": "individuel"})

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
class ProjectNotesApiTests(APITestCase):
    def setUp(self):
        self.member = User.objects.create_user(username="alice")
        self.outsider = User.objects.create_user(username="bob")
        self.project = Project.objects.create(name="Projet Test")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_member_updates_notepad_content(self):
        response = self.client.patch(
            f"/api/v1/projects/{self.project.id}/",
            {"notepad_content": "Idée en vrac"},
            content_type="application/json",
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["notepad_content"], "Idée en vrac")

    def test_outsider_cannot_update_notes(self):
        # 404, pas 403 : l'outsider n'a pas de ProjectMembership active sur ce
        # projet, donc il sort du queryset scopé avant même la vérification de
        # rôle — voir CLAUDE.md > "Scoping des listes par appartenance"
        # ("ne révèle pas l'existence de l'objet à quelqu'un qui n'y a pas accès").
        response = self.client.patch(
            f"/api/v1/projects/{self.project.id}/",
            {"notepad_content": "Intrusion"},
            content_type="application/json",
            **self.as_user(self.outsider),
        )

        self.assertEqual(response.status_code, 404)


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
class SpecSectionApiTests(APITestCase):
    def setUp(self):
        self.member = User.objects.create_user(username="carole-api")
        self.outsider = User.objects.create_user(username="dave-api")
        self.project = Project.objects.create(name="Projet Test")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_member_lists_twelve_sections(self):
        response = self.client.get(f"/api/v1/projects/{self.project.id}/spec-sections/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 12)

    def test_member_toggles_section_active(self):
        response = self.client.patch(
            f"/api/v1/projects/{self.project.id}/spec-sections/objectifs/",
            {"is_active": True, "content": "Nos objectifs."},
            content_type="application/json",
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["section_key"], "objectifs")
        self.assertTrue(payload["is_active"])
        self.assertEqual(payload["content"], "Nos objectifs.")

    def test_invalid_section_key_returns_400(self):
        response = self.client.patch(
            f"/api/v1/projects/{self.project.id}/spec-sections/wrong/",
            {"is_active": True},
            content_type="application/json",
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 400)

    def test_outsider_gets_404_on_sections(self):
        response = self.client.get(
            f"/api/v1/projects/{self.project.id}/spec-sections/", **self.as_user(self.outsider)
        )

        self.assertEqual(response.status_code, 404)
