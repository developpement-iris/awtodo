from django.test import TestCase

from apps.budgeting.models import BudgetEntry
from apps.projects.models import Project


class BudgetEntryTests(TestCase):
    def test_creation(self):
        project = Project.objects.create(name="Projet Test")

        entry = BudgetEntry.objects.create(project=project, hours="4.50", hourly_rate="65.00")

        self.assertEqual(BudgetEntry.objects.count(), 1)
        self.assertEqual(entry.project, project)
