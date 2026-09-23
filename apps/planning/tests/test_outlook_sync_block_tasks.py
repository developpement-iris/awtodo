"""Synchronisation Outlook des créneaux de tâche/incident (session du
2026-09-23) — un créneau se synchronise sur le calendrier Outlook du
propriétaire ET de chaque personne à qui il a partagé son calendrier, à
condition que cette personne ait elle-même activé son opt-in. Appels Graph
mockés, pas de tenant réel dans les tests."""

from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.communication.models import O365Connection
from apps.planning.graph_client import GraphSyncError
from apps.planning.models import BlockOutlookSync, CalendarShare
from apps.planning.services import cancel_block, create_block, create_share
from apps.planning.tasks import backfill_user_outlook_sync, sync_scheduled_block_to_outlook
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task


class OutlookBlockSyncTaskTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="block-owner", email="owner@reparstores.com")
        self.grantee = User.objects.create_user(username="block-grantee", email="grantee@reparstores.com")
        project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=project, user=self.owner, role="membre")
        version = ProjectVersion.objects.create(project=project, label="v1", is_current=True)
        self.task = Task.objects.create(
            project=project, version=version, title="Corriger le formulaire", task_type="correction", assignee=self.owner
        )
        start = timezone.now()
        self.block = create_block(actor=self.owner, task=self.task, start=start, end=start + timezone.timedelta(hours=1))

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

    @patch("apps.planning.tasks.create_graph_block_event")
    def test_syncs_owner_when_owner_has_opted_in(self, mock_create):
        self._enable_sync(self.owner)
        mock_create.return_value = "graph-block-owner"
        sync_scheduled_block_to_outlook(str(self.block.id), "created")
        mock_create.assert_called_once()
        sync_row = BlockOutlookSync.objects.get(block=self.block, user=self.owner)
        self.assertEqual(sync_row.outlook_event_id, "graph-block-owner")

    @patch("apps.planning.tasks.create_graph_block_event")
    def test_event_title_is_task_title(self, mock_create):
        self._enable_sync(self.owner)
        mock_create.return_value = "graph-block-owner"
        sync_scheduled_block_to_outlook(str(self.block.id), "created")
        block_arg = mock_create.call_args.args[2]
        self.assertEqual(block_arg.task.title, "Corriger le formulaire")

    @patch("apps.planning.tasks.create_graph_block_event")
    def test_shared_grantee_with_opt_in_also_synced(self, mock_create):
        self._enable_sync(self.owner)
        self._enable_sync(self.grantee)
        create_share(actor=self.owner, grantee=self.grantee)
        mock_create.return_value = "graph-block-id"
        sync_scheduled_block_to_outlook(str(self.block.id), "created")
        self.assertEqual(mock_create.call_count, 2)
        self.assertTrue(BlockOutlookSync.objects.filter(block=self.block, user=self.owner).exists())
        self.assertTrue(BlockOutlookSync.objects.filter(block=self.block, user=self.grantee).exists())

    @patch("apps.planning.tasks.create_graph_block_event")
    def test_shared_grantee_without_opt_in_is_not_synced(self, mock_create):
        self._enable_sync(self.owner)
        create_share(actor=self.owner, grantee=self.grantee)
        mock_create.return_value = "graph-block-id"
        sync_scheduled_block_to_outlook(str(self.block.id), "created")
        mock_create.assert_called_once()
        self.assertFalse(BlockOutlookSync.objects.filter(block=self.block, user=self.grantee).exists())

    @patch("apps.planning.tasks.create_graph_block_event")
    def test_revoked_share_excludes_grantee(self, mock_create):
        self._enable_sync(self.owner)
        self._enable_sync(self.grantee)
        share = create_share(actor=self.owner, grantee=self.grantee)
        share.status = "revoked"
        share.save(update_fields=["status", "updated_at"])
        mock_create.return_value = "graph-block-id"
        sync_scheduled_block_to_outlook(str(self.block.id), "created")
        mock_create.assert_called_once()
        self.assertFalse(BlockOutlookSync.objects.filter(block=self.block, user=self.grantee).exists())

    @patch("apps.planning.tasks.update_graph_block_event")
    def test_updates_existing_sync_row(self, mock_update):
        self._enable_sync(self.owner)
        BlockOutlookSync.objects.create(block=self.block, user=self.owner, outlook_event_id="already-there")
        sync_scheduled_block_to_outlook(str(self.block.id), "updated")
        mock_update.assert_called_once()
        args = mock_update.call_args.args
        self.assertEqual(args[2], "already-there")

    @patch("apps.planning.tasks.delete_graph_event")
    def test_cancel_deletes_and_clears_id(self, mock_delete):
        self._enable_sync(self.owner)
        BlockOutlookSync.objects.create(block=self.block, user=self.owner, outlook_event_id="already-there")
        cancel_block(actor=self.owner, block=self.block)
        sync_scheduled_block_to_outlook(str(self.block.id), "cancelled")
        mock_delete.assert_called_once()
        sync_row = BlockOutlookSync.objects.get(block=self.block, user=self.owner)
        self.assertEqual(sync_row.outlook_event_id, "")

    @patch("apps.planning.tasks.create_graph_block_event")
    def test_one_recipient_failure_does_not_block_the_other(self, mock_create):
        self._enable_sync(self.owner)
        self._enable_sync(self.grantee)
        create_share(actor=self.owner, grantee=self.grantee)

        def side_effect(connection, upn, block):
            if upn == self.owner.email:
                raise GraphSyncError("échec simulé")
            return "graph-block-grantee"

        mock_create.side_effect = side_effect
        sync_scheduled_block_to_outlook(str(self.block.id), "created")
        self.assertFalse(BlockOutlookSync.objects.get(block=self.block, user=self.owner).outlook_event_id)
        self.assertEqual(
            BlockOutlookSync.objects.get(block=self.block, user=self.grantee).outlook_event_id, "graph-block-grantee"
        )

    @patch("apps.planning.tasks.create_graph_block_event")
    def test_unknown_block_id_is_ignored(self, mock_create):
        sync_scheduled_block_to_outlook("00000000-0000-0000-0000-000000000000", "created")
        mock_create.assert_not_called()


