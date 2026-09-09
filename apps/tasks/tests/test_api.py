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
    }
)
class TaskListApiTests(APITestCase):
    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_list_returns_active_tasks_filtered_by_project(self):
        project = Project.objects.create(name="Projet Test")
        other_project = Project.objects.create(name="Autre Projet")
        version = ProjectVersion.objects.create(project=project, label="v1", is_current=True)
        other_version = ProjectVersion.objects.create(project=other_project, label="v1", is_current=True)
        member = User.objects.create_user(username="member-list")
        ProjectMembership.objects.create(project=project, user=member, role="membre")
        ProjectMembership.objects.create(project=other_project, user=member, role="membre")
        task = Task.objects.create(project=project, version=version, title="Corriger le bug", task_type="correction")
        Task.objects.create(project=other_project, version=other_version, title="Autre tâche", task_type="ajout")

        response = self.client.get("/api/v1/tasks/", {"project": str(project.id)}, **self.as_user(member))

        self.assertEqual(response.status_code, 200)
        titles = [item["title"] for item in response.json()]
        self.assertEqual(titles, [task.title])

    def test_list_filtered_by_team_returns_only_tasks_assigned_to_team_members(self):
        project = Project.objects.create(name="Projet Test")
        version = ProjectVersion.objects.create(project=project, label="v1", is_current=True)
        team = Team.objects.create(name="Équipe Test")
        member = User.objects.create_user(username="alice")
        outsider = User.objects.create_user(username="bob")
        TeamMembership.objects.create(team=team, user=member)
        ProjectMembership.objects.create(project=project, user=member, role="membre")

        task = Task.objects.create(
            project=project, version=version, title="Tâche équipe", task_type="correction", assignee=member, status="assignee"
        )
        Task.objects.create(
            project=project, version=version, title="Tâche hors équipe", task_type="correction", assignee=outsider, status="assignee"
        )

        response = self.client.get("/api/v1/tasks/", {"team": str(team.id)}, **self.as_user(member))

        self.assertEqual(response.status_code, 200)
        titles = [item["title"] for item in response.json()]
        self.assertEqual(titles, [task.title])


