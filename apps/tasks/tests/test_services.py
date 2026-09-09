from django.test import TestCase

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task
from apps.tasks.services import (
    InvalidTransitionError,
    TaskPermissionError,
    assign_task,
    claim_task,
    complete_task,
    create_task,
    reject_task,
    rename_task,
    start_task,
    update_task_description,
    validate_task,
)


class TaskServicesTestCase(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.manager = User.objects.create_user(username="manager")
        self.member = User.objects.create_user(username="member")
        self.other_member = User.objects.create_user(username="other_member")
        self.outsider = User.objects.create_user(username="outsider")

        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        ProjectMembership.objects.create(project=self.project, user=self.other_member, role="membre")

    def make_task(self, status="en_attente_validation", assignee=None):
        return Task.objects.create(
            project=self.project,
            version=self.version,
            title="Corriger le bug",
            task_type="correction",
            status=status,
            assignee=assignee,
        )


class CreateTaskTests(TaskServicesTestCase):
    def test_member_creates_task_pending_validation(self):
        task = create_task(actor=self.member, project=self.project, title="Titre", task_type="correction")

        self.assertEqual(task.status, "en_attente_validation")
        self.assertIsNone(task.assignee)

    def test_manager_creates_task_without_assignee_is_available(self):
        task = create_task(actor=self.manager, project=self.project, title="Titre", task_type="ajout")

        self.assertEqual(task.status, "disponible")

    def test_manager_creates_task_with_assignee_is_assigned(self):
        task = create_task(
            actor=self.manager,
            project=self.project,
            title="Titre",
            task_type="ajout",
            assignee=self.member,
        )

        self.assertEqual(task.status, "assignee")
        self.assertEqual(task.assignee, self.member)

    def test_external_reference_id_is_optional(self):
        task = create_task(actor=self.member, project=self.project, title="Titre", task_type="correction")

        self.assertIsNone(task.external_reference_id)

    def test_non_member_cannot_create_task(self):
        with self.assertRaises(TaskPermissionError):
            create_task(actor=self.outsider, project=self.project, title="Titre", task_type="correction")


class ValidateTaskTests(TaskServicesTestCase):
    def test_manager_validates_without_assignee(self):
        task = self.make_task("en_attente_validation")

        validate_task(actor=self.manager, task=task)

        self.assertEqual(task.status, "disponible")

    def test_manager_validates_with_assignee(self):
        task = self.make_task("en_attente_validation")

        validate_task(actor=self.manager, task=task, assignee=self.member)

        self.assertEqual(task.status, "assignee")
        self.assertEqual(task.assignee, self.member)

    def test_member_cannot_validate(self):
        task = self.make_task("en_attente_validation")

        with self.assertRaises(TaskPermissionError):
            validate_task(actor=self.member, task=task)

    def test_cannot_validate_from_wrong_status(self):
        task = self.make_task("disponible")

        with self.assertRaises(InvalidTransitionError):
            validate_task(actor=self.manager, task=task)


class RejectTaskTests(TaskServicesTestCase):
    def test_manager_rejects_with_reason(self):
        task = self.make_task("en_attente_validation")

        reject_task(actor=self.manager, task=task, rejection_reason="Hors périmètre")

        self.assertEqual(task.status, "rejetee")
        self.assertEqual(task.rejection_reason, "Hors périmètre")

    def test_reject_requires_reason(self):
        task = self.make_task("en_attente_validation")

        with self.assertRaises(InvalidTransitionError):
            reject_task(actor=self.manager, task=task, rejection_reason="")

    def test_member_cannot_reject(self):
        task = self.make_task("en_attente_validation")

        with self.assertRaises(TaskPermissionError):
            reject_task(actor=self.member, task=task, rejection_reason="Non merci")

    def test_cannot_reject_from_wrong_status(self):
        task = self.make_task("disponible")

        with self.assertRaises(InvalidTransitionError):
            reject_task(actor=self.manager, task=task, rejection_reason="Trop tard")


class ClaimTaskTests(TaskServicesTestCase):
    def test_member_claims_available_task(self):
        task = self.make_task("disponible")

        claim_task(actor=self.member, task=task)

        self.assertEqual(task.status, "assignee")
        self.assertEqual(task.assignee, self.member)

    def test_outsider_cannot_claim(self):
        task = self.make_task("disponible")

        with self.assertRaises(TaskPermissionError):
            claim_task(actor=self.outsider, task=task)

    def test_cannot_claim_from_wrong_status(self):
        task = self.make_task("en_attente_validation")

        with self.assertRaises(InvalidTransitionError):
            claim_task(actor=self.member, task=task)


class AssignTaskTests(TaskServicesTestCase):
    def test_manager_assigns_available_task(self):
        task = self.make_task("disponible")

        assign_task(actor=self.manager, task=task, assignee=self.member)

        self.assertEqual(task.status, "assignee")
        self.assertEqual(task.assignee, self.member)

    def test_manager_reassigns_already_assigned_task(self):
        task = self.make_task("assignee", assignee=self.member)

        assign_task(actor=self.manager, task=task, assignee=self.other_member)

        self.assertEqual(task.assignee, self.other_member)

    def test_member_cannot_assign(self):
        task = self.make_task("disponible")

        with self.assertRaises(TaskPermissionError):
            assign_task(actor=self.member, task=task, assignee=self.other_member)

    def test_cannot_assign_to_non_member(self):
        task = self.make_task("disponible")

        with self.assertRaises(InvalidTransitionError):
            assign_task(actor=self.manager, task=task, assignee=self.outsider)

    def test_assign_requires_assignee(self):
        task = self.make_task("disponible")

        with self.assertRaises(InvalidTransitionError):
            assign_task(actor=self.manager, task=task, assignee=None)

    def test_cannot_assign_from_wrong_status(self):
        task = self.make_task("en_attente_validation")

        with self.assertRaises(InvalidTransitionError):
            assign_task(actor=self.manager, task=task, assignee=self.member)


class StartTaskTests(TaskServicesTestCase):
    def test_assignee_starts_task(self):
        task = self.make_task("assignee", assignee=self.member)

        start_task(actor=self.member, task=task)

        self.assertEqual(task.status, "en_cours")

    def test_non_assignee_cannot_start(self):
        task = self.make_task("assignee", assignee=self.member)

        with self.assertRaises(TaskPermissionError):
            start_task(actor=self.other_member, task=task)

    def test_cannot_start_from_wrong_status(self):
        task = self.make_task("disponible", assignee=self.member)

        with self.assertRaises(InvalidTransitionError):
            start_task(actor=self.member, task=task)


class CompleteTaskTests(TaskServicesTestCase):
    def test_assignee_completes_task(self):
        task = self.make_task("en_cours", assignee=self.member)

        complete_task(actor=self.member, task=task, time_spent="3.5")
        task.refresh_from_db()

        self.assertEqual(task.status, "archivee")
        self.assertEqual(str(task.time_spent), "3.50")

    def test_non_assignee_cannot_complete(self):
        task = self.make_task("en_cours", assignee=self.member)

        with self.assertRaises(TaskPermissionError):
            complete_task(actor=self.other_member, task=task, time_spent="1")

    def test_manager_completes_task_not_assigned_to_them(self):
        task = self.make_task("en_cours", assignee=self.member)

        complete_task(actor=self.manager, task=task, time_spent="4")
        task.refresh_from_db()

        self.assertEqual(task.status, "archivee")
        self.assertEqual(str(task.time_spent), "4.00")

    def test_complete_requires_time_spent(self):
        task = self.make_task("en_cours", assignee=self.member)

        with self.assertRaises(InvalidTransitionError):
            complete_task(actor=self.member, task=task, time_spent=None)

    def test_complete_rejects_non_numeric_time_spent(self):
        task = self.make_task("en_cours", assignee=self.member)

        with self.assertRaises(InvalidTransitionError):
            complete_task(actor=self.member, task=task, time_spent="beaucoup")

    def test_cannot_complete_from_wrong_status(self):
        task = self.make_task("assignee", assignee=self.member)

        with self.assertRaises(InvalidTransitionError):
            complete_task(actor=self.member, task=task, time_spent="2")


class RenameTaskTests(TaskServicesTestCase):
    def test_member_renames_task(self):
        task = self.make_task("disponible")

        rename_task(actor=self.member, task=task, title="Nouveau titre")

        self.assertEqual(task.title, "Nouveau titre")

    def test_rename_trims_whitespace(self):
        task = self.make_task("disponible")

        rename_task(actor=self.member, task=task, title="  Titre avec espaces  ")

        self.assertEqual(task.title, "Titre avec espaces")

    def test_outsider_cannot_rename(self):
        task = self.make_task("disponible")

        with self.assertRaises(TaskPermissionError):
            rename_task(actor=self.outsider, task=task, title="Nouveau titre")

    def test_rename_rejects_empty_title(self):
        task = self.make_task("disponible")

        with self.assertRaises(InvalidTransitionError):
            rename_task(actor=self.member, task=task, title="   ")


class UpdateTaskDescriptionTests(TaskServicesTestCase):
    def test_member_updates_description(self):
        task = self.make_task("disponible")

        update_task_description(actor=self.member, task=task, description="Nouvelle description")

        self.assertEqual(task.description, "Nouvelle description")

    def test_update_trims_whitespace(self):
        task = self.make_task("disponible")

        update_task_description(actor=self.member, task=task, description="  avec espaces  ")

        self.assertEqual(task.description, "avec espaces")

    def test_empty_description_is_allowed(self):
        task = self.make_task("disponible")

        update_task_description(actor=self.member, task=task, description="")

        self.assertEqual(task.description, "")

    def test_outsider_cannot_update_description(self):
        task = self.make_task("disponible")

        with self.assertRaises(TaskPermissionError):
            update_task_description(actor=self.outsider, task=task, description="Nouvelle description")