class OutlookBlockBackfillTests(TestCase):
    """Le backfill à l'activation couvre aussi les créneaux — les siens et
    ceux des personnes qui ont partagé leur calendrier avec l'utilisateur
    (voir apps.planning.tasks.backfill_user_outlook_sync)."""

    def setUp(self):
        self.owner = User.objects.create_user(username="backfill-owner", email="owner2@reparstores.com")
        self.grantee = User.objects.create_user(username="backfill-grantee", email="grantee2@reparstores.com")
        project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=project, user=self.owner, role="membre")
        version = ProjectVersion.objects.create(project=project, label="v1", is_current=True)
        self.task = Task.objects.create(
            project=project, version=version, title="Tâche", task_type="correction", assignee=self.owner
        )
        start = timezone.now()
        self.block = create_block(actor=self.owner, task=self.task, start=start, end=start + timezone.timedelta(hours=1))
        O365Connection.objects.get_or_create(
            organisation=self.owner.organisation,
            defaults={
                "tenant_id": "tenant-1",
                "client_id": "client-1",
                "client_secret": "secret-1",
                "is_enabled": True,
            },
        )

    @patch("apps.planning.tasks.create_graph_block_event")
    def test_backfill_syncs_shared_blocks_when_grantee_activates(self, mock_create):
        # Le partage existait déjà avant que le destinataire n'active son
        # opt-in — le propriétaire, lui, n'a jamais activé le sien.
        create_share(actor=self.owner, grantee=self.grantee)
        self.grantee.outlook_calendar_sync_enabled = True
        self.grantee.save(update_fields=["outlook_calendar_sync_enabled"])
        mock_create.return_value = "graph-block-id"

        backfill_user_outlook_sync(str(self.grantee.id))

        mock_create.assert_called_once()
        self.assertEqual(
            BlockOutlookSync.objects.get(block=self.block, user=self.grantee).outlook_event_id, "graph-block-id"
        )
        self.assertFalse(BlockOutlookSync.objects.filter(block=self.block, user=self.owner).exists())
