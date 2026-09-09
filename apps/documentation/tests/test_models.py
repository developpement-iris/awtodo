from django.test import TestCase

from apps.documentation.models import DocEntry, DocPage, DocSpace
from apps.projects.models import Project


class DocManagerRegressionTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        self.space = DocSpace.objects.create(project=self.project)

    def test_archived_page_hidden_from_default_manager(self):
        DocPage.objects.create(space=self.space, title="Vivante", slug="vivante")
        DocPage.all_objects.create(space=self.space, title="Vieille", slug="vieille", status="archive")
        self.assertEqual(DocPage.objects.count(), 1)
        self.assertEqual(DocPage.all_objects.count(), 2)

    def test_reverse_relation_uses_all_objects(self):
        DocPage.all_objects.create(space=self.space, title="A", slug="a", status="archive")
        self.assertEqual(self.space.pages.count(), 1)

    def test_docentry_managers(self):
        DocEntry.all_objects.create(space=self.space, kind="fonctionnalite", title="F", status="archive")
        self.assertEqual(DocEntry.objects.count(), 0)
        self.assertEqual(DocEntry.all_objects.count(), 1)
