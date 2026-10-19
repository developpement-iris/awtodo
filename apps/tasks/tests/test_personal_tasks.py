from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Organisation, User
from apps.projects.services import get_scoped_history
from apps.tasks.services import (
    InvalidTransitionError,
    TaskPermissionError,
    assign_task,
    cancel_task,
    complete_task,
    create_task,
    get_assigned_tasks_for_admin,
    get_task_permissions,
    rename_task,
    start_task,
    update_task_deadline,
    update_task_type,
)


class PersonalTaskServiceTests(TestCase):
    """Tâche sans projet (session du 2026-10-19) : privée au créateur,
    assignée d'office à lui, types par défaut uniquement."""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner-perso")
        self.other = User.objects.create_user(username="other-perso")

    def _create(self, **kwargs):
        return create_task(actor=self.owner, title="Préparer la réunion", task_type="ajout", **kwargs)

    def test_created_task_is_owned_and_assigned_to_creator(self):
        task = self._create()

        self.assertIsNone(task.project)
        self.assertIsNone(task.version)
        self.assertEqual(task.owner, self.owner)
        self.assertEqual(task.assignee, self.owner)
        self.assertEqual(task.status, "assignee")

    def test_assigning_to_someone_else_is_rejected(self):
        with self.assertRaises(InvalidTransitionError):
            self._create(assignee=self.other)

    def test_custom_task_type_is_rejected(self):
        with self.assertRaises(InvalidTransitionError):
            create_task(actor=self.owner, title="X", task_type="developpement")

    def test_service_account_must_give_a_project(self):
        service = User.objects.create_user(username="service-perso", is_service_account=True)

        with self.assertRaises(InvalidTransitionError):
            create_task(actor=service, title="X", task_type="ajout")

    def test_owner_runs_the_full_lifecycle(self):
        task = self._create()

        rename_task(actor=self.owner, task=task, title="Nouveau titre")
        update_task_deadline(actor=self.owner, task=task, deadline="2026-12-31")
        update_task_type(actor=self.owner, task=task, task_type="test")
        start_task(actor=self.owner, task=task)
        complete_task(actor=self.owner, task=task, time_spent="1.5")

        self.assertEqual(task.status, "archivee")
        self.assertEqual(task.task_type, "test")

    def test_owner_can_cancel(self):
        task = self._create()

        cancel_task(actor=self.owner, task=task, cancellation_reason="Plus utile")

        self.assertEqual(task.status, "annulee")

    def test_someone_else_cannot_touch_it(self):
        task = self._create()

        with self.assertRaises(TaskPermissionError):
            rename_task(actor=self.other, task=task, title="Piraté")
        with self.assertRaises(TaskPermissionError):
            start_task(actor=self.other, task=task)

    def test_cannot_be_reassigned(self):
        task = self._create()

        with self.assertRaises(InvalidTransitionError):
            assign_task(actor=self.owner, task=task, assignee=self.other)

    def test_permissions_flags(self):
        task = self._create()

        owner_flags = get_task_permissions(self.owner, task)
        self.assertTrue(owner_flags["can_rename"])
        self.assertTrue(owner_flags["can_start"])
        self.assertTrue(owner_flags["can_cancel"])
        self.assertFalse(owner_flags["can_assign"])
        self.assertFalse(owner_flags["can_validate"])
        self.assertFalse(any(get_task_permissions(self.other, task).values()))

    def test_hidden_from_admin_workload_view(self):
        admin = User.objects.create_user(username="admin-perso", organisation_role="admin")
        self._create()

        self.assertEqual(list(get_assigned_tasks_for_admin(actor=admin, target_user=self.owner)), [])


class PersonalTaskHistoryExportTests(TestCase):
    """Retour direct : les lignes d'audit d'une tâche personnelle sont
    retirées de l'export d'historique des autres, admin d'organisation
    compris — son propriétaire garde les siennes."""

    def setUp(self):
        self.org = Organisation.objects.create(name="Org perso")
        self.owner = User.objects.create_user(username="owner-hist-perso", organisation=self.org)
        self.admin = User.objects.create_user(
            username="admin-hist-perso", organisation=self.org, organisation_role="admin"
        )
        self.task = create_task(actor=self.owner, title="Secret", task_type="ajout")
        rename_task(actor=self.owner, task=self.task, title="Toujours secret")

    def _task_entries(self, actor):
        return [e for e in get_scoped_history(actor=actor) if e.object_id == self.task.id]

    def test_entries_are_marked_private(self):
        self.assertTrue(all(e.is_private for e in self._task_entries(self.owner)))

    def test_hidden_from_organisation_admin_export(self):
        self.assertEqual(self._task_entries(self.admin), [])

    def test_kept_in_owner_export(self):
        verbs = {e.verb for e in self._task_entries(self.owner)}
        self.assertEqual(verbs, {"created", "field_changed"})


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
class PersonalTaskApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner-perso-api")
        self.other = User.objects.create_user(username="other-perso-api")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def _create(self):
        return self.client.post(
            "/api/v1/tasks/", {"title": "Ma tâche", "task_type": "correction"}, format="json", **self.as_user(self.owner)
        )

    def test_create_without_project(self):
        response = self._create()

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIsNone(body["project"])
        self.assertIsNone(body["project_name"])
        self.assertIsNone(body["version_label"])
        self.assertEqual(body["status"], "assignee")
        self.assertEqual(body["task_type_display"], "Correction")

    def test_listed_for_owner_only(self):
        task_id = self._create().json()["id"]

        own = self.client.get("/api/v1/tasks/", **self.as_user(self.owner)).json()
        others = self.client.get("/api/v1/tasks/", **self.as_user(self.other)).json()

        self.assertIn(task_id, [t["id"] for t in own])
        self.assertNotIn(task_id, [t["id"] for t in others])
        self.assertEqual(
            self.client.get(f"/api/v1/tasks/{task_id}/", **self.as_user(self.other)).status_code, 404
        )

    def test_personal_filter(self):
        task_id = self._create().json()["id"]

        response = self.client.get("/api/v1/tasks/?personal=true", **self.as_user(self.owner))

        self.assertEqual([t["id"] for t in response.json()], [task_id])
