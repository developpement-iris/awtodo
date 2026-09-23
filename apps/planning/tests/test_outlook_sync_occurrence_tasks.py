"""Synchronisation Outlook d'une occurrence isolée d'une série (session du
2026-09-23, RECURRENCE-ID) — appels Graph mockés, pas de tenant réel dans
les tests. Voir apps/planning/graph_client.py pour le disclaimer "best
effort, non vérifié contre un vrai tenant" sur la résolution d'instance."""

from unittest.mock import patch

from django.test import TestCase
from django.utils.dateparse import parse_datetime

from apps.accounts.models import User
from apps.communication.models import O365Connection
from apps.planning.graph_client import GraphSyncError
from apps.planning.models import EventOccurrenceOutlookSync, EventParticipantOutlookSync
from apps.planning.services import add_participant, cancel_event_occurrence, create_event, update_event_occurrence
from apps.planning.tasks import (
    sync_event_occurrence_for_participant_outlook,
    sync_event_occurrence_to_all_participants_outlook,
    sync_event_occurrence_to_outlook,
)

OCCURRENCE = parse_datetime("2026-10-02T09:00:00+02:00")


class OutlookOccurrenceSyncTaskTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(username="occ-organizer", email="organizer@reparstores.com")
        self.event = create_event(
            actor=self.organizer,
            title="Daily",
            start=parse_datetime("2026-10-01T09:00:00+02:00"),
            end=parse_datetime("2026-10-01T09:15:00+02:00"),
            recurrence_rule="FREQ=DAILY;COUNT=5",
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

    @patch("apps.planning.tasks.upsert_graph_occurrence")
    def test_skips_if_series_not_synced_yet(self, mock_upsert):
        self._enable_sync(self.organizer)
        override = update_event_occurrence(
            actor=self.organizer, event=self.event, occurrence_start=OCCURRENCE, title="Exception"
        )
        sync_event_occurrence_to_outlook(str(override.id), "updated")
        mock_upsert.assert_not_called()

    @patch("apps.planning.tasks.upsert_graph_occurrence")
    def test_updates_occurrence_once_series_is_synced(self, mock_upsert):
        self._enable_sync(self.organizer)
        self.event.outlook_event_id = "series-master-id"
        self.event.save(update_fields=["outlook_event_id"])
        mock_upsert.return_value = "instance-id-1"
        override = update_event_occurrence(
            actor=self.organizer, event=self.event, occurrence_start=OCCURRENCE, title="Exception"
        )
        sync_event_occurrence_to_outlook(str(override.id), "updated")
        mock_upsert.assert_called_once()
        args = mock_upsert.call_args.args
        self.assertEqual(args[2], "series-master-id")
        sync_row = EventOccurrenceOutlookSync.objects.get(override=override, user=self.organizer)
        self.assertEqual(sync_row.outlook_event_id, "instance-id-1")

    @patch("apps.planning.tasks.delete_graph_occurrence")
    def test_cancelling_occurrence_deletes_the_instance(self, mock_delete):
        self._enable_sync(self.organizer)
        self.event.outlook_event_id = "series-master-id"
        self.event.save(update_fields=["outlook_event_id"])
        override = cancel_event_occurrence(actor=self.organizer, event=self.event, occurrence_start=OCCURRENCE)
        EventOccurrenceOutlookSync.objects.create(override=override, user=self.organizer, outlook_event_id="instance-1")
        sync_event_occurrence_to_outlook(str(override.id), "cancelled")
        mock_delete.assert_called_once()
        sync_row = EventOccurrenceOutlookSync.objects.get(override=override, user=self.organizer)
        self.assertEqual(sync_row.outlook_event_id, "")

    @patch("apps.planning.tasks.upsert_graph_occurrence")
    def test_graph_error_is_caught_not_raised(self, mock_upsert):
        self._enable_sync(self.organizer)
        self.event.outlook_event_id = "series-master-id"
        self.event.save(update_fields=["outlook_event_id"])
        mock_upsert.side_effect = GraphSyncError("échec simulé")
        override = update_event_occurrence(
            actor=self.organizer, event=self.event, occurrence_start=OCCURRENCE, title="Exception"
        )
        sync_event_occurrence_to_outlook(str(override.id), "updated")
        self.assertEqual(
            EventOccurrenceOutlookSync.objects.get(override=override, user=self.organizer).outlook_event_id, ""
        )

    @patch("apps.planning.tasks.upsert_graph_occurrence")
    def test_participant_occurrence_sync_uses_their_own_series_copy(self, mock_upsert):
        participant = User.objects.create_user(username="occ-participant", email="participant@reparstores.com")
        self._enable_sync(participant)
        add_participant(actor=self.organizer, event=self.event, user=participant)
        EventParticipantOutlookSync.objects.create(
            event=self.event, user=participant, outlook_event_id="participant-series-id"
        )
        mock_upsert.return_value = "participant-instance-id"
        override = update_event_occurrence(
            actor=self.organizer, event=self.event, occurrence_start=OCCURRENCE, title="Exception"
        )
        sync_event_occurrence_for_participant_outlook(str(override.id), str(participant.id), "updated")
        args = mock_upsert.call_args.args
        self.assertEqual(args[2], "participant-series-id")

    @patch("apps.planning.tasks.upsert_graph_occurrence")
    def test_participant_without_own_series_copy_is_skipped(self, mock_upsert):
        participant = User.objects.create_user(username="occ-participant-2", email="participant2@reparstores.com")
        self._enable_sync(participant)
        add_participant(actor=self.organizer, event=self.event, user=participant)
        # Pas de EventParticipantOutlookSync pour ce participant : sa série
        # n'a jamais été synchronisée, rien à cibler pour cette occurrence.
        override = update_event_occurrence(
            actor=self.organizer, event=self.event, occurrence_start=OCCURRENCE, title="Exception"
        )
        sync_event_occurrence_for_participant_outlook(str(override.id), str(participant.id), "updated")
        mock_upsert.assert_not_called()

    @patch("apps.planning.tasks.upsert_graph_occurrence")
    def test_fan_out_syncs_every_participant_with_a_series_copy(self, mock_upsert):
        p1 = User.objects.create_user(username="occ-p1", email="p1@reparstores.com")
        p2 = User.objects.create_user(username="occ-p2", email="p2@reparstores.com")
        self._enable_sync(p1)
        self._enable_sync(p2)
        add_participant(actor=self.organizer, event=self.event, user=p1)
        add_participant(actor=self.organizer, event=self.event, user=p2)
        EventParticipantOutlookSync.objects.create(event=self.event, user=p1, outlook_event_id="p1-series-id")
        EventParticipantOutlookSync.objects.create(event=self.event, user=p2, outlook_event_id="p2-series-id")
        mock_upsert.return_value = "instance-id"
        override = update_event_occurrence(
            actor=self.organizer, event=self.event, occurrence_start=OCCURRENCE, title="Exception"
        )
        sync_event_occurrence_to_all_participants_outlook(str(override.id), "updated")
        self.assertEqual(mock_upsert.call_count, 2)
