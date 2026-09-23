"""Synchronisation Outlook (session du 2026-09-22, sens unique Awtodo →
Outlook). Vérifie que les signaux sont bien émis aux bons moments, et que le
récepteur planifie bien une tâche Celery après commit sans jamais lever
d'exception — voir `apps/planning/tests/test_outlook_sync_tasks.py` pour le
comportement de la tâche elle-même (appels Graph mockés)."""

from unittest.mock import patch

from django.dispatch import Signal
from django.test import TestCase
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.accounts.models import User
from apps.accounts.services import update_planning_preferences
from apps.planning.services import (
    add_participant,
    cancel_block,
    cancel_event,
    cancel_event_occurrence,
    create_block,
    create_event,
    remove_participant,
    update_event,
    update_event_occurrence,
)
from apps.planning.signals import (
    calendar_event_cancelled,
    calendar_event_created,
    calendar_event_occurrence_cancelled,
    calendar_event_occurrence_updated,
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
        block.refresh_from_db()
        self.assertEqual(block.outlook_event_id, "")


class EventParticipantOutlookSyncSignalTests(TestCase):
    """Événement partagé avec un participant (session du 2026-09-23) — à
    distinguer du partage de calendrier `CalendarShare`, qui ne déclenche
    jamais aucune synchro Outlook."""

    def setUp(self):
        self.organizer = User.objects.create_user(username="organizer")
        self.participant = User.objects.create_user(username="participant")
        self.event = create_event(
            actor=self.organizer,
            title="Point équipe",
            start="2026-10-01T09:00:00+02:00",
            end="2026-10-01T10:00:00+02:00",
        )

    @patch("apps.planning.tasks.sync_event_participant_to_outlook.delay")
    def test_inviting_participant_schedules_their_sync(self, mock_delay):
        with self.captureOnCommitCallbacks(execute=True):
            add_participant(actor=self.organizer, event=self.event, user=self.participant)
        mock_delay.assert_called_once_with(str(self.event.id), str(self.participant.id), "created")

    @patch("apps.planning.tasks.sync_event_participant_to_outlook.delay")
    def test_removing_participant_schedules_cancellation(self, mock_delay):
        participant = add_participant(actor=self.organizer, event=self.event, user=self.participant)
        mock_delay.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            remove_participant(actor=self.organizer, participant=participant)
        mock_delay.assert_called_once_with(str(self.event.id), str(self.participant.id), "cancelled")

    @patch("apps.planning.tasks.sync_event_to_all_participants_outlook.delay")
    def test_updating_event_fans_out_to_participants(self, mock_delay):
        with self.captureOnCommitCallbacks(execute=True):
            update_event(actor=self.organizer, event=self.event, title="Renommé")
        mock_delay.assert_called_once_with(str(self.event.id), "updated")

    @patch("apps.planning.tasks.sync_event_participant_to_outlook.delay")
    def test_adding_participants_at_creation_schedules_their_sync(self, mock_delay):
        # Session du 2026-09-23 : ajouter des participants dès la création
        # de l'événement, pas seulement après coup — doit déclencher
        # exactement le même signal par participant qu'un ajout classique.
        other = User.objects.create_user(username="participant-2")
        with self.captureOnCommitCallbacks(execute=True):
            event = create_event(
                actor=self.organizer,
                title="Revue de sprint",
                start="2026-10-02T09:00:00+02:00",
                end="2026-10-02T10:00:00+02:00",
                participant_ids=[self.participant, other],
            )
        self.assertEqual(mock_delay.call_count, 2)
        mock_delay.assert_any_call(str(event.id), str(self.participant.id), "created")
        mock_delay.assert_any_call(str(event.id), str(other.id), "created")

    @patch("apps.planning.tasks.sync_event_participant_to_outlook.delay")
    def test_organizer_in_participant_ids_at_creation_is_skipped(self, mock_delay):
        with self.captureOnCommitCallbacks(execute=True):
            create_event(
                actor=self.organizer,
                title="Revue de sprint",
                start="2026-10-02T09:00:00+02:00",
                end="2026-10-02T10:00:00+02:00",
                participant_ids=[self.organizer],
            )
        mock_delay.assert_not_called()

    @patch("apps.planning.tasks.sync_event_to_all_participants_outlook.delay")
    def test_cancelling_event_fans_out_to_participants(self, mock_delay):
        with self.captureOnCommitCallbacks(execute=True):
            cancel_event(actor=self.organizer, event=self.event)
        mock_delay.assert_called_once_with(str(self.event.id), "cancelled")


class EventOccurrenceOutlookSyncSignalTests(TestCase):
    """Occurrence unique d'une série (session du 2026-09-23, RECURRENCE-ID)
    — les signaux dédiés se déclenchent, jamais ceux de la série entière."""

    def setUp(self):
        self.organizer = User.objects.create_user(username="occurrence-organizer")
        self.event = create_event(
            actor=self.organizer,
            title="Daily",
            start=parse_datetime("2026-10-01T09:00:00+02:00"),
            end=parse_datetime("2026-10-01T09:15:00+02:00"),
            recurrence_rule="FREQ=DAILY;COUNT=5",
        )

    @patch("apps.planning.tasks.sync_event_occurrence_to_all_participants_outlook.delay")
    @patch("apps.planning.tasks.sync_event_occurrence_to_outlook.delay")
    def test_updating_one_occurrence_schedules_occurrence_sync(self, mock_owner_delay, mock_participants_delay):
        with self.captureOnCommitCallbacks(execute=True):
            override = update_event_occurrence(
                actor=self.organizer,
                event=self.event,
                occurrence_start=parse_datetime("2026-10-02T09:00:00+02:00"),
                title="Daily (exceptionnel)",
            )
        mock_owner_delay.assert_called_once_with(str(override.id), "updated")
        mock_participants_delay.assert_called_once_with(str(override.id), "updated")

    @patch("apps.planning.tasks.sync_event_occurrence_to_all_participants_outlook.delay")
    @patch("apps.planning.tasks.sync_event_occurrence_to_outlook.delay")
    def test_cancelling_one_occurrence_schedules_occurrence_sync(self, mock_owner_delay, mock_participants_delay):
        with self.captureOnCommitCallbacks(execute=True):
            override = cancel_event_occurrence(
                actor=self.organizer,
                event=self.event,
                occurrence_start=parse_datetime("2026-10-03T09:00:00+02:00"),
            )
        mock_owner_delay.assert_called_once_with(str(override.id), "cancelled")
        mock_participants_delay.assert_called_once_with(str(override.id), "cancelled")

    @patch("apps.planning.tasks.sync_calendar_event_to_outlook.delay")
    def test_updating_one_occurrence_does_not_schedule_whole_series_sync(self, mock_series_delay):
        with self.captureOnCommitCallbacks(execute=True):
            update_event_occurrence(
                actor=self.organizer,
                event=self.event,
                occurrence_start=parse_datetime("2026-10-02T09:00:00+02:00"),
                title="Daily (exceptionnel)",
            )
        mock_series_delay.assert_not_called()
