from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APITestCase

from apps.evaluations import results, services
from apps.evaluations.catalog import get_catalog
from apps.evaluations.definitions import EvaluationPermissionError, EvaluationValidationError
from apps.evaluations.models import CatalogQuestion
from apps.projects.models import Project, ProjectMembership

from .factories import make_team_project, make_user


def q(answer_type, options=()):
    return SimpleNamespace(id="x", label="Q", answer_type=answer_type, options=list(options))


CLIENT_VALUES = {"note_5": 5, "nps_10": 10, "oui_non": "oui", "texte_long": "ok"}


def client_answers(sheet, values=CLIENT_VALUES):
    return {str(x.id): values[x.answer_type] for x in services.sheet_questions(sheet, section="client")}


class SummarizeTests(SimpleTestCase):
    def test_note(self):
        s = results.summarize(q("note_5"), [5, 4, 3])
        self.assertEqual(s["average"], 4.0)
        self.assertEqual(s["distribution"]["5"], 1)

    def test_nps(self):
        s = results.summarize(q("nps_10"), [10, 9, 8, 3])
        self.assertEqual((s["promoters"], s["passives"], s["detractors"]), (2, 1, 1))
        self.assertEqual(s["score"], 25)

    def test_yes_no(self):
        s = results.summarize(q("oui_non"), ["oui", "oui", "non"])
        self.assertAlmostEqual(s["yes_rate"], 2 / 3)

    def test_multiple_choice(self):
        s = results.summarize(q("choix_multiple", ["A", "B"]), [["A", "B"], ["A"]])
        self.assertEqual(s["counts"], {"A": 2, "B": 1})
        self.assertEqual(s["count"], 2)

    def test_empty(self):
        self.assertIsNone(results.summarize(q("note_5"), [])["average"])

    def test_none_values_are_ignored(self):
        self.assertEqual(results.summarize(q("note_5"), [None, 4])["count"], 1)

    def test_format_value(self):
        self.assertEqual(results.format_value(q("choix_multiple", ["A", "B"]), ["A", "B"]), "A | B")
        self.assertEqual(results.format_value(q("note_5"), None), "")


class InternalAndResultsTests(TestCase):
    def setUp(self):
        self.data = make_team_project()
        self.manager = self.data["manager"]
        self.sheet = services.create_sheet(actor=self.manager, project=self.data["project"], title="Bilan")
        self.realisation = services.sheet_questions(self.sheet).get(label="Le projet a été réalisé")
        self.presta = services.sheet_questions(self.sheet).get(label="Nom du prestataire")

    def test_internal_requires_open_sheet(self):
        with self.assertRaises(EvaluationValidationError):
            services.save_internal_evaluation(actor=self.manager, sheet=self.sheet, answers={})

    def test_internal_save_is_partial_and_overwrites(self):
        services.open_sheet(actor=self.manager, sheet=self.sheet)
        services.save_internal_evaluation(
            actor=self.manager,
            sheet=self.sheet,
            answers={str(self.realisation.id): "Par un prestataire", str(self.presta.id): "ACME"},
        )
        services.save_internal_evaluation(
            actor=self.manager,
            sheet=self.sheet,
            answers={str(self.realisation.id): "En interne", str(self.presta.id): "ACME"},
        )
        answers = services.internal_answers(self.sheet)
        self.assertEqual(answers[str(self.realisation.id)], "En interne")
        self.assertIsNone(answers[str(self.presta.id)])  # masquée par la condition

    def test_only_managers_fill_internal_part(self):
        services.open_sheet(actor=self.manager, sheet=self.sheet)
        with self.assertRaises(EvaluationPermissionError):
            services.save_internal_evaluation(actor=self.data["team_admin"], sheet=self.sheet, answers={})

    def test_discarded_responses_leave_results_and_export(self):
        services.open_sheet(actor=self.manager, sheet=self.sheet)
        answers = client_answers(self.sheet)
        kept = services.submit_client_response(token=self.sheet.public_token, respondent_name="A", answers=answers)
        spam = services.submit_client_response(token=self.sheet.public_token, respondent_name="B", answers=answers)
        services.discard_response(actor=self.manager, response=spam)
        self.assertEqual(results.sheet_results(self.sheet)["response_count"], 1)
        header, rows = results.export_csv_rows(self.sheet)
        self.assertEqual([row[1] for row in rows], ["A"])
        self.assertIn("Chef de projet — Le projet a été réalisé", header)
        services.restore_response(actor=self.manager, response=spam)
        self.assertEqual(results.sheet_results(self.sheet)["response_count"], 2)
        self.assertEqual(kept.status, "retenue")

    def test_export_without_client_response_keeps_internal_part(self):
        services.open_sheet(actor=self.manager, sheet=self.sheet)
        services.save_internal_evaluation(
            actor=self.manager, sheet=self.sheet, answers={str(self.realisation.id): "En interne"}
        )
        _, rows = results.export_csv_rows(self.sheet)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "(aucune réponse client)")
        self.assertIn("En interne", rows[0])

    def test_export_empty_sheet_has_no_rows(self):
        services.open_sheet(actor=self.manager, sheet=self.sheet)
        self.assertEqual(results.export_csv_rows(self.sheet)[1], [])

    def test_results_summarize_client_questions(self):
        services.open_sheet(actor=self.manager, sheet=self.sheet)
        services.submit_client_response(
            token=self.sheet.public_token, respondent_name="A", answers=client_answers(self.sheet)
        )
        data = results.sheet_results(self.sheet)
        kinds = {item["summary"]["kind"] for item in data["client"]}
        self.assertTrue({"note", "nps", "text"} <= kinds)


