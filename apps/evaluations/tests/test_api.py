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


SHEETS_URL = "/api/v1/evaluations/sheets/"


class SheetApiTests(APITestCase):
    def setUp(self):
        self.data = make_team_project()

    def _create(self):
        self.client.force_authenticate(self.data["manager"])
        return self.client.post(SHEETS_URL, {"project": str(self.data["project"].id), "title": "Bilan"}, format="json")

    def test_manager_creates_lists_and_opens(self):
        r = self._create()
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["questions"])
        self.assertTrue(r.data["permissions"]["can_manage"])
        sheet_id = r.data["id"]
        r = self.client.get(f"{SHEETS_URL}?project={self.data['project'].id}")
        self.assertEqual([s["response_count"] for s in r.data], [0])
        r = self.client.post(f"{SHEETS_URL}{sheet_id}/open/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["public_path"].startswith("/evaluation/"))

    def test_custom_question_lifecycle(self):
        sheet_id = self._create().data["id"]
        r = self.client.post(f"{SHEETS_URL}{sheet_id}/questions/", {
            "section": "client", "label": "Spécifique ?", "answer_type": "oui_non",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.data["is_generic"])
        question_id = r.data["id"]
        r = self.client.patch(f"{SHEETS_URL}{sheet_id}/questions/{question_id}/", {"required": True}, format="json")
        self.assertTrue(r.data["required"])
        r = self.client.post(f"{SHEETS_URL}{sheet_id}/questions/{question_id}/move/", {"direction": "up"}, format="json")
        self.assertEqual(r.status_code, 200)
        r = self.client.post(f"{SHEETS_URL}{sheet_id}/questions/{question_id}/archive/")
        self.assertEqual(r.data["status"], "archived")

    def test_generic_question_edit_returns_400(self):
        r = self._create()
        generic = next(q for q in r.data["questions"] if q["is_generic"])
        r = self.client.patch(f"{SHEETS_URL}{r.data['id']}/questions/{generic['id']}/", {"label": "X"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_member_cannot_list(self):
        self.client.force_authenticate(self.data["member"])
        r = self.client.get(f"{SHEETS_URL}?project={self.data['project'].id}")
        self.assertEqual(r.status_code, 403)

    def test_team_admin_reads_but_cannot_create(self):
        sheet_id = self._create().data["id"]
        self.client.force_authenticate(self.data["team_admin"])
        r = self.client.get(f"{SHEETS_URL}{sheet_id}/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["permissions"]["can_manage"])
        r = self.client.post(SHEETS_URL, {"project": str(self.data["project"].id), "title": "X"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_list_requires_project(self):
        self.client.force_authenticate(self.data["manager"])
        self.assertEqual(self.client.get(SHEETS_URL).status_code, 400)
