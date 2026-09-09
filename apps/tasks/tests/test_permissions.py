from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership, ProjectVersion

from .. import services
from ..models import Task


class TaskPermissionFlagsServiceTests(TestCase):
    """Voir CLAUDE.md > "Permissions API — flags calculés" : chaque flag doit
    refléter exactement la même règle que la transition réelle correspondante
    (même fonction de garde, voir services.py)."""

    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.manager = User.objects.create_user(username="manager-perm")
        self.member = User.objects.create_user(username="member-perm")
        self.outsider = User.objects.create_user(username="outsider-perm")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def make_task(self, status="en_attente_validation", assignee=None):
        return Task.objects.create(
            project=self.project, version=self.version, title="Tâche", task_type="correction", status=status, assignee=assignee
        )

    def test_pending_validation_task_flags_for_manager(self):
        task = self.make_task("en_attente_validation")

        flags = services.get_task_permissions(self.manager, task)

        self.assertTrue(flags["can_validate"])
        self.assertTrue(flags["can_reject"])
        self.assertFalse(flags["can_claim"])
        self.assertFalse(flags["can_assign"])
        self.assertFalse(flags["can_start"])
        self.assertFalse(flags["can_complete"])
        self.assertTrue(flags["can_rename"])
        # `can_edit_description` reprend exactement la même garde que
        # `can_rename` (voir get_task_permissions) — toujours identique.
        self.assertEqual(flags["can_edit_description"], flags["can_rename"])

    def test_pending_validation_task_flags_for_member(self):
        task = self.make_task("en_attente_validation")

        flags = services.get_task_permissions(self.member, task)

        self.assertFalse(flags["can_validate"])
        self.assertFalse(flags["can_reject"])
        self.assertTrue(flags["can_rename"])

    def test_available_task_flags_for_member(self):
        task = self.make_task("disponible")

        flags = services.get_task_permissions(self.member, task)

        self.assertTrue(flags["can_claim"])
        self.assertFalse(flags["can_assign"])

    def test_available_task_flags_for_manager(self):
        task = self.make_task("disponible")

        flags = services.get_task_permissions(self.manager, task)

        self.assertTrue(flags["can_assign"])
        # Un chef de projet est aussi membre du projet : rien dans la règle
        # de `claim` (_require_member) ne l'exclut — il peut s'auto-attribuer
        # une tâche disponible comme n'importe quel membre.
        self.assertTrue(flags["can_claim"])

    def test_assigned_task_flags_only_true_for_assignee(self):
        task = self.make_task("assignee", assignee=self.member)

        assignee_flags = services.get_task_permissions(self.member, task)
        manager_flags = services.get_task_permissions(self.manager, task)

        self.assertTrue(assignee_flags["can_start"])
        self.assertFalse(manager_flags["can_start"])

    def test_in_progress_task_flags_true_for_assignee_and_manager(self):
        # Un chef de projet peut clôturer une tâche en cours même si elle
        # n'est pas assignée à lui-même — remonté par le client, voir
        # `_ensure_can_complete` (services.py).
        task = self.make_task("en_cours", assignee=self.member)

        assignee_flags = services.get_task_permissions(self.member, task)
        manager_flags = services.get_task_permissions(self.manager, task)

        self.assertTrue(assignee_flags["can_complete"])
        self.assertTrue(manager_flags["can_complete"])

    def test_in_progress_task_flags_false_for_unrelated_member(self):
        other_member = User.objects.create_user(username="other-member-perm")
        ProjectMembership.objects.create(project=self.project, user=other_member, role="membre")
        task = self.make_task("en_cours", assignee=self.member)

        other_flags = services.get_task_permissions(other_member, task)

        self.assertFalse(other_flags["can_complete"])

    def test_outsider_has_every_flag_false(self):
        task = self.make_task("disponible")

        flags = services.get_task_permissions(self.outsider, task)

        self.assertFalse(any(flags.values()))

    def test_anonymous_has_every_flag_false(self):
        task = self.make_task("disponible")

        flags = services.get_task_permissions(None, task)

        self.assertFalse(any(flags.values()))

    def test_flag_matches_real_transition_outcome(self):
        # Le flag n'est pas une règle parallèle : si `can_validate` est vrai,
        # l'appel réel doit réussir ; s'il est faux, l'appel réel doit lever.
        task = self.make_task("en_attente_validation")
        self.assertTrue(services.can_validate_task(self.manager, task))
        services.validate_task(actor=self.manager, task=task)  # ne lève pas

        task2 = self.make_task("en_attente_validation")
        self.assertFalse(services.can_validate_task(self.member, task2))
        with self.assertRaises(services.TaskPermissionError):
            services.validate_task(actor=self.member, task=task2)


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
class TaskPermissionFlagsApiTests(APITestCase):
    def test_task_response_includes_permissions_object(self):
        project = Project.objects.create(name="Projet Test")
        version = ProjectVersion.objects.create(project=project, label="v1", is_current=True)
        manager = User.objects.create_user(username="manager-perm-api")
        ProjectMembership.objects.create(project=project, user=manager, role="chef_de_projet")
        task = Task.objects.create(
            project=project, version=version, title="Tâche", task_type="correction", status="en_attente_validation"
        )

        response = self.client.get(f"/api/v1/tasks/{task.id}/", HTTP_X_DEBUG_USER_ID=str(manager.id))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["permissions"]["can_validate"])
