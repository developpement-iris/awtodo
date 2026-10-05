"""Synchronisation Outlook des entrées de planning projet (session du
2026-10-05) — une entrée créée sur le planning d'un projet, qui se pose sur
le planning personnel de chaque assigné, doit maintenant se synchroniser sur
l'Outlook de ceux qui ont activé leur synchro (seuls les assignés, pas tout
le projet). Appels Graph mockés, pas de tenant réel dans les tests.

`captureOnCommitCallbacks(execute=True)` est nécessaire autour de chaque
appel qui déclenche un signal : les récepteurs planifient la tâche via
`transaction.on_commit`, qui ne s'exécute pas tout seul dans un `TestCase`
classique (bloc atomique jamais réellement commité) — même pattern que
`test_outlook_sync_signals.py`/`test_outlook_sync_participant_tasks.py`."""

from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import User
from apps.communication.models import O365Connection
from apps.planning.graph_client import GraphSyncError
from apps.planning.models import ProjectPlanningEntryOutlookSync
from apps.planning.services import cancel_project_entry, create_project_entry, update_project_entry
from apps.planning.tasks import (
    backfill_user_outlook_sync,
    sync_project_entry_assignee_to_outlook,
    sync_project_entry_to_all_assignees_outlook,
)
from apps.projects.models import Project, ProjectMembership


