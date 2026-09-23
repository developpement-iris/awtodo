"""Synchronisation Outlook des créneaux de tâche/incident (session du
2026-09-23) — un seul destinataire possible, le propriétaire du créneau
(pas de partage pour les tâches planifiées, tranché avec l'utilisateur).
Appels Graph mockés, pas de tenant réel dans les tests."""

from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.communication.models import O365Connection
from apps.planning.graph_client import GraphSyncError
from apps.planning.services import cancel_block, create_block
from apps.planning.tasks import backfill_user_outlook_sync, sync_scheduled_block_to_outlook
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task


class OutlookBlockSyncTaskTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="block-owner", email="owner@reparstores.com")
        project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=project, user=self.owner, role="membre")
        version = ProjectVersion.objects.create(project=project, label="v1", is_current=True)
        self.task = Task.objects.create(
            project=project, version=version, title="Corriger le formulaire", task_type="correction", assignee=self.owner
        )
        start = timezone.now()
        self.block = create_block(actor=self.owner, task=self.task, start=start, end=start + timezone.timedelta(hours=1))

    def _enable_sync(self):
        self.owner.outlook_calendar_sync_enabled = True
        self.owner.save(update_fields=["outlook_calendar_sync_enabled"])
        O365Connection.objects.create(
            organisation=self.owner.organisation,
            tenant_id="tenant-1",
            client_id="client-1",
            client_secret="secret-1",
            is_enabled=True,
        )

    @patch("apps.planning.tasks.create_graph_block_event")
    def test_skips_when_owner_sync_disabled(self, mock_create):
        sync_scheduled_block_to_outlook(str(self.block.id), "created")
        mock_create.assert_not_called()

    @patch("apps.planning.tasks.create_graph_block_event")
    def test_creates_block_and_stores_outlook_id(self, mock_create):
        self._enable_sync()
        mock_create.return_value = "graph-block-1"
        sync_scheduled_block_to_outlook(str(self.block.id), "created")
        mock_create.assert_called_once()
        self.block.refresh_from_db()
        self.assertEqual(self.block.outlook_event_id, "graph-block-1")

    @patch("apps.planning.tasks.create_graph_block_event")
    def test_event_title_is_task_title(self, mock_create):
        self._enable_sync()
        mock_create.return_value = "graph-block-1"
        sync_scheduled_block_to_outlook(str(self.block.id), "created")
        block_arg = mock_create.call_args.args[2]
        self.assertEqual(block_arg.task.title, "Corriger le formulaire")

    @patch("apps.planning.tasks.update_graph_block_event")
    def test_updates_existing_block(self, mock_update):
        self._enable_sync()
        self.block.outlook_event_id = "already-there"
        self.block.save(update_fields=["outlook_event_id"])
        sync_scheduled_block_to_outlook(str(self.block.id), "updated")
        mock_update.assert_called_once()
        self.assertEqual(mock_update.call_args.args[2], "already-there")

    @patch("apps.planning.tasks.delete_graph_event")
    def test_cancel_deletes_and_clears_id(self, mock_delete):
        self._enable_sync()
        self.block.outlook_event_id = "already-there"
        self.block.save(update_fields=["outlook_event_id"])
        cancel_block(actor=self.owner, block=self.block)
        sync_scheduled_block_to_outlook(str(self.block.id), "cancelled")
        mock_delete.assert_called_once()
        self.block.refresh_from_db()
        self.assertEqual(self.block.outlook_event_id, "")

    @patch("apps.planning.tasks.create_graph_block_event")
    def test_graph_error_is_caught_not_raised(self, mock_create):
        self._enable_sync()
        mock_create.side_effect = GraphSyncError("échec simulé")
        sync_scheduled_block_to_outlook(str(self.block.id), "created")
        self.block.refresh_from_db()
        self.assertEqual(self.block.outlook_event_id, "")

    @patch("apps.planning.tasks.create_graph_block_event")
    def test_unknown_block_id_is_ignored(self, mock_create):
        sync_scheduled_block_to_outlook("00000000-0000-0000-0000-000000000000", "created")
        mock_create.assert_not_called()

    @patch("apps.planning.tasks.create_graph_block_event")
    def test_backfill_syncs_owners_blocks(self, mock_create):
        self.owner.outlook_calendar_sync_enabled = True
        self.owner.save(update_fields=["outlook_calendar_sync_enabled"])
        O365Connection.objects.create(
            organisation=self.owner.organisation,
            tenant_id="tenant-1",
            client_id="client-1",
            client_secret="secret-1",
            is_enabled=True,
        )
        mock_create.return_value = "graph-block-1"
        backfill_user_outlook_sync(str(self.owner.id))
        mock_create.assert_called_once()
        self.block.refresh_from_db()
        self.assertEqual(self.block.outlook_event_id, "graph-block-1")
