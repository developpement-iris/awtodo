from django.test import TestCase

from apps.accounts.models import Team
from apps.evaluations import catalog
from apps.evaluations.defaults import DEFAULT_CATALOG
from apps.evaluations.models import CatalogQuestion

from .factories import make_individual_project, make_team_project


class CatalogSeedingTests(TestCase):
    def test_new_team_gets_default_catalog_in_both_sections(self):
        team = Team.objects.create(name="Dev")
        questions = CatalogQuestion.all_objects.filter(team=team)
        self.assertEqual(questions.count(), len(DEFAULT_CATALOG))
        self.assertEqual(set(questions.values_list("section", flat=True)), {"client", "interne"})

    def test_project_without_team_gets_its_own_catalog(self):
        project = make_individual_project()["project"]
        self.assertEqual(CatalogQuestion.all_objects.filter(project=project).count(), len(DEFAULT_CATALOG))

    def test_project_with_team_uses_team_catalog(self):
        data = make_team_project()
        self.assertEqual(CatalogQuestion.all_objects.filter(project=data["project"]).count(), 0)
        self.assertEqual(catalog.catalog_scope(data["project"]), data["team"])

    def test_default_conditions_point_to_the_realisation_question(self):
        team = Team.objects.create(name="Dev")
        realisation = CatalogQuestion.all_objects.get(team=team, label="Le projet a été réalisé")
        dependents = CatalogQuestion.all_objects.filter(team=team, condition_on=realisation)
        self.assertEqual(dependents.count(), 4)

    def test_seeding_is_idempotent(self):
        team = Team.objects.create(name="Dev")
        catalog.seed_default_catalog(team)
        self.assertEqual(CatalogQuestion.all_objects.filter(team=team).count(), len(DEFAULT_CATALOG))
