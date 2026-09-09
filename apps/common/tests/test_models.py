from django.test import TestCase

from apps.projects.models import Project, ProjectVersion
from apps.tasks.models import Task


class StatusLifecycleReverseRelationTests(TestCase):
    """Régression : sans `base_manager_name = "all_objects"` sur
    `StatusLifecycleModel`, Django utilise le manager filtré (`objects`)
    comme manager de base, et les relations inverses (`project.tasks.all()`)
    masquent silencieusement les objets archivés/rejetés — contraire à la
    règle "aucune suppression physique, historique permanent"."""

    def test_reverse_relation_includes_archived_objects(self):
        project = Project.objects.create(name="Projet Test")
        version = ProjectVersion.objects.create(project=project, label="v1", is_current=True)
        Task.objects.create(project=project, version=version, title="Active", task_type="correction", status="disponible")
        Task.objects.create(project=project, version=version, title="Archivée", task_type="correction", status="archivee")

        self.assertEqual(project.tasks.all().count(), 2)
        self.assertEqual(project.tasks.filter(status="archivee").count(), 1)
