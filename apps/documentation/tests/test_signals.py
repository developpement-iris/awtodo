from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.documentation.models import DocSpace, PendingDocEntry
from apps.incidents import services as incident_services
from apps.incidents.models import Incident
from apps.notifications.models import Notification
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks import services as task_services
from apps.tasks.models import Task


class DocQueueSignalTests(TestCase):
    def setUp(self):
        self.mgr = User.objects.create(username="mgr")
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=self.project, user=self.mgr, role="chef_de_projet")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)

    def _complete_task(self, task_type):
        task = Task.objects.create(
            project=self.project,
            version=self.version,
            title=f"T {task_type}",
            task_type=task_type,
            status="en_cours",
            assignee=self.mgr,
        )
        task_services.complete_task(actor=self.mgr, task=task, time_spent=Decimal("1"))
        return task

    def _resolve_incident(self):
        incident = Incident.objects.create(
            project=self.project, title="Panne export", status="en_cours"
        )
        incident_services.resolve_incident(
            actor=self.mgr, incident=incident, resolution_comment="Corrigé.", time_spent=Decimal("1")
        )
        return incident

    def test_no_space_no_pending(self):
        self._complete_task("ajout")
        self._resolve_incident()
        self.assertEqual(PendingDocEntry.objects.count(), 0)

    def test_ajout_creates_feature_pending(self):
        DocSpace.objects.create(project=self.project)
        task = self._complete_task("ajout")
        self.assertEqual(
            PendingDocEntry.objects.filter(
                task=task, kind="fonctionnalite", status="en_attente"
            ).count(),
            1,
        )

    def test_evolution_creates_feature_pending(self):
        DocSpace.objects.create(project=self.project)
        self._complete_task("evolution")
        self.assertEqual(PendingDocEntry.objects.filter(kind="fonctionnalite").count(), 1)

    def test_correction_creates_nothing(self):
        DocSpace.objects.create(project=self.project)
        self._complete_task("correction")
        self.assertEqual(PendingDocEntry.objects.count(), 0)

    def test_resolved_incident_creates_resolution_pending(self):
        DocSpace.objects.create(project=self.project)
        incident = self._resolve_incident()
        self.assertEqual(
            PendingDocEntry.objects.filter(
                incident=incident, kind="resolution", status="en_attente"
            ).count(),
            1,
        )

    def test_ajout_notifies_project_manager(self):
        # Retour direct (session du 2026-09-23) : "envoie des notifs au chef
        # de projet".
        DocSpace.objects.create(project=self.project)
        task = self._complete_task("ajout")
        notif = Notification.objects.get(recipient=self.mgr, verb="doc_entry_pending")
        self.assertEqual(notif.task_id, task.id)

    def test_resolved_incident_notifies_project_manager(self):
        DocSpace.objects.create(project=self.project)
        incident = self._resolve_incident()
        notif = Notification.objects.get(recipient=self.mgr, verb="doc_entry_pending")
        self.assertEqual(notif.incident_id, incident.id)

    def test_notifies_every_active_manager(self):
        other_mgr = User.objects.create(username="mgr2")
        ProjectMembership.objects.create(project=self.project, user=other_mgr, role="chef_de_projet")
        DocSpace.objects.create(project=self.project)
        self._complete_task("ajout")
        self.assertEqual(Notification.objects.filter(verb="doc_entry_pending", recipient=self.mgr).count(), 1)
        self.assertEqual(Notification.objects.filter(verb="doc_entry_pending", recipient=other_mgr).count(), 1)

    def test_no_notification_without_space(self):
        self._complete_task("ajout")
        self.assertEqual(Notification.objects.filter(verb="doc_entry_pending").count(), 0)

    def test_correction_does_not_notify(self):
        DocSpace.objects.create(project=self.project)
        self._complete_task("correction")
        self.assertEqual(Notification.objects.filter(verb="doc_entry_pending").count(), 0)

    def test_signal_is_idempotent(self):
        DocSpace.objects.create(project=self.project)
        incident = Incident.objects.create(
            project=self.project, title="Panne", status="en_cours"
        )
        incident_services.resolve_incident(
            actor=self.mgr, incident=incident, resolution_comment="Corrigé.", time_spent=Decimal("1")
        )
        # Un second envoi manuel du signal ne doit pas créer un doublon.
        from apps.incidents.signals import incident_resolved

        incident_resolved.send(sender=Incident, incident=incident, actor=self.mgr)
        self.assertEqual(PendingDocEntry.objects.filter(incident=incident).count(), 1)
        # Pas de notification en double non plus — seule la création réelle
        # de la ligne (get_or_create) déclenche `_notify_project_managers`.
        self.assertEqual(Notification.objects.filter(verb="doc_entry_pending").count(), 1)