class OutlookProjectEntryAssigneeSyncTaskTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        self.mgr = User.objects.create_user(username="mgr", email="mgr@reparstores.com")
        self.alice = User.objects.create_user(username="alice", email="alice@reparstores.com")
        self.bob = User.objects.create_user(username="bob", email="bob@reparstores.com")
        ProjectMembership.objects.create(project=self.project, user=self.mgr, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.alice, role="membre")
        ProjectMembership.objects.create(project=self.project, user=self.bob, role="membre")
        self.entry = create_project_entry(
            actor=self.mgr,
            project=self.project,
            title="Revue de sprint",
            start="2026-10-10T09:00:00+02:00",
            end="2026-10-10T10:00:00+02:00",
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

    @patch("apps.planning.tasks.create_graph_project_entry_event")
    def test_skips_when_assignee_has_not_opted_in(self, mock_create):
        with self.captureOnCommitCallbacks(execute=True):
            update_project_entry(actor=self.mgr, entry=self.entry, assignees=[self.alice])
        mock_create.assert_not_called()

    @patch("apps.planning.tasks.create_graph_project_entry_event")
    def test_creates_assignee_copy_on_assignment_and_stores_id(self, mock_create):
        self._enable_sync(self.alice)
        mock_create.return_value = "graph-entry-alice"
        with self.captureOnCommitCallbacks(execute=True):
            update_project_entry(actor=self.mgr, entry=self.entry, assignees=[self.alice])
        mock_create.assert_called_once()
        sync_row = ProjectPlanningEntryOutlookSync.objects.get(entry=self.entry, user=self.alice)
        self.assertEqual(sync_row.outlook_event_id, "graph-entry-alice")

    @patch("apps.planning.tasks.create_graph_project_entry_event")
    def test_only_assignees_are_synced_not_other_project_members(self, mock_create):
        # Bob est membre du projet (donc voit l'entrée dans son planning
        # personnel via get_calendar) mais n'est PAS assigné — pas de copie
        # Outlook pour lui.
        self._enable_sync(self.alice)
        self._enable_sync(self.bob)
        mock_create.return_value = "graph-entry-alice"
        with self.captureOnCommitCallbacks(execute=True):
            update_project_entry(actor=self.mgr, entry=self.entry, assignees=[self.alice])
        mock_create.assert_called_once()
        self.assertFalse(ProjectPlanningEntryOutlookSync.objects.filter(entry=self.entry, user=self.bob).exists())

    @patch("apps.planning.tasks.create_graph_project_entry_event")
    def test_assignees_added_at_creation_are_synced(self, mock_create):
        self._enable_sync(self.alice)
        mock_create.return_value = "graph-entry-alice"
        with self.captureOnCommitCallbacks(execute=True):
            entry = create_project_entry(
                actor=self.mgr,
                project=self.project,
                title="Jalon",
                start="2026-10-12T09:00:00+02:00",
                end="2026-10-12T10:00:00+02:00",
                assignees=[self.alice],
            )
        mock_create.assert_called_once()
        sync_row = ProjectPlanningEntryOutlookSync.objects.get(entry=entry, user=self.alice)
        self.assertEqual(sync_row.outlook_event_id, "graph-entry-alice")

    @patch("apps.planning.tasks.update_graph_project_entry_event")
    def test_content_update_follows_to_existing_assignee_copy(self, mock_update):
        self._enable_sync(self.alice)
        with self.captureOnCommitCallbacks(execute=True):
            update_project_entry(actor=self.mgr, entry=self.entry, assignees=[self.alice])
        ProjectPlanningEntryOutlookSync.objects.filter(entry=self.entry, user=self.alice).update(
            outlook_event_id="already-there"
        )
        with self.captureOnCommitCallbacks(execute=True):
            update_project_entry(actor=self.mgr, entry=self.entry, title="Revue renommée")
        mock_update.assert_called_once()
        self.assertEqual(mock_update.call_args.args[2], "already-there")

    @patch("apps.planning.tasks.delete_graph_event")
    @patch("apps.planning.tasks.create_graph_project_entry_event")
    def test_removing_assignee_deletes_and_clears_id(self, mock_create, mock_delete):
        self._enable_sync(self.alice)
        mock_create.return_value = "already-there"
        with self.captureOnCommitCallbacks(execute=True):
            update_project_entry(actor=self.mgr, entry=self.entry, assignees=[self.alice])
        with self.captureOnCommitCallbacks(execute=True):
            update_project_entry(actor=self.mgr, entry=self.entry, assignees=[])
        mock_delete.assert_called_once()
        sync_row = ProjectPlanningEntryOutlookSync.objects.get(entry=self.entry, user=self.alice)
        self.assertEqual(sync_row.outlook_event_id, "")

    @patch("apps.planning.tasks.delete_graph_event")
    @patch("apps.planning.tasks.create_graph_project_entry_event")
    def test_cancelling_entry_deletes_copy_for_every_assignee(self, mock_create, mock_delete):
        self._enable_sync(self.alice)
        self._enable_sync(self.bob)
        mock_create.side_effect = ["graph-a", "graph-b"]
        with self.captureOnCommitCallbacks(execute=True):
            update_project_entry(actor=self.mgr, entry=self.entry, assignees=[self.alice, self.bob])

        with self.captureOnCommitCallbacks(execute=True):
            cancel_project_entry(actor=self.mgr, entry=self.entry)
        self.assertEqual(mock_delete.call_count, 2)

    @patch("apps.planning.tasks.create_graph_project_entry_event")
    def test_graph_error_for_one_assignee_does_not_raise(self, mock_create):
        self._enable_sync(self.alice)
        mock_create.side_effect = GraphSyncError("échec simulé")
        with self.captureOnCommitCallbacks(execute=True):
            update_project_entry(actor=self.mgr, entry=self.entry, assignees=[self.alice])
        sync_row = ProjectPlanningEntryOutlookSync.objects.get(entry=self.entry, user=self.alice)
        self.assertEqual(sync_row.outlook_event_id, "")

    @patch("apps.planning.tasks.create_graph_project_entry_event")
    def test_fan_out_syncs_each_current_assignee_independently(self, mock_create):
        self._enable_sync(self.alice)
        self._enable_sync(self.bob)
        # Les deux assignés posés SANS laisser les hooks `on_commit`
        # s'exécuter (pas de `captureOnCommitCallbacks`) — aucune copie
        # Outlook n'existe encore, pour tester `sync_project_entry_to_all_
        # assignees_outlook` elle-même, pas l'ajout individuel.
        update_project_entry(actor=self.mgr, entry=self.entry, assignees=[self.alice, self.bob])

        def side_effect(connection, upn, entry):
            if upn == self.alice.email:
                raise GraphSyncError("échec simulé")
            return "graph-entry-bob"

        mock_create.side_effect = side_effect
        sync_project_entry_to_all_assignees_outlook(str(self.entry.id), "created")
        self.assertEqual(
            ProjectPlanningEntryOutlookSync.objects.get(entry=self.entry, user=self.alice).outlook_event_id, ""
        )
        self.assertEqual(
            ProjectPlanningEntryOutlookSync.objects.get(entry=self.entry, user=self.bob).outlook_event_id,
            "graph-entry-bob",
        )

    @patch("apps.planning.tasks.create_graph_project_entry_event")
    def test_backfill_syncs_entries_the_user_is_already_assigned_to(self, mock_create):
        with self.captureOnCommitCallbacks(execute=True):
            update_project_entry(actor=self.mgr, entry=self.entry, assignees=[self.alice])
        self._enable_sync(self.alice)
        mock_create.return_value = "graph-entry-alice"

        backfill_user_outlook_sync(str(self.alice.id))

        mock_create.assert_called_once()
        sync_row = ProjectPlanningEntryOutlookSync.objects.get(entry=self.entry, user=self.alice)
        self.assertEqual(sync_row.outlook_event_id, "graph-entry-alice")

    @patch("apps.planning.tasks.create_graph_project_entry_event")
    def test_recipient_opt_in_alone_governs_sync_regardless_of_actor(self, mock_create):
        # Le chef de projet (actor) n'a pas activé sa propre synchro — sans
        # rapport, seul l'opt-in du destinataire compte.
        self._enable_sync(self.alice)
        mock_create.return_value = "graph-entry-alice"
        with self.captureOnCommitCallbacks(execute=True):
            update_project_entry(actor=self.mgr, entry=self.entry, assignees=[self.alice])
        mock_create.assert_called_once()

    def test_direct_task_call_skips_silently_when_entry_missing(self):
        sync_project_entry_assignee_to_outlook("00000000-0000-0000-0000-000000000000", str(self.alice.id), "created")
        self.assertFalse(ProjectPlanningEntryOutlookSync.objects.exists())
