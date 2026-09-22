"""Tâche Celery de synchronisation Outlook (session du 2026-09-22). Les
appels Microsoft Graph sont mockés — pas de tenant réel dans les tests."""

from unittest.mock import patch

from django.test import TestCase
from django.utils.dateparse import parse_datetime

from apps.accounts.models import User
from apps.communication.models import O365Connection
from apps.planning.graph_client import GraphSyncError
from apps.planning.services import cancel_event, create_event, update_event
from apps.planning.tasks import backfill_user_outlook_sync, sync_calendar_event_to_outlook


class OutlookSyncTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="outlook-sync-user", email="outlook-sync-user@reparstores.com")
        self.event = create_event(
            actor=self.user,
            title="Point équipe",
            start="2026-10-01T09:00:00+02:00",
            end="2026-10-01T10:00:00+02:00",
        )

    def _enable_sync(self):
        self.user.outlook_calendar_sync_enabled = True
        self.user.save(update_fields=["outlook_calendar_sync_enabled"])
        O365Connection.objects.create(
            organisation=self.user.organisation,
            tenant_id="tenant-1",
            client_id="client-1",
            client_secret="secret-1",
            is_enabled=True,
        )

    @patch("apps.planning.tasks.create_graph_event")
    def test_skips_when_owner_sync_disabled(self, mock_create):
        sync_calendar_event_to_outlook(str(self.event.id), "created")
        mock_create.assert_not_called()

    @patch("apps.planning.tasks.create_graph_event")
    def test_skips_when_o365_connection_not_enabled(self, mock_create):
        self.user.outlook_calendar_sync_enabled = True
        self.user.save(update_fields=["outlook_calendar_sync_enabled"])
        sync_calendar_event_to_outlook(str(self.event.id), "created")
        mock_create.assert_not_called()

    @patch("apps.planning.tasks.create_graph_event")
    def test_creates_event_and_stores_outlook_id(self, mock_create):
        self._enable_sync()
        mock_create.return_value = "graph-event-123"
        sync_calendar_event_to_outlook(str(self.event.id), "created")
        mock_create.assert_called_once()
        self.event.refresh_from_db()
        self.assertEqual(self.event.outlook_event_id, "graph-event-123")

    @patch("apps.planning.tasks.update_graph_event")
    def test_updates_existing_event(self, mock_update):
        self._enable_sync()
        self.event.outlook_event_id = "graph-event-123"
        self.event.save(update_fields=["outlook_event_id"])
        update_event(actor=self.user, event=self.event, title="Point équipe (déplacé)")
        sync_calendar_event_to_outlook(str(self.event.id), "updated")
        mock_update.assert_called_once()
        args = mock_update.call_args.args
        self.assertEqual(args[2], "graph-event-123")

    @patch("apps.planning.tasks.delete_graph_event")
    def test_cancel_deletes_and_clears_outlook_id(self, mock_delete):
        self._enable_sync()
        self.event.outlook_event_id = "graph-event-123"
        self.event.save(update_fields=["outlook_event_id"])
        cancel_event(actor=self.user, event=self.event)
        sync_calendar_event_to_outlook(str(self.event.id), "cancelled")
        mock_delete.assert_called_once()
        self.event.refresh_from_db()
        self.assertEqual(self.event.outlook_event_id, "")

    @patch("apps.planning.tasks.create_graph_event")
    def test_skips_recurring_event(self, mock_create):
        self._enable_sync()
        recurring = create_event(
            actor=self.user,
            title="Point hebdo",
            start=parse_datetime("2026-10-02T09:00:00+02:00"),
            end=parse_datetime("2026-10-02T10:00:00+02:00"),
            recurrence_rule="FREQ=WEEKLY;BYDAY=FR",
        )
        sync_calendar_event_to_outlook(str(recurring.id), "created")
        mock_create.assert_not_called()

    @patch("apps.planning.tasks.create_graph_event")
    def test_graph_error_is_caught_not_raised(self, mock_create):
        self._enable_sync()
        mock_create.side_effect = GraphSyncError("échec simulé")
        sync_calendar_event_to_outlook(str(self.event.id), "created")
        self.event.refresh_from_db()
        self.assertEqual(self.event.outlook_event_id, "")

    @patch("apps.planning.tasks.create_graph_event")
    def test_unknown_event_id_is_ignored(self, mock_create):
        sync_calendar_event_to_outlook("00000000-0000-0000-0000-000000000000", "created")
        mock_create.assert_not_called()


class OutlookBackfillTaskTests(TestCase):
    """Rattrapage des événements déjà existants à l'activation de la
    synchro (remonté directement : "ça synchronise pas mes événements déjà
    existants ?") — voir aussi apps.accounts.tests.test_account_access
    pour l'émission du signal côté préférences."""

    def setUp(self):
        self.user = User.objects.create_user(username="backfill-user", email="backfill-user@reparstores.com")
        self.user.outlook_calendar_sync_enabled = True
        self.user.save(update_fields=["outlook_calendar_sync_enabled"])
        O365Connection.objects.create(
            organisation=self.user.organisation,
            tenant_id="tenant-1",
            client_id="client-1",
            client_secret="secret-1",
            is_enabled=True,
        )

    @patch("apps.planning.tasks.create_graph_event")
    def test_backfills_existing_events_without_outlook_id(self, mock_create):
        mock_create.return_value = "graph-event-1"
        event_a = create_event(
            actor=self.user, title="A", start="2026-10-01T09:00:00+02:00", end="2026-10-01T10:00:00+02:00"
        )
        event_b = create_event(
            actor=self.user, title="B", start="2026-10-02T09:00:00+02:00", end="2026-10-02T10:00:00+02:00"
        )
        backfill_user_outlook_sync(str(self.user.id))
        self.assertEqual(mock_create.call_count, 2)
        event_a.refresh_from_db()
        event_b.refresh_from_db()
        self.assertEqual(event_a.outlook_event_id, "graph-event-1")
        self.assertEqual(event_b.outlook_event_id, "graph-event-1")

    @patch("apps.planning.tasks.create_graph_event")
    def test_skips_events_already_synced(self, mock_create):
        event = create_event(
            actor=self.user, title="A", start="2026-10-01T09:00:00+02:00", end="2026-10-01T10:00:00+02:00"
        )
        event.outlook_event_id = "already-synced"
        event.save(update_fields=["outlook_event_id"])
        backfill_user_outlook_sync(str(self.user.id))
        mock_create.assert_not_called()

    @patch("apps.planning.tasks.create_graph_event")
    def test_skips_recurring_and_cancelled_events(self, mock_create):
        create_event(
            actor=self.user,
            title="Récurrent",
            start=parse_datetime("2026-10-01T09:00:00+02:00"),
            end=parse_datetime("2026-10-01T10:00:00+02:00"),
            recurrence_rule="FREQ=WEEKLY;BYDAY=FR",
        )
        cancelled = create_event(
            actor=self.user, title="Annulé", start="2026-10-02T09:00:00+02:00", end="2026-10-02T10:00:00+02:00"
        )
        cancel_event(actor=self.user, event=cancelled)
        backfill_user_outlook_sync(str(self.user.id))
        mock_create.assert_not_called()

    @patch("apps.planning.tasks.create_graph_event")
    def test_no_events_is_a_no_op(self, mock_create):
        backfill_user_outlook_sync(str(self.user.id))
        mock_create.assert_not_called()
