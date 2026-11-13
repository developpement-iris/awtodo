from django.test import TestCase

from apps.common.models import AuditLogEntry
from apps.evaluations import catalog, services
from apps.evaluations.definitions import EvaluationPermissionError, EvaluationValidationError
from apps.evaluations.models import SheetQuestion
from apps.projects.services import get_project_permissions

from .factories import make_team_project


class SheetLifecycleTests(TestCase):
    def setUp(self):
        self.data = make_team_project()
        self.manager = self.data["manager"]
        self.sheet = services.create_sheet(actor=self.manager, project=self.data["project"], title="Bilan v1")

    def _question(self, label):
        return services.sheet_questions(self.sheet).get(label=label)

    def test_creation_copies_the_catalog_with_conditions(self):
        copies = SheetQuestion.all_objects.filter(sheet=self.sheet)
        self.assertEqual(copies.count(), catalog.get_catalog(self.data["team"]).count())
        presta = copies.get(label="Nom du prestataire")
        self.assertEqual(presta.condition_on.sheet_id, self.sheet.id)
        self.assertEqual(presta.condition_on.label, "Le projet a été réalisé")
        self.assertTrue(AuditLogEntry.objects.filter(project=self.data["project"], verb="created").exists())

    def test_catalog_changes_do_not_alter_existing_sheets(self):
        question = catalog.get_catalog(self.data["team"], section="client").first()
        catalog.update_catalog_question(actor=self.data["team_admin"], question=question, label="Nouveau libellé")
        self.assertFalse(services.sheet_questions(self.sheet).filter(label="Nouveau libellé").exists())

    def test_empty_title_is_refused(self):
        with self.assertRaises(EvaluationValidationError):
            services.create_sheet(actor=self.manager, project=self.data["project"], title="  ")

    def test_only_project_manager_creates(self):
        with self.assertRaises(EvaluationPermissionError):
            services.create_sheet(actor=self.data["member"], project=self.data["project"], title="X")

    def test_team_admin_can_view_but_not_manage(self):
        self.assertTrue(services.can_view_sheets(self.data["team_admin"], self.data["project"]))
        self.assertFalse(services.can_manage_sheets(self.data["team_admin"], self.data["project"]))
        self.assertFalse(services.can_view_sheets(self.data["member"], self.data["project"]))
        with self.assertRaises(EvaluationPermissionError):
            services.list_sheets(actor=self.data["member"], project=self.data["project"])

    def test_custom_question_in_draft(self):
        question = services.add_sheet_question(
            actor=self.manager, sheet=self.sheet, section="client", label="Spécifique ?", answer_type="oui_non"
        )
        self.assertIsNone(question.catalog_question)
        services.update_sheet_question(actor=self.manager, question=question, answer_type="note_5")
        question.refresh_from_db()
        self.assertEqual(question.answer_type, "note_5")
        services.archive_sheet_question(actor=self.manager, question=question)
        self.assertNotIn(question, list(services.sheet_questions(self.sheet)))

    def test_generic_question_is_locked(self):
        generic = services.sheet_questions(self.sheet).exclude(catalog_question=None).first()
        with self.assertRaises(EvaluationValidationError):
            services.update_sheet_question(actor=self.manager, question=generic, label="Autre")
        with self.assertRaises(EvaluationValidationError):
            services.archive_sheet_question(actor=self.manager, question=generic)

    def test_generic_questions_can_be_reordered_in_draft(self):
        first, second = list(services.sheet_questions(self.sheet, section="client"))[:2]
        services.move_sheet_question(actor=self.manager, question=second, direction="up")
        self.assertEqual(services.sheet_questions(self.sheet, section="client").first().pk, second.pk)
        self.assertNotEqual(first.pk, second.pk)

    def test_custom_question_can_depend_on_a_generic_one(self):
        root = self._question("Le projet a été réalisé")
        question = services.add_sheet_question(
            actor=self.manager, sheet=self.sheet, section="interne", label="Contrat signé ?",
            answer_type="oui_non", condition_on=root.id, condition_values=["Par un prestataire"],
        )
        self.assertEqual(question.condition_on, root)

    def test_open_generates_token_and_freezes_questions(self):
        services.open_sheet(actor=self.manager, sheet=self.sheet)
        self.assertEqual(self.sheet.status, "ouverte")
        self.assertTrue(self.sheet.public_token)
        self.assertEqual(services.public_path(self.sheet), f"/evaluation/{self.sheet.public_token}")
        with self.assertRaises(EvaluationValidationError):
            services.add_sheet_question(
                actor=self.manager, sheet=self.sheet, section="client", label="Tard", answer_type="oui_non"
            )

    def test_open_requires_a_client_question(self):
        other = make_team_project("Vide")
        for question in catalog.get_catalog(other["team"], section="client"):
            question.status = "archived"
            question.save()
        sheet = services.create_sheet(actor=other["manager"], project=other["project"], title="X")
        with self.assertRaises(EvaluationValidationError):
            services.open_sheet(actor=other["manager"], sheet=sheet)
        sheet.refresh_from_db()
        self.assertEqual(sheet.status, "brouillon")

    def test_close_reopen_archive(self):
        services.open_sheet(actor=self.manager, sheet=self.sheet)
        token = self.sheet.public_token
        services.close_sheet(actor=self.manager, sheet=self.sheet)
        self.assertEqual(self.sheet.status, "close")
        self.assertIsNone(services.public_path(self.sheet))
        services.reopen_sheet(actor=self.manager, sheet=self.sheet)
        self.assertEqual(self.sheet.public_token, token)
        with self.assertRaises(EvaluationValidationError):
            services.archive_sheet(actor=self.manager, sheet=self.sheet)
        services.close_sheet(actor=self.manager, sheet=self.sheet)
        services.archive_sheet(actor=self.manager, sheet=self.sheet)
        self.assertEqual(self.sheet.status, "archivee")

    def test_rotate_link_changes_token(self):
        services.open_sheet(actor=self.manager, sheet=self.sheet)
        token = self.sheet.public_token
        services.rotate_sheet_link(actor=self.manager, sheet=self.sheet)
        self.assertNotEqual(self.sheet.public_token, token)

    def test_project_permissions_expose_flags(self):
        perms = get_project_permissions(self.manager, self.data["project"])
        self.assertTrue(perms["can_manage_evaluations"])
        self.assertTrue(perms["can_view_evaluations"])
        admin_perms = get_project_permissions(self.data["team_admin"], self.data["project"])
        self.assertFalse(admin_perms["can_manage_evaluations"])
        self.assertTrue(admin_perms["can_view_evaluations"])
        self.assertFalse(get_project_permissions(self.data["member"], self.data["project"])["can_view_evaluations"])