@override_settings(
    DEBUG=True,
    REST_FRAMEWORK={
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "apps.accounts.authentication.DebugUserIdAuthentication",
            "rest_framework.authentication.SessionAuthentication",
        ],
    }
)
class TaskLifecycleApiTests(APITestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.manager = User.objects.create_user(username="manager")
        self.member = User.objects.create_user(username="member")
        self.outsider = User.objects.create_user(username="outsider")

        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def make_task(self, status="en_attente_validation", assignee=None):
        return Task.objects.create(
            project=self.project,
            version=self.version,
            title="Corriger le bug",
            task_type="correction",
            status=status,
            assignee=assignee,
        )

    def test_create_without_debug_header_is_rejected(self):
        response = self.client.post(
            "/api/v1/tasks/",
            {"project": str(self.project.id), "title": "Nouvelle tâche", "task_type": "correction"},
        )

        self.assertEqual(response.status_code, 403)

    def test_member_creates_task_pending_validation(self):
        response = self.client.post(
            "/api/v1/tasks/",
            {"project": str(self.project.id), "title": "Nouvelle tâche", "task_type": "correction"},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "en_attente_validation")

    def test_create_ignores_missing_external_reference_id(self):
        response = self.client.post(
            "/api/v1/tasks/",
            {"project": str(self.project.id), "title": "Nouvelle tâche", "task_type": "correction"},
            **self.as_user(self.member),
        )

        self.assertIsNone(response.json()["external_reference_id"])

    def test_outsider_cannot_create_task(self):
        response = self.client.post(
            "/api/v1/tasks/",
            {"project": str(self.project.id), "title": "Nouvelle tâche", "task_type": "correction"},
            **self.as_user(self.outsider),
        )

        self.assertEqual(response.status_code, 403)

    def test_manager_validates_task(self):
        task = self.make_task("en_attente_validation")

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/validate/", **self.as_user(self.manager)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "disponible")

    def test_member_cannot_validate_task(self):
        task = self.make_task("en_attente_validation")

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/validate/", **self.as_user(self.member)
        )

        self.assertEqual(response.status_code, 403)

    def test_validate_wrong_status_returns_400(self):
        task = self.make_task("disponible")

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/validate/", **self.as_user(self.manager)
        )

        self.assertEqual(response.status_code, 400)

    def test_manager_rejects_task_with_reason(self):
        task = self.make_task("en_attente_validation")

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/reject/",
            {"rejection_reason": "Hors périmètre"},
            **self.as_user(self.manager),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "rejetee")

    def test_reject_without_reason_returns_400(self):
        task = self.make_task("en_attente_validation")

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/reject/", **self.as_user(self.manager)
        )

        self.assertEqual(response.status_code, 400)

    def test_member_claims_available_task(self):
        task = self.make_task("disponible")

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/claim/", **self.as_user(self.member)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "assignee")
        self.assertEqual(response.json()["assignee"]["id"], str(self.member.id))

    def test_outsider_cannot_claim(self):
        # 404, pas 403 : sans ProjectMembership, l'outsider sort du queryset
        # scopé avant même la vérification de rôle (voir CLAUDE.md >
        # "Scoping des listes par appartenance").
        task = self.make_task("disponible")

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/claim/", **self.as_user(self.outsider)
        )

        self.assertEqual(response.status_code, 404)

    def test_manager_assigns_task(self):
        task = self.make_task("disponible")

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/assign/",
            {"assignee": str(self.member.id)},
            **self.as_user(self.manager),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "assignee")

    def test_assign_unknown_user_returns_400(self):
        task = self.make_task("disponible")

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/assign/",
            {"assignee": "00000000-0000-0000-0000-000000000000"},
            **self.as_user(self.manager),
        )

        self.assertEqual(response.status_code, 400)

    def test_assignee_starts_task(self):
        task = self.make_task("assignee", assignee=self.member)

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/start/", **self.as_user(self.member)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "en_cours")

    def test_non_assignee_cannot_start(self):
        task = self.make_task("assignee", assignee=self.member)

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/start/", **self.as_user(self.manager)
        )

        self.assertEqual(response.status_code, 403)

    def test_assignee_completes_task(self):
        task = self.make_task("en_cours", assignee=self.member)

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/complete/",
            {"time_spent": "2.5"},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "archivee")
        self.assertEqual(response.json()["time_spent"], "2.50")

    def test_manager_completes_task_not_assigned_to_them(self):
        task = self.make_task("en_cours", assignee=self.member)

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/complete/",
            {"time_spent": "1.5"},
            **self.as_user(self.manager),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "archivee")

    def test_complete_without_time_spent_returns_400(self):
        task = self.make_task("en_cours", assignee=self.member)

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/complete/", **self.as_user(self.member)
        )

        self.assertEqual(response.status_code, 400)

    def test_member_renames_task(self):
        task = self.make_task("disponible")

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/rename/",
            {"title": "Titre corrigé"},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Titre corrigé")

    def test_outsider_cannot_rename_task(self):
        # 404, pas 403 : même raison que test_outsider_cannot_claim.
        task = self.make_task("disponible")

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/rename/",
            {"title": "Titre corrigé"},
            **self.as_user(self.outsider),
        )

        self.assertEqual(response.status_code, 404)

    def test_rename_with_empty_title_returns_400(self):
        task = self.make_task("disponible")

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/rename/",
            {"title": "   "},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 400)

    def test_member_updates_task_description(self):
        task = self.make_task("disponible")

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/update-description/",
            {"description": "Description corrigée"},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["description"], "Description corrigée")

    def test_outsider_cannot_update_task_description(self):
        # 404, pas 403 : même raison que test_outsider_cannot_rename_task.
        task = self.make_task("disponible")

        response = self.client.post(
            f"/api/v1/tasks/{task.id}/update-description/",
            {"description": "Description corrigée"},
            **self.as_user(self.outsider),
        )

        self.assertEqual(response.status_code, 404)
