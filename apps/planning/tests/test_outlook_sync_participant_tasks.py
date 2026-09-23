"""Synchronisation Outlook d'un événement partagé avec des participants
(session du 2026-09-23) — à distinguer explicitement du partage de
calendrier (`CalendarShare`), qui ne synchronise jamais rien côté Outlook.
Appels Graph mockés, pas de tenant réel dans les tests."""

from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import User
from apps.communication.models import O365Connection
from apps.planning.graph_client import GraphSyncError
from apps.planning.models import EventParticipantOutlookSync
from apps.planning.services import add_participant, create_event, remove_participant, update_event
from apps.planning.tasks import (
    backfill_user_outlook_sync,
    sync_event_participant_to_outlook,
    sync_event_to_all_participants_outlook,
)


class OutlookEventParticipantSyncTaskTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(username="organizer", email="organizer@reparstores.com")
        self.participant = User.objects.create_user(username="participant", email="participant@reparstores.com")
        self.event = create_event(
            actor=self.organizer,
            title="Point équipe",
            start="2026-10-01T09:00:00+02:00",
            end="2026-10-01T10:00:00+02:00",
        )

    def _enable_sync(self, user):
        user.outlook_calendar_sync_enabled = True
        user.save(update_fields=["outlook_calendar_sync_enabled"])
        O365Connection.objects.get_or_create(
            organisation=user.organisation,
            defaults={
                "tenant_id": "tenant-1",
                "client_id": "client-1",
                "client_secret": "secret-1",
                "is_enabled": True,
            },
        )

    @patch("apps.planning.tasks.create_graph_event")
    def test_skips_when_participant_has_not_opted_in(self, mock_create):
        sync_event_participant_to_outlook(str(self.event.id), str(self.participant.id), "created")
        mock_create.assert_not_called()

    @patch("apps.planning.tasks.create_graph_event")
    def test_creates_participant_copy_and_stores_id(self, mock_create):
        self._enable_sync(self.participant)
        mock_create.return_value = "graph-event-participant"
        sync_event_participant_to_outlook(str(self.event.id), str(self.participant.id), "created")
        mock_create.assert_called_once()
        sync_row = EventParticipantOutlookSync.objects.get(event=self.event, user=self.participant)
        self.assertEqual(sync_row.outlook_event_id, "graph-event-participant")

    @patch("apps.planning.tasks.create_graph_event")
    def test_organizer_own_opt_in_does_not_affect_participant_copy(self, mock_create):
        # L'organisateur n'a PAS activé son opt-in, seul le participant l'a
        # fait — sa copie à lui doit quand même se synchroniser.
        self._enable_sync(self.participant)
        mock_create.return_value = "graph-event-participant"
        sync_event_participant_to_outlook(str(self.event.id), str(self.participant.id), "created")
        mock_create.assert_called_once()

    @patch("apps.planning.tasks.update_graph_event")
    def test_updates_existing_participant_copy(self, mock_update):
        self._enable_sync(self.participant)
        EventParticipantOutlookSync.objects.create(
            event=self.event, user=self.participant, outlook_event_id="already-there"
        )
        sync_event_participant_to_outlook(str(self.event.id), str(self.participant.id), "updated")
        mock_update.assert_called_once()
        self.assertEqual(mock_update.call_args.args[2], "already-there")

    @patch("apps.planning.tasks.delete_graph_event")
    def test_removing_participant_deletes_and_clears_id(self, mock_delete):
        self._enable_sync(self.participant)
        participant = add_participant(actor=self.organizer, event=self.event, user=self.participant)
        EventParticipantOutlookSync.objects.create(
            event=self.event, user=self.participant, outlook_event_id="already-there"
        )
        remove_participant(actor=self.organizer, participant=participant)
        sync_event_participant_to_outlook(str(self.event.id), str(self.participant.id), "cancelled")
        mock_delete.assert_called_once()
        sync_row = EventParticipantOutlookSync.objects.get(event=self.event, user=self.participant)
        self.assertEqual(sync_row.outlook_event_id, "")

    @patch("apps.planning.tasks.create_graph_event")
    def test_graph_error_for_one_participant_does_not_raise(self, mock_create):
        self._enable_sync(self.participant)
        mock_create.side_effect = GraphSyncError("échec simulé")
        sync_event_participant_to_outlook(str(self.event.id), str(self.participant.id), "created")
        sync_row = EventParticipantOutlookSync.objects.get(event=self.event, user=self.participant)
        self.assertEqual(sync_row.outlook_event_id, "")

    @patch("apps.planning.tasks.create_graph_event")
    def test_fan_out_syncs_every_active_participant_independently(self, mock_create):
        other = User.objects.create_user(username="other-participant", email="other@reparstores.com")
        self._enable_sync(self.participant)
        self._enable_sync(other)
        add_participant(actor=self.organizer, event=self.event, user=self.participant)
        add_participant(actor=self.organizer, event=self.event, user=other)

        def side_effect(connection, upn, event):
            if upn == self.participant.email:
                raise GraphSyncError("échec simulé")
            return "graph-event-other"

        mock_create.side_effect = side_effect
        sync_event_to_all_participants_outlook(str(self.event.id), "updated")
        self.assertEqual(
            EventParticipantOutlookSync.objects.get(event=self.event, user=self.participant).outlook_event_id, ""
        )
        self.assertEqual(
            EventParticipantOutlookSync.objects.get(event=self.event, user=other).outlook_event_id,
            "graph-event-other",
        )

    @patch("apps.planning.tasks.create_graph_event")
    def test_fan_out_ignores_removed_participants(self, mock_create):
        self._enable_sync(self.participant)
        participant = add_participant(actor=self.organizer, event=self.event, user=self.participant)
        remove_participant(actor=self.organizer, participant=participant)
        mock_create.reset_mock()
        sync_event_to_all_participants_outlook(str(self.event.id), "updated")
        mock_create.assert_not_called()

    @patch("apps.planning.tasks.create_graph_event")
    def test_backfill_syncs_events_the_user_is_invited_to(self, mock_create):
        add_participant(actor=self.organizer, event=self.event, user=self.participant)
        self._enable_sync(self.participant)
        mock_create.return_value = "graph-event-participant"

        backfill_user_outlook_sync(str(self.participant.id))

        mock_create.assert_called_once()
        sync_row = EventParticipantOutlookSync.objects.get(event=self.event, user=self.participant)
        self.assertEqual(sync_row.outlook_event_id, "graph-event-participant")
