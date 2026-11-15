"""Widgets de statistiques des fiches d'évaluation (session du 2026-11-15)."""

from django.test import TestCase

from apps.dashboards.services import DashboardPermissionError, compute_widget_data, create_widget
from apps.evaluations import services as evaluations
from apps.evaluations.tests.factories import make_team_project


class EvaluationWidgetTests(TestCase):
    def setUp(self):
        self.data = make_team_project("Dash")
        manager = self.data["manager"]
        sheet = evaluations.create_sheet(actor=manager, project=self.data["project"], title="Vague 1")
        evaluations.open_sheet(actor=manager, sheet=sheet)
        values = {"note_5": 5, "nps_10": 9, "oui_non": "oui", "texte_long": "ok"}
        answers = {
            str(q.id): values[q.answer_type] for q in evaluations.sheet_questions(sheet, section="client")
        }
        evaluations.submit_client_response(token=sheet.public_token, respondent_name="A", answers=answers)

    def test_manager_sees_generic_results_table_globally(self):
        widget = create_widget(
            actor=self.data["manager"], scope="global", widget_type="defaut", metric_key="evaluation_generic_results"
        )
        data = compute_widget_data(actor=self.data["manager"], widget=widget)
        self.assertEqual(data["type"], "table")
        self.assertTrue(any(row["Question"].startswith("Globalement") for row in data["rows"]))
        self.assertEqual(set(data["rows"][0]), {"Groupe", "Partie", "Question", "Résultat", "Réponses"})

    def test_response_count_on_project(self):
        widget = create_widget(
            actor=self.data["manager"],
            scope="projet",
            project=self.data["project"],
            widget_type="defaut",
            metric_key="evaluation_response_count",
        )
        data = compute_widget_data(actor=self.data["manager"], widget=widget)
        self.assertEqual(data, {"type": "scalar", "value": 1})

    def test_plain_member_cannot_add_the_widget(self):
        with self.assertRaises(DashboardPermissionError):
            create_widget(
                actor=self.data["member"],
                scope="projet",
                project=self.data["project"],
                widget_type="defaut",
                metric_key="evaluation_generic_results",
            )
