"""Plusieurs assignés sur une entrée de planning projet (session du
2026-10-05) — remplace l'ancien `assignee` unique par un M2M `assignees`."""

from django.test import TestCase

from apps.accounts.models import User
from apps.planning.models import ProjectPlanningEntry
from apps.planning.services import (
    PlanningValidationError,
    cancel_project_entry,
    create_project_entry,
    update_project_entry,
)
from apps.projects.models import Project, ProjectMembership


class ProjectEntryAssigneesServiceTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        self.mgr = User.objects.create(username="mgr", email="mgr@x.io")
        self.alice = User.objects.create(username="alice", email="alice@x.io")
        self.bob = User.objects.create(username="bob", email="bob@x.io")
        self.outsider = User.objects.create(username="outsider", email="outsider@x.io")
        ProjectMembership.objects.create(project=self.project, user=self.mgr, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.alice, role="membre")
        ProjectMembership.objects.create(project=self.project, user=self.bob, role="membre")

    def test_create_with_multiple_assignees(self):
        entry = create_project_entry(
            actor=self.mgr,
            project=self.project,
            title="Revue",
            start="2026-06-15T09:00:00+02:00",
            end="2026-06-15T10:00:00+02:00",
            assignees=[self.alice, self.bob],
        )
        self.assertEqual(set(entry.assignees.all()), {self.alice, self.bob})

    def test_create_rejects_assignee_outside_project(self):
        with self.assertRaises(PlanningValidationError):
            create_project_entry(
                actor=self.mgr,
                project=self.project,
                title="Revue",
                start="2026-06-15T09:00:00+02:00",
                end="2026-06-15T10:00:00+02:00",
                assignees=[self.outsider],
            )

    def test_update_can_add_and_remove_assignees(self):
        entry = create_project_entry(
            actor=self.mgr,
            project=self.project,
            title="Revue",
            start="2026-06-15T09:00:00+02:00",
            end="2026-06-15T10:00:00+02:00",
            assignees=[self.alice],
        )
        update_project_entry(actor=self.mgr, entry=entry, assignees=[self.bob])
        self.assertEqual(set(entry.assignees.all()), {self.bob})

    def test_update_without_assignees_key_leaves_assignees_untouched(self):
        entry = create_project_entry(
            actor=self.mgr,
            project=self.project,
            title="Revue",
            start="2026-06-15T09:00:00+02:00",
            end="2026-06-15T10:00:00+02:00",
            assignees=[self.alice],
        )
        update_project_entry(actor=self.mgr, entry=entry, title="Revue renommée")
        self.assertEqual(set(entry.assignees.all()), {self.alice})

    def test_entry_without_any_assignee_is_still_valid(self):
        entry = create_project_entry(
            actor=self.mgr,
            project=self.project,
            title="Jalon",
            start="2026-06-15T09:00:00+02:00",
            end="2026-06-15T10:00:00+02:00",
        )
        self.assertEqual(entry.assignees.count(), 0)

    def test_cancel_does_not_clear_assignees(self):
        entry = create_project_entry(
            actor=self.mgr,
            project=self.project,
            title="Revue",
            start="2026-06-15T09:00:00+02:00",
            end="2026-06-15T10:00:00+02:00",
            assignees=[self.alice],
        )
        cancel_project_entry(actor=self.mgr, entry=entry)
        entry.refresh_from_db()
        self.assertEqual(entry.status, "annule")
        self.assertEqual(set(entry.assignees.all()), {self.alice})


class ProjectEntryManagerRegressionTests(TestCase):
    """Même gotcha StatusLifecycleModel que `test_models.py` — vérifie que la
    nouvelle relation M2M `assignees` (côté `User.project_planning_entries`)
    voit bien les entrées annulées."""

    def test_reverse_relation_from_user_includes_cancelled_entries(self):
        project = Project.objects.create(name="P", project_type="collaboratif")
        user = User.objects.create(username="u")
        start, end = "2026-06-15T09:00:00+02:00", "2026-06-15T10:00:00+02:00"
        active = ProjectPlanningEntry.objects.create(project=project, title="A", start=start, end=end)
        active.assignees.add(user)
        cancelled = ProjectPlanningEntry.objects.create(
            project=project, title="B", start=start, end=end, status="annule"
        )
        cancelled.assignees.add(user)
        self.assertEqual(user.project_planning_entries.count(), 2)
