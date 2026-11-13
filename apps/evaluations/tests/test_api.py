from rest_framework.test import APITestCase

from .factories import make_team_project, make_user

CATALOG_URL = "/api/v1/evaluations/catalog/"


class CatalogApiTests(APITestCase):
    def setUp(self):
        self.data = make_team_project()

    def _create(self, **overrides):
        payload = {"team": str(self.data["team"].id), "section": "client", "label": "Accueil", "answer_type": "note_5"}
        payload.update(overrides)
        return self.client.post(CATALOG_URL, payload, format="json")

    def test_member_lists_team_catalog(self):
        self.client.force_authenticate(self.data["member"])
        r = self.client.get(f"{CATALOG_URL}?team={self.data['team'].id}")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["can_manage"])
        self.assertGreater(len(r.data["questions"]), 0)

    def test_project_param_resolves_to_team_catalog(self):
        self.client.force_authenticate(self.data["manager"])
        r = self.client.get(f"{CATALOG_URL}?project={self.data['project'].id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["scope"], {"kind": "team", "id": str(self.data["team"].id), "name": self.data["team"].name})

    def test_missing_scope_is_400(self):
        self.client.force_authenticate(self.data["member"])
        self.assertEqual(self.client.get(CATALOG_URL).status_code, 400)

    def test_outsider_is_refused(self):
        self.client.force_authenticate(make_user("dehors"))
        r = self.client.get(f"{CATALOG_URL}?team={self.data['team'].id}")
        self.assertEqual(r.status_code, 403)

    def test_member_cannot_create(self):
        self.client.force_authenticate(self.data["member"])
        self.assertEqual(self._create().status_code, 403)

    def test_team_admin_creates_moves_and_archives(self):
        self.client.force_authenticate(self.data["team_admin"])
        r = self._create()
        self.assertEqual(r.status_code, 201)
        question_id = r.data["id"]
        r = self.client.post(f"{CATALOG_URL}{question_id}/move/", {"direction": "up"}, format="json")
        self.assertEqual(r.status_code, 200)
        r = self.client.patch(f"{CATALOG_URL}{question_id}/", {"label": "Accueil reçu"}, format="json")
        self.assertEqual(r.data["label"], "Accueil reçu")
        r = self.client.post(f"{CATALOG_URL}{question_id}/archive/")
        self.assertEqual(r.data["status"], "archived")

    def test_invalid_definition_returns_400(self):
        self.client.force_authenticate(self.data["team_admin"])
        r = self._create(answer_type="choix_unique", options=["seule"])
        self.assertEqual(r.status_code, 400)
        self.assertIn("deux options", r.data["detail"])

    def test_changing_answer_type_returns_400(self):
        self.client.force_authenticate(self.data["team_admin"])
        question_id = self._create().data["id"]
        r = self.client.patch(f"{CATALOG_URL}{question_id}/", {"answer_type": "nps_10"}, format="json")
        self.assertEqual(r.status_code, 400)
