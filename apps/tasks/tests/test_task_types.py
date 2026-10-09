from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionProfile, Team, TeamMembership, User
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks import services
from apps.tasks.models import Task, TaskType


class TaskTypeSeedingTests(TestCase):
    def test_new_team_gets_default_types(self):
        team = Team.objects.create(name="Dev")
        self.assertEqual(
            list(TaskType.all_objects.filter(team=team).values_list("key", flat=True)),
            ["correction", "ajout", "evolution", "test"],
        )

    def test_project_without_team_gets_its_own_types(self):
        project = Project.objects.create(name="Perso", project_type="individuel")
        self.assertEqual(TaskType.all_objects.filter(project=project).count(), 4)

    def test_project_with_team_uses_team_types(self):
        team = Team.objects.create(name="Dev")
        project = Project.objects.create(name="Collab", team=team)
        self.assertEqual(TaskType.all_objects.filter(project=project).count(), 0)
        self.assertEqual(services.task_type_scope(project), team)


class TaskTypeServiceTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username="creator")
        self.team = Team.objects.create(name="Dev", created_by=self.creator)
        TeamMembership.objects.create(team=self.team, user=self.creator, role="administrateur")
        self.member = User.objects.create_user(username="member")
        TeamMembership.objects.create(team=self.team, user=self.member)
        self.project = Project.objects.create(name="Collab", team=self.team)
        ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        ProjectMembership.objects.create(project=self.project, user=self.creator, role="chef_de_projet")
        self.profile = PermissionProfile.objects.create(
            organisation=self.creator.organisation, name="Types", capabilities=["manage_task_types"]
        )

    def _grant(self, user):
        user.permission_profiles.add(self.profile)

    def test_team_admin_without_capability_cannot_manage(self):
        with self.assertRaises(services.TaskPermissionError):
            services.create_task_type(actor=self.creator, scope=self.team, label="Déploiement")

    def test_team_admin_with_capability_creates_type(self):
        self._grant(self.creator)
        task_type = services.create_task_type(actor=self.creator, scope=self.team, label="Déploiement", icon="rocket")
        self.assertEqual(task_type.key, "deploiement")
        self.assertEqual(task_type.team, self.team)

    def test_capability_alone_is_not_enough(self):
        self._grant(self.member)
        with self.assertRaises(services.TaskPermissionError):
            services.create_task_type(actor=self.member, scope=self.team, label="Étude")

    def test_organisation_admin_can_manage(self):
        admin = User.objects.create_user(username="orgadmin", organisation_role="admin")
        services.create_task_type(actor=admin, scope=self.team, label="Étude")

    def test_duplicate_label_rejected_and_key_deduplicated(self):
        self._grant(self.creator)
        first = services.create_task_type(actor=self.creator, scope=self.team, label="Étude")
        with self.assertRaises(services.InvalidTransitionError):
            services.create_task_type(actor=self.creator, scope=self.team, label="étude")
        services.archive_task_type(actor=self.creator, task_type=first)
        second = services.create_task_type(actor=self.creator, scope=self.team, label="Étude")
        self.assertEqual(second.key, "etude_2")

    def test_task_creation_validates_type_against_scope(self):
        self._grant(self.creator)
        services.create_task_type(actor=self.creator, scope=self.team, label="Déploiement")
        task = services.create_task(actor=self.creator, project=self.project, title="T", task_type="deploiement")
        self.assertEqual(task.task_type, "deploiement")
        with self.assertRaises(services.InvalidTransitionError):
            services.create_task(actor=self.creator, project=self.project, title="T", task_type="inconnu")

    def test_archived_type_not_selectable_but_still_resolved(self):
        self._grant(self.creator)
        task = services.create_task(actor=self.creator, project=self.project, title="T", task_type="test")
        test_type = TaskType.all_objects.get(team=self.team, key="test")
        services.archive_task_type(actor=self.creator, task_type=test_type)
        with self.assertRaises(services.InvalidTransitionError):
            services.create_task(actor=self.creator, project=self.project, title="T2", task_type="test")
        self.assertEqual(services.resolve_task_type(task.project, task.task_type), ("Test", "flask"))

    def test_last_active_type_cannot_be_archived(self):
        self._grant(self.creator)
        types = list(services.get_task_types(self.team))
        for task_type in types[:-1]:
            services.archive_task_type(actor=self.creator, task_type=task_type)
        with self.assertRaises(services.InvalidTransitionError):
            services.archive_task_type(actor=self.creator, task_type=types[-1])

    def test_rename_keeps_key(self):
        self._grant(self.creator)
        correction = TaskType.all_objects.get(team=self.team, key="correction")
        services.update_task_type_definition(actor=self.creator, task_type=correction, label="Bugfix", icon="bug")
        correction.refresh_from_db()
        self.assertEqual((correction.key, correction.label, correction.icon), ("correction", "Bugfix", "bug"))

    def test_individual_project_manager_manages_own_types(self):
        owner = User.objects.create_user(username="owner")
        project = Project.objects.create(name="Perso", project_type="individuel")
        ProjectMembership.objects.create(project=project, user=owner, role="chef_de_projet")
        services.create_task_type(actor=owner, scope=project, label="Réflexion", icon="lightbulb")
        with self.assertRaises(services.TaskPermissionError):
            services.create_task_type(actor=self.member, scope=project, label="Autre")


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
class TaskTypeApiTests(APITestCase):
    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def setUp(self):
        self.owner = User.objects.create_user(username="owner")
        self.project = Project.objects.create(name="Perso", project_type="individuel")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        ProjectMembership.objects.create(project=self.project, user=self.owner, role="chef_de_projet")

    def test_list_by_project_returns_scope_and_types(self):
        response = self.client.get("/api/v1/tasks/types/", {"project": str(self.project.id)}, **self.as_user(self.owner))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["scope"]["kind"], "project")
        self.assertTrue(body["can_manage"])
        self.assertEqual([t["key"] for t in body["types"]], ["correction", "ajout", "evolution", "test"])

    def test_create_rename_archive_restore(self):
        response = self.client.post(
            "/api/v1/tasks/types/",
            {"project": str(self.project.id), "label": "Étude", "icon": "search"},
            format="json",
            **self.as_user(self.owner),
        )
        self.assertEqual(response.status_code, 201)
        type_id = response.json()["id"]

        response = self.client.patch(
            f"/api/v1/tasks/types/{type_id}/", {"label": "Étude préalable"}, format="json", **self.as_user(self.owner)
        )
        self.assertEqual(response.json()["label"], "Étude préalable")

        response = self.client.post(f"/api/v1/tasks/types/{type_id}/archive/", **self.as_user(self.owner))
        self.assertEqual(response.json()["status"], "archived")
        response = self.client.post(f"/api/v1/tasks/types/{type_id}/restore/", **self.as_user(self.owner))
        self.assertEqual(response.json()["status"], "active")

    def test_task_serializer_exposes_custom_label_and_icon(self):
        services.create_task_type(actor=self.owner, scope=self.project, label="Réflexion", icon="lightbulb")
        Task.objects.create(project=self.project, version=self.version, title="T", task_type="reflexion")
        response = self.client.get("/api/v1/tasks/", {"project": str(self.project.id)}, **self.as_user(self.owner))
        item = response.json()[0]
        self.assertEqual((item["task_type_display"], item["task_type_icon"]), ("Réflexion", "lightbulb"))

    def test_create_task_with_unknown_type_is_400(self):
        response = self.client.post(
            "/api/v1/tasks/",
            {"project": str(self.project.id), "title": "T", "task_type": "inconnu"},
            format="json",
            **self.as_user(self.owner),
        )
        self.assertEqual(response.status_code, 400)

    def test_outsider_cannot_list(self):
        outsider = User.objects.create_user(username="outsider")
        response = self.client.get("/api/v1/tasks/types/", {"project": str(self.project.id)}, **self.as_user(outsider))
        self.assertEqual(response.status_code, 404)
