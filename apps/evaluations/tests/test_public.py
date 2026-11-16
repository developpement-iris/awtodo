from unittest import mock

from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.evaluations import services
from apps.evaluations.models import Answer, ClientResponse
from apps.evaluations.throttles import EvaluationSubmitThrottle

from .factories import make_team_project


class PublicEvaluationTests(APITestCase):
    def setUp(self):
        cache.clear()  # throttle anonyme partagé entre tests
        self.data = make_team_project()
        self.sheet = services.create_sheet(actor=self.data["manager"], project=self.data["project"], title="Bilan")
        services.open_sheet(actor=self.data["manager"], sheet=self.sheet)
        self.url = f"/api/v1/evaluations/public/{self.sheet.public_token}/"
        self.client_questions = list(services.sheet_questions(self.sheet, section="client"))

    def _valid_answers(self):
        values = {"note_5": 4, "nps_10": 9, "oui_non": "oui", "texte_long": "Très bien"}
        return {str(q.id): values[q.answer_type] for q in self.client_questions}

    def _submit(self, name="Mme Martin", answers=None):
        answers = self._valid_answers() if answers is None else answers
        return self.client.post(f"{self.url}responses/", {"respondent_name": name, "answers": answers}, format="json")

    def test_get_exposes_only_client_questions(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual({q["id"] for q in r.data["questions"]}, {str(q.id) for q in self.client_questions})
        self.assertNotIn("internal", r.data)
        self.assertEqual(r.data["project_name"], self.data["project"].name)

    def test_unknown_token_is_404(self):
        self.assertEqual(self.client.get("/api/v1/evaluations/public/inconnu/").status_code, 404)

    def test_submit_stores_answers(self):
        r = self._submit()
        self.assertEqual(r.status_code, 201)
        response = ClientResponse.all_objects.get(sheet=self.sheet)
        self.assertEqual(response.respondent_name, "Mme Martin")
        self.assertEqual(Answer.objects.filter(client_response=response).count(), len(self.client_questions))

    def test_name_is_required(self):
        self.assertEqual(self._submit(name=" ").status_code, 400)

    def test_required_answer_is_enforced(self):
        answers = self._valid_answers()
        answers.pop(str(self.client_questions[0].id))
        r = self._submit(answers=answers)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["question"], str(self.client_questions[0].id))

    def test_internal_question_cannot_be_answered_publicly(self):
        internal = services.sheet_questions(self.sheet, section="interne").first()
        r = self._submit(answers={**self._valid_answers(), str(internal.id): "En interne"})
        self.assertEqual(r.status_code, 400)

    def test_closed_sheet_refuses_answers(self):
        services.close_sheet(actor=self.data["manager"], sheet=self.sheet)
        self.assertTrue(self.client.get(self.url).data["closed"])
        self.assertEqual(self._submit().status_code, 410)

    def test_draft_sheet_is_not_reachable(self):
        draft = services.create_sheet(actor=self.data["manager"], project=self.data["project"], title="Brouillon")
        self.assertIsNone(draft.public_token)
        self.assertEqual(self.client.get("/api/v1/evaluations/public/None/").status_code, 404)

    def test_rotated_token_invalidates_old_link(self):
        services.rotate_sheet_link(actor=self.data["manager"], sheet=self.sheet)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_submission_is_throttled(self):
        with mock.patch.object(EvaluationSubmitThrottle, "THROTTLE_RATES", {"evaluation_submit": "2/hour"}):
            self.assertEqual(self._submit().status_code, 201)
            self.assertEqual(self._submit().status_code, 201)
            self.assertEqual(self._submit().status_code, 429)
