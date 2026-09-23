"""Synchronisation Outlook (session du 2026-09-22, sens unique Awtodo →
Outlook). Vérifie que les signaux sont bien émis aux bons moments, et que le
récepteur planifie bien une tâche Celery après commit sans jamais lever
d'exception — voir `apps/planning/tests/test_outlook_sync_tasks.py` pour le
comportement de la tâche elle-même (appels Graph mockés)."""

from unittest.mock import patch

from django.dispatch import Signal
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.services import update_planning_preferences
from apps.planning.services import cancel_block, cancel_event, create_block, create_event, update_event
from apps.planning.signals import (
    calendar_event_cancelled,
    calendar_event_created,
    calendar_event_updated,
    scheduled_block_cancelled,
    scheduled_block_created,
)
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task


class _SignalCatcher:
    def __init__(self, signal: Signal):
        self.signal = signal
        self.received = []
        signal.connect(self._handler, weak=False)

    def _handler(self, sender, **kwargs):
        self.received.append(kwargs)

    def disconnect(self):
        self.signal.disconnect(self._handler)


class OutlookSyncSignalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="outlook-sync-user")

    def test_create_event_emits_calendar_event_created(self):
        catcher = _SignalCatcher(calendar_event_created)
        try:
            event = create_event(
                actor=self.user,
                title="Point équipe",
                start="2026-10-01T09:00:00+02:00",
                end="2026-10-01T10:00:00+02:00",
            )
            self.assertEqual(len(catcher.received), 1)
            self.assertEqual(catcher.received[0]["event"].id, event.id)
            self.assertEqual(catcher.received[0]["actor"], self.user)
        finally:
            catcher.disconnect()

    def test_update_event_emits_calendar_event_updated(self):
        event = create_event(
            actor=self.user,
            title="Point équipe",
            start="2026-10-01T09:00:00+02:00",
            end="2026-10-01T10:00:00+02:00",
        )
        catcher = _SignalCatcher(calendar_event_updated)
        try:
            update_event(actor=self.user, event=event, title="Point équipe (déplacé)")
            self.assertEqual(len(catcher.received), 1)
            self.assertEqual(catcher.received[0]["event"].id, event.id)
        finally:
            catcher.disconnect()

    def test_cancel_event_emits_calendar_event_cancelled(self):
        event = create_event(
            actor=self.user,
            title="Point équipe",
            start="2026-10-01T09:00:00+02:00",
            end="2026-10-01T10:00:00+02:00",
        )
        catcher = _SignalCatcher(calendar_event_cancelled)
        try:
            cancel_event(actor=self.user, event=event)
            self.assertEqual(len(catcher.received), 1)
            self.assertEqual(catcher.received[0]["event"].id, event.id)
        finally:
            catcher.disconnect()

    def test_default_receivers_never_raise_without_o365_config(self):
        # Aucune `O365Connection` configurée pour l'organisation de l'acteur,
        # `outlook_calendar_sync_enabled` toujours False par défaut sur
        # `User` — la tâche planifiée après commit doit se contenter de ne
        # rien faire, jamais lever.
        with self.captureOnCommitCallbacks(execute=True):
            event = create_event(
                actor=self.user,
                title="Point équipe",
                start="2026-10-01T09:00:00+02:00",
                end="2026-10-01T10:00:00+02:00",
            )
        with self.captureOnCommitCallbacks(execute=True):
            update_event(actor=self.user, event=event, title="Renommé")
        with self.captureOnCommitCallbacks(execute=True):
            cancel_event(actor=self.user, event=event)
        event.refresh_from_db()
        self.assertEqual(event.outlook_event_id, "")

    @patch("apps.planning.tasks.backfill_user_outlook_sync.delay")
    def test_activating_sync_schedules_backfill_after_commit(self, mock_delay):
        with self.captureOnCommitCallbacks(execute=True):
            update_planning_preferences(actor=self.user, outlook_calendar_sync_enabled=True)
        mock_delay.assert_called_once_with(str(self.user.id))

    @patch("apps.planning.tasks.backfill_user_outlook_sync.delay")
    def test_reactivating_sync_does_not_reschedule_backfill(self, mock_delay):
        with self.captureOnCommitCallbacks(execute=True):
            update_planning_preferences(actor=self.user, outlook_calendar_sync_enabled=True)
        mock_delay.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            update_planning_preferences(actor=self.user, outlook_calendar_sync_enabled=True)
        mock_delay.assert_not_called()


class ScheduledBlockOutlookSyncSignalTests(TestCase):
    """Créneaux de tâche (session du 2026-09-23) — mêmes vérifications que
    pour les événements libres, sur `scheduled_block_*`."""

    def setUp(self):
        self.user = User.objects.create_user(username="block-sync-user")
        project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=project, user=self.user, role="membre")
        version = ProjectVersion.objects.create(project=project, label="v1", is_current=True)
        self.task = Task.objects.create(
            project=project, version=version, title="Corriger le formulaire", task_type="correction", assignee=self.user
        )

    def _window(self):
        start = timezone.now()
        return start, start + timezone.timedelta(hours=1)

    def test_create_block_emits_scheduled_block_created(self):
        catcher = _SignalCatcher(scheduled_block_created)
        try:
            start, end = self._window()
            block = create_block(actor=self.user, task=self.task, start=start, end=end)
            self.assertEqual(len(catcher.received), 1)
            self.assertEqual(catcher.received[0]["block"].id, block.id)
        finally:
            catcher.disconnect()

    def test_cancel_block_emits_scheduled_block_cancelled(self):
        start, end = self._window()
        block = create_block(actor=self.user, task=self.task, start=start, end=end)
        catcher = _SignalCatcher(scheduled_block_cancelled)
        try:
            cancel_block(actor=self.user, block=block)
            self.assertEqual(len(catcher.received), 1)
            self.assertEqual(catcher.received[0]["block"].id, block.id)
        finally:
            catcher.disconnect()

    def test_default_receiver_never_raises_without_o365_config(self):
        start, end = self._window()
        with self.captureOnCommitCallbacks(execute=True):
            block = create_block(actor=self.user, task=self.task, start=start, end=end)
        with self.captureOnCommitCallbacks(execute=True):
            cancel_block(actor=self.user, block=block)
        self.assertEqual(block.outlook_syncs.count(), 0)
