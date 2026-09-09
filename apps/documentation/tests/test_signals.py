from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.documentation.models import DocSpace, PendingDocEntry
from apps.incidents import services as incident_services
from apps.incidents.models import Incident
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
        incident_services.resolve_incident(actor=self.mgr, incident=incident)
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

    def test_signal_is_idempotent(self):
        DocSpace.objects.create(project=self.project)
        incident = Incident.objects.create(
            project=self.project, title="Panne", status="en_cours"
        )
        incident_services.resolve_incident(actor=self.mgr, incident=incident)
        # Un second envoi manuel du signal ne doit pas créer un doublon.
        from apps.incidents.signals import incident_resolved

        incident_resolved.send(sender=Incident, incident=incident, actor=self.mgr)
        self.assertEqual(PendingDocEntry.objects.filter(incident=incident).count(), 1)
