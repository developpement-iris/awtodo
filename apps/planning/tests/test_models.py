from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.incidents.models import Incident
from apps.planning.models import (
    CalendarEvent,
    CalendarShare,
    EventParticipant,
    ProjectPlanningEntry,
    ScheduledBlock,
)
from apps.projects.models import Project
from apps.tasks.models import Task


def _window():
    now = timezone.now()
    return now, now + timedelta(hours=1)


class StatusLifecycleManagerRegressionTests(TestCase):
    """Piège Django documenté dans CLAUDE.md : sans `default_manager_name` /
    `base_manager_name` explicites sur chaque modèle concret, les relations
    inverses masquent silencieusement les objets en statut terminal."""

    def setUp(self):
        self.user = User.objects.create(username="u")
        self.other = User.objects.create(username="o")
        self.project = Project.objects.create(name="P", project_type="collaboratif")

    def test_calendar_event_reverse_relation_includes_cancelled(self):
        start, end = _window()
        CalendarEvent.objects.create(owner=self.user, title="A", start=start, end=end)
        CalendarEvent.objects.create(owner=self.user, title="B", start=start, end=end, status="annule")
        self.assertEqual(self.user.calendar_events.count(), 2)

    def test_event_participant_reverse_relation_includes_removed(self):
        start, end = _window()
        event = CalendarEvent.objects.create(owner=self.user, title="A", start=start, end=end)
        EventParticipant.objects.create(event=event, user=self.other)
        EventParticipant.all_objects.create(event=event, user=self.other, status="removed")
        self.assertEqual(event.participants.count(), 2)

    def test_scheduled_block_reverse_relation_includes_cancelled(self):
        start, end = _window()
        from apps.projects.models import ProjectVersion

        version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        task = Task.objects.create(
            project=self.project, version=version, title="T", task_type="ajout", assignee=self.user
        )
        ScheduledBlock.objects.create(owner=self.user, task=task, start=start, end=end)
        ScheduledBlock.objects.create(
            owner=self.user, task=task, start=start, end=end, status="annule"
        )
        self.assertEqual(self.user.scheduled_blocks.count(), 2)

    def test_project_planning_entry_reverse_relation_includes_cancelled(self):
        start, end = _window()
        ProjectPlanningEntry.objects.create(project=self.project, title="J", start=start, end=end)
        ProjectPlanningEntry.objects.create(
            project=self.project, title="K", start=start, end=end, status="annule"
        )
        self.assertEqual(self.project.planning_entries.count(), 2)

    def test_calendar_share_reverse_relation_includes_revoked(self):
        CalendarShare.objects.create(owner=self.user, grantee=self.other)
        CalendarShare.objects.create(
            owner=self.user, grantee=User.objects.create(username="x"), status="revoked"
        )
        self.assertEqual(self.user.calendar_shares_granted.count(), 2)

    def test_active_manager_excludes_terminal(self):
        start, end = _window()
        CalendarEvent.objects.create(owner=self.user, title="A", start=start, end=end)
        CalendarEvent.objects.create(owner=self.user, title="B", start=start, end=end, status="annule")
        self.assertEqual(CalendarEvent.objects.count(), 1)
        self.assertEqual(CalendarEvent.all_objects.count(), 2)
