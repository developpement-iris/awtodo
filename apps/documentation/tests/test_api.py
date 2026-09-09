from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.documentation import services
from apps.projects.models import Project, ProjectMembership, SpecSection


@override_settings(
    DEBUG=True,
    REST_FRAMEWORK={
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
        "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.DebugUserIdAuthentication"],
    },
)
class DocsApiAuthedTests(APITestCase):
    def setUp(self):
        self.mgr = User.objects.create(username="mgr")
        self.member = User.objects.create(username="mbr")
        self.outsider = User.objects.create(username="out")
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=self.project, user=self.mgr, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def _as(self, user):
        self.client.credentials(HTTP_X_DEBUG_USER_ID=str(user.id))

    def test_get_bootstraps_empty(self):
        self._as(self.member)
        r = self.client.get(f"/api/v1/docs/{self.project.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["pages"], [])
        self.assertEqual(r.data["features"], [])
        self.assertEqual(r.data["resolutions"], [])
        self.assertIsNone(r.data["space"]["public_url"])

    def test_outsider_gets_404_on_bundle(self):
        self._as(self.outsider)
        r = self.client.get(f"/api/v1/docs/{self.project.id}/")
        self.assertEqual(r.status_code, 404)

    def test_member_cannot_create_page(self):
        self._as(self.member)
        r = self.client.post(f"/api/v1/docs/{self.project.id}/pages/", {"title": "X"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_manager_page_lifecycle(self):
        self._as(self.mgr)
        r = self.client.post(
            f"/api/v1/docs/{self.project.id}/pages/", {"title": "Prise en main"}, format="json"
        )
        self.assertEqual(r.status_code, 201)
        pid = r.data["id"]

        r = self.client.patch(
            f"/api/v1/docs/{self.project.id}/pages/{pid}/", {"content": "# Bonjour"}, format="json"
        )
        self.assertEqual(r.data["content"], "# Bonjour")

        r = self.client.post(f"/api/v1/docs/{self.project.id}/pages/{pid}/publish/")
        self.assertEqual(r.data["status"], "publie")

        r = self.client.post(f"/api/v1/docs/{self.project.id}/pages/{pid}/unpublish/")
        self.assertEqual(r.data["status"], "brouillon")

        r = self.client.delete(f"/api/v1/docs/{self.project.id}/pages/{pid}/")
        self.assertEqual(r.status_code, 204)

    def test_create_resolution_entry(self):
        self._as(self.mgr)
        r = self.client.post(
            f"/api/v1/docs/{self.project.id}/entries/",
            {"kind": "resolution", "title": "Panne export résolue"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["kind"], "resolution")

    def test_seed_from_spec(self):
        SpecSection.objects.create(
            project=self.project,
            section_key="exigences_fonctionnelles",
            is_active=True,
            content="- Export Excel\n\n- Filtre multi-critères\n",
        )
        self._as(self.mgr)
        r = self.client.post(f"/api/v1/docs/{self.project.id}/seed-from-spec/")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(r.data["created"]), 2)

    def test_enable_rotate_revoke_public_link(self):
        self._as(self.mgr)
        r = self.client.post(f"/api/v1/docs/{self.project.id}/public-link/")
        self.assertTrue(r.data["space"]["public_url"])
        first = r.data["space"]["public_token"]

        r = self.client.post(f"/api/v1/docs/{self.project.id}/public-link/rotate/")
        self.assertNotEqual(r.data["space"]["public_token"], first)

        r = self.client.delete(f"/api/v1/docs/{self.project.id}/public-link/")
        self.assertIsNone(r.data["space"]["public_url"])

    def test_pending_create_entry_flow(self):
        from decimal import Decimal

        from apps.projects.models import ProjectVersion
        from apps.tasks import services as task_services
        from apps.tasks.models import Task

        services.get_or_create_space(actor=self.mgr, project=self.project)
        version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        task = Task.objects.create(
            project=self.project, version=version, title="Export Excel",
            task_type="ajout", status="en_cours", assignee=self.mgr,
        )
        task_services.complete_task(actor=self.mgr, task=task, time_spent=Decimal("1"))

        self._as(self.mgr)
        bundle = self.client.get(f"/api/v1/docs/{self.project.id}/").data
        self.assertEqual(len(bundle["pending_features"]), 1)
        pending_id = bundle["pending_features"][0]["id"]

        r = self.client.post(
            f"/api/v1/docs/{self.project.id}/pending/{pending_id}/create-entry/"
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["title"], "Export Excel")

        bundle = self.client.get(f"/api/v1/docs/{self.project.id}/").data
        self.assertEqual(bundle["pending_features"], [])
        self.assertEqual(len(bundle["features"]), 1)


@override_settings(DEBUG=True)
class DocsApiPublicTests(APITestCase):
    def setUp(self):
        self.mgr = User.objects.create(username="mgr")
        self.project = Project.objects.create(name="Mon Produit", project_type="collaboratif")
        ProjectMembership.objects.create(project=self.project, user=self.mgr, role="chef_de_projet")
        self.space = services.enable_public_link(actor=self.mgr, project=self.project)
        published = services.create_page(
            actor=self.mgr, project=self.project, title="Publiee", content="# Bonjour"
        )
        services.publish_page(actor=self.mgr, project=self.project, page_id=published.id)
        services.create_page(actor=self.mgr, project=self.project, title="Brouillon")
        feature = services.create_entry(
            actor=self.mgr, project=self.project, kind="fonctionnalite", title="Export"
        )
        services.publish_entry(actor=self.mgr, project=self.project, entry_id=feature.id)

    def test_only_published(self):
        r = self.client.get(f"/api/v1/docs/public/{self.space.public_token}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["project_name"], "Mon Produit")
        self.assertEqual([p["title"] for p in r.data["pages"]], ["Publiee"])
        self.assertEqual([f["title"] for f in r.data["features"]], ["Export"])
        self.assertEqual(r.data["resolutions"], [])

    def test_unknown_token_404(self):
        self.assertEqual(self.client.get("/api/v1/docs/public/nope/").status_code, 404)

    def test_revoked_token_404(self):
        token = self.space.public_token
        services.revoke_public_link(actor=self.mgr, project=self.project)
        self.assertEqual(self.client.get(f"/api/v1/docs/public/{token}/").status_code, 404)

    def test_public_endpoint_needs_no_auth(self):
        # Aucune en-tête d'authentification : doit quand même répondre 200.
        r = self.client.get(f"/api/v1/docs/public/{self.space.public_token}/")
        self.assertEqual(r.status_code, 200)
