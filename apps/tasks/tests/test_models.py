from django.test import TestCase

from apps.projects.models import Project, ProjectVersion
from apps.tasks.models import Task


class TaskActiveManagerTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)

    def test_active_manager_filters_by_status(self):
        task = Task.objects.create(project=self.project, version=self.version, title="Corriger le bug", task_type="correction")

        self.assertIn(task, Task.objects.active())
        self.assertIn(task, Task.objects.all())

        task.status = "archivee"
        task.save()

        self.assertNotIn(task, Task.objects.active())
        self.assertNotIn(task, Task.objects.all())
        self.assertIn(task, Task.all_objects.all())
