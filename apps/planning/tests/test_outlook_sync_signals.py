"""Synchronisation Outlook (session du 2026-09-22, sens unique Awtodo →
Outlook). Vérifie que les signaux sont bien émis aux bons moments, et que le
récepteur planifie bien une tâche Celery après commit sans jamais lever
d'exception — voir `apps/planning/tests/test_outlook_sync_tasks.py` pour le
comportement de la tâche elle-même (appels Graph mockés)."""

from unittest.mock import patch

from django.dispatch import Signal
from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.services import update_planning_preferences
from apps.planning.services import cancel_event, create_event, update_event
from apps.planning.signals import calendar_event_cancelled, calendar_event_created, calendar_event_updated


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
