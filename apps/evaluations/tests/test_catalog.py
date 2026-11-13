from django.test import TestCase

from apps.accounts.models import Team
from apps.evaluations import catalog
from apps.evaluations.defaults import DEFAULT_CATALOG
from apps.evaluations.definitions import EvaluationPermissionError, EvaluationValidationError
from apps.evaluations.models import CatalogQuestion

from .factories import make_individual_project, make_team_project, make_user


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


class CatalogServiceTests(TestCase):
    def setUp(self):
        self.data = make_team_project()
        self.team = self.data["team"]
        self.admin = self.data["team_admin"]

    def _create(self, actor, **overrides):
        payload = {"section": "client", "label": "Accueil ?", "answer_type": "note_5"}
        payload.update(overrides)
        return catalog.create_catalog_question(actor=actor, scope=self.team, **payload)

    def _default(self, label):
        return CatalogQuestion.all_objects.get(team=self.team, label=label)

    def test_team_admin_creates_question(self):
        question = self._create(self.admin)
        self.assertEqual(question.team, self.team)
        self.assertEqual(question.position, len([s for s in DEFAULT_CATALOG if s["section"] == "client"]))

    def test_project_manager_is_not_team_admin(self):
        with self.assertRaises(EvaluationPermissionError):
            self._create(self.data["manager"])

    def test_member_can_view_but_not_manage(self):
        self.assertTrue(catalog.can_view_catalog(self.data["member"], self.team))
        self.assertFalse(catalog.can_manage_catalog(self.data["member"], self.team))
        outsider = make_user("dehors")
        with self.assertRaises(EvaluationPermissionError):
            catalog.list_catalog(actor=outsider, scope=self.team)

    def test_individual_project_catalog_is_managed_by_its_manager(self):
        perso = make_individual_project()
        question = catalog.create_catalog_question(
            actor=perso["manager"], scope=perso["project"], section="interne", label="Bilan",
            answer_type="texte_long",
        )
        self.assertEqual(question.project, perso["project"])

    def test_choice_question_requires_two_distinct_options(self):
        with self.assertRaises(EvaluationValidationError):
            self._create(self.admin, answer_type="choix_unique", options=["A"])
        with self.assertRaises(EvaluationValidationError):
            self._create(self.admin, answer_type="choix_unique", options=["A", "a"])

    def test_options_are_dropped_for_non_choice_types(self):
        self.assertEqual(self._create(self.admin, options=["A", "B"]).options, [])

    def test_condition_must_target_a_conditionable_question_of_same_section(self):
        text = self._create(self.admin, answer_type="texte_court")
        with self.assertRaises(EvaluationValidationError):
            self._create(self.admin, label="Détail", condition_on=text.id, condition_values=["x"])
        interne = self._create(self.admin, section="interne", answer_type="oui_non", label="Budget ok ?")
        with self.assertRaises(EvaluationValidationError):
            self._create(self.admin, label="Détail", condition_on=interne.id, condition_values=["oui"])

    def test_condition_values_must_exist(self):
        root = self._create(self.admin, answer_type="choix_unique", options=["A", "B"])
        with self.assertRaises(EvaluationValidationError):
            self._create(self.admin, label="Détail", condition_on=root.id, condition_values=["C"])
        with self.assertRaises(EvaluationValidationError):
            self._create(self.admin, label="Détail", condition_on=root.id, condition_values=[])
        detail = self._create(self.admin, label="Détail", condition_on=root.id, condition_values=["B"])
        self.assertEqual(detail.condition_on, root)

    def test_condition_cycle_is_refused(self):
        a = self._create(self.admin, label="A", answer_type="oui_non")
        b = self._create(self.admin, label="B", answer_type="oui_non", condition_on=a.id, condition_values=["oui"])
        with self.assertRaises(EvaluationValidationError):
            catalog.update_catalog_question(actor=self.admin, question=a, condition_on=b.id, condition_values=["oui"])

    def test_answer_type_is_frozen(self):
        question = self._create(self.admin)
        with self.assertRaises(EvaluationValidationError):
            catalog.update_catalog_question(actor=self.admin, question=question, answer_type="nps_10")

    def test_update_label_keeps_other_fields(self):
        question = self._create(self.admin, required=True)
        catalog.update_catalog_question(actor=self.admin, question=question, label="Nouveau")
        question.refresh_from_db()
        self.assertEqual((question.label, question.required), ("Nouveau", True))

    def test_cannot_archive_a_condition_target(self):
        with self.assertRaises(EvaluationValidationError):
            catalog.archive_catalog_question(actor=self.admin, question=self._default("Le projet a été réalisé"))

    def test_archive_and_restore(self):
        question = self._default("Remarques ou suggestions")
        catalog.archive_catalog_question(actor=self.admin, question=question)
        self.assertNotIn(question, list(catalog.get_catalog(self.team)))
        catalog.restore_catalog_question(actor=self.admin, question=question)
        self.assertIn(question, list(catalog.get_catalog(self.team)))

    def test_options_still_used_by_a_condition_cannot_be_removed(self):
        with self.assertRaises(EvaluationValidationError):
            catalog.update_catalog_question(
                actor=self.admin, question=self._default("Le projet a été réalisé"), options=["En interne", "Mixte"]
            )

    def test_move_swaps_positions_within_section(self):
        first, second = list(catalog.get_catalog(self.team, section="client"))[:2]
        catalog.move_catalog_question(actor=self.admin, question=second, direction="up")
        ordered = list(catalog.get_catalog(self.team, section="client"))
        self.assertEqual([ordered[0].pk, ordered[1].pk], [second.pk, first.pk])
