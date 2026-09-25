from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Organisation, Team, User
from apps.incidents.models import Incident
from apps.integrations.models import ApiKey


@override_settings(DEBUG=True)
class ApiKeyApiTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org")
        self.admin = User.objects.create(username="admin", organisation=self.org, organisation_role="admin")
        self.member = User.objects.create(username="membre", organisation=self.org)
        self.team = Team.objects.create(name="Équipe support", organisation=self.org)

    def _as(self, user):
        self.client.credentials(HTTP_X_DEBUG_USER_ID=str(user.id))

    def test_org_admin_generates_and_lists_keys(self):
        self._as(self.admin)
        create = self.client.post("/api/v1/integrations/api-keys/", {"name": "GLPI"}, format="json")
        self.assertEqual(create.status_code, 201)
        self.assertIn("key", create.data)
        self.assertTrue(create.data["key"].startswith("awt_"))

        listing = self.client.get("/api/v1/integrations/api-keys/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.data), 1)
        self.assertNotIn("key", listing.data[0])
        self.assertNotIn("key_hash", listing.data[0])

    def test_member_cannot_generate_key(self):
        self._as(self.member)
        r = self.client.post("/api/v1/integrations/api-keys/", {"name": "GLPI"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_org_admin_revokes_key(self):
        self._as(self.admin)
        create = self.client.post("/api/v1/integrations/api-keys/", {"name": "GLPI"}, format="json")
        key_id = create.data["id"]

        revoke = self.client.post(f"/api/v1/integrations/api-keys/{key_id}/revoke/")
        self.assertEqual(revoke.status_code, 200)
        self.assertFalse(revoke.data["is_active"])

    def test_generated_key_creates_incident_without_group_membership(self):
        """Le vrai scénario visé : un système de ticketing externe, muni
        uniquement d'une clé API, crée un incident rattaché à un groupe sans
        qu'aucun compte humain n'en soit membre — même contournement que
        `X-Debug-User-Id` + `is_service_account` en dev, mais via un canal
        valable en production."""
        self._as(self.admin)
        create = self.client.post("/api/v1/integrations/api-keys/", {"name": "GLPI"}, format="json")
        raw_key = create.data["key"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key}")
        r = self.client.post(
            "/api/v1/incidents/",
            {"team": str(self.team.id), "title": "Panne signalée par GLPI"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        incident = Incident.objects.get(id=r.data["id"])
        self.assertEqual(incident.team_id, self.team.id)

    def test_revoked_key_is_rejected(self):
        self._as(self.admin)
        create = self.client.post("/api/v1/integrations/api-keys/", {"name": "GLPI"}, format="json")
        raw_key = create.data["key"]
        self.client.post(f"/api/v1/integrations/api-keys/{create.data['id']}/revoke/")

        self.client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key}")
        r = self.client.get("/api/v1/incidents/inbox/")
        # DRF choisit 401 vs 403 selon `authenticate_header` du *premier*
        # authenticator enregistré (`DebugUserIdAuthentication`, sans
        # WWW-Authenticate) plutôt que celui qui a effectivement rejeté la
        # requête — 403 est donc le code obtenu en pratique ici, cohérent
        # avec l'ordre de `DEFAULT_AUTHENTICATION_CLASSES`.
        self.assertEqual(r.status_code, 403)

    def test_api_key_scoped_to_its_own_organisation(self):
        other_org = Organisation.objects.create(name="Autre org")
        other_admin = User.objects.create(
            username="autre_admin", organisation=other_org, organisation_role="admin"
        )
        self._as(other_admin)
        create = self.client.post("/api/v1/integrations/api-keys/", {"name": "Autre"}, format="json")

        self._as(self.admin)
        # Une clé d'une autre organisation ne doit pas apparaître dans la
        # liste ni être révocable par cet admin.
        listing = self.client.get("/api/v1/integrations/api-keys/")
        self.assertEqual(len(listing.data), 0)

        revoke = self.client.post(f"/api/v1/integrations/api-keys/{create.data['id']}/revoke/")
        self.assertEqual(revoke.status_code, 404)
        self.assertTrue(ApiKey.objects.get(id=create.data["id"]).is_active)