class ExistingProjectsTests(TestCase):
    """Un projet existant dont la portée n'a aucune question reçoit le
    catalogue par défaut à la création de sa première fiche."""

    def test_sheet_on_scope_without_catalog_gets_default_questions(self):
        data = make_team_project("Ancien")
        CatalogQuestion.all_objects.filter(team=data["team"]).update(condition_on=None)
        CatalogQuestion.all_objects.filter(team=data["team"]).delete()
        sheet = services.create_sheet(actor=data["manager"], project=data["project"], title="Bilan")
        self.assertTrue(get_catalog(data["team"]).exists())
        self.assertTrue(services.sheet_questions(sheet, section="client").exists())

    def test_converted_project_uses_its_group_catalog(self):
        data = make_team_project("Converti")
        manager = make_user("solo-cp")
        project = Project.objects.create(name="Solo", project_type="individuel")
        ProjectMembership.objects.create(project=project, user=manager, role="chef_de_projet")
        project.team = data["team"]
        project.project_type = "collaboratif"
        project.save()
        sheet = services.create_sheet(actor=manager, project=project, title="Bilan")
        sources = {q.catalog_question.team_id for q in services.sheet_questions(sheet)}
        self.assertEqual(sources, {data["team"].id})


class EvaluationInsightsTests(TestCase):
    def test_rows_group_by_catalog_question_and_skip_custom(self):
        data = make_team_project()
        manager = data["manager"]
        for title in ("Vague 1", "Vague 2"):
            sheet = services.create_sheet(actor=manager, project=data["project"], title=title)
            services.add_sheet_question(actor=manager, sheet=sheet, section="client", label="Perso", answer_type="note_5")
            services.open_sheet(actor=manager, sheet=sheet)
            values = {"note_5": 4, "nps_10": 10, "oui_non": "oui", "texte_long": "ok"}
            services.submit_client_response(
                token=sheet.public_token, respondent_name="A", answers=client_answers(sheet, values)
            )
        insights = results.evaluation_insights([data["project"].id])
        satisfaction = next(r for r in insights["generic_rows"] if r["question"].startswith("Globalement"))
        self.assertEqual(satisfaction["reponses"], 2)
        self.assertEqual(satisfaction["resultat"], "4,0 / 5")
        self.assertEqual(satisfaction["groupe"], data["team"].name)
        self.assertFalse(any(r["question"] == "Perso" for r in insights["generic_rows"]))
        self.assertEqual(insights["response_count"], 2)

    def test_discarded_responses_are_excluded(self):
        data = make_team_project()
        sheet = services.create_sheet(actor=data["manager"], project=data["project"], title="Vague")
        services.open_sheet(actor=data["manager"], sheet=sheet)
        response = services.submit_client_response(
            token=sheet.public_token, respondent_name="Spam", answers=client_answers(sheet)
        )
        services.discard_response(actor=data["manager"], response=response)
        insights = results.evaluation_insights([data["project"].id])
        self.assertEqual(insights["generic_rows"], [])
        self.assertEqual(insights["response_count"], 0)


class ResultsApiTests(APITestCase):
    def setUp(self):
        self.data = make_team_project()
        self.sheet = services.create_sheet(actor=self.data["manager"], project=self.data["project"], title="Bilan")
        services.open_sheet(actor=self.data["manager"], sheet=self.sheet)
        self.url = f"/api/v1/evaluations/sheets/{self.sheet.id}/"
        self.realisation = services.sheet_questions(self.sheet).get(label="Le projet a été réalisé")

    def test_manager_saves_internal_part(self):
        self.client.force_authenticate(self.data["manager"])
        r = self.client.put(
            f"{self.url}internal/", {"answers": {str(self.realisation.id): "En interne"}}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["internal"]["answers"][str(self.realisation.id)], "En interne")
        self.assertIsNotNone(r.data["internal"]["updated_by"])

    def test_team_admin_cannot_save_internal_part(self):
        self.client.force_authenticate(self.data["team_admin"])
        r = self.client.put(f"{self.url}internal/", {"answers": {}}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_team_admin_reads_results(self):
        self.client.force_authenticate(self.data["team_admin"])
        r = self.client.get(f"{self.url}results/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["response_count"], 0)

    def test_member_cannot_read_results(self):
        self.client.force_authenticate(self.data["member"])
        self.assertEqual(self.client.get(f"{self.url}results/").status_code, 403)

    def test_export_csv(self):
        services.submit_client_response(
            token=self.sheet.public_token, respondent_name="Client A", answers=client_answers(self.sheet)
        )
        self.client.force_authenticate(self.data["manager"])
        r = self.client.get(f"{self.url}export/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("text/csv"))
        first_line = r.content.decode("utf-8-sig").splitlines()[0]
        self.assertIn("Répondant", first_line)

    def test_discard_and_restore_response(self):
        response = services.submit_client_response(
            token=self.sheet.public_token, respondent_name="Spam", answers=client_answers(self.sheet)
        )
        self.client.force_authenticate(self.data["manager"])
        r = self.client.post(f"{self.url}responses/{response.id}/discard/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data[0]["status"], "ecartee")
        r = self.client.post(f"{self.url}responses/{response.id}/restore/")
        self.assertEqual(r.data[0]["status"], "retenue")
        r = self.client.get(f"{self.url}responses/")
        self.assertEqual(len(r.data), 1)
