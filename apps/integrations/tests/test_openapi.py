from unittest import mock

from django.test import SimpleTestCase, override_settings
from drf_spectacular.drainage import GENERATOR_STATS
from drf_spectacular.generators import SchemaGenerator
from rest_framework.permissions import IsAuthenticated
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.integrations.services import generate_api_key

PREFIX = "/api/v1/"
SHELL_URL = f"{PREFIX}docs-api/"
SCHEMA_URL = f"{PREFIX}schema/"

# Actions sans corps : elles héritaient du serializer de l'entité complète.
NO_BODY = [
    ("post", "tasks/{id}/start/"),
    ("post", "tasks/{id}/claim/"),
    ("post", "tasks/{id}/reactivate/"),
    ("post", "tasks/types/{id}/archive/"),
    ("post", "tasks/types/{id}/restore/"),
    ("post", "incidents/{id}/start/"),
    ("post", "incidents/{id}/claim/"),
    ("post", "incidents/{id}/archive/"),
    ("post", "projects/{id}/close/"),
    ("post", "projects/{id}/reopen/"),
    ("post", "budgeting/{id}/remove/"),
    ("post", "notifications/{id}/mark-read/"),
    ("post", "notifications/mark-all-read/"),
    ("post", "accounts/users/{id}/deactivate/"),
    ("post", "accounts/users/{id}/reactivate/"),
    ("post", "accounts/invitations/{token}/resend/"),
    ("post", "planning/events/{id}/cancel/"),
    ("post", "planning/blocks/{id}/cancel/"),
    ("post", "planning/shares/{id}/revoke/"),
    ("post", "planning/projects/{project_id}/entries/{entry_id}/cancel/"),
    ("post", "integrations/api-keys/{api_key_id}/revoke/"),
    ("post", "docs/{project_id}/pages/{page_id}/publish/"),
    ("post", "docs/{project_id}/pages/{page_id}/unpublish/"),
    ("post", "docs/{project_id}/entries/{entry_id}/publish/"),
    ("post", "docs/{project_id}/entries/{entry_id}/unpublish/"),
    ("post", "docs/{project_id}/seed-from-spec/"),
    ("post", "docs/{project_id}/pending/{pending_id}/create-entry/"),
    ("post", "docs/{project_id}/pending/{pending_id}/ignore/"),
    ("post", "docs/{project_id}/contributors/generate/"),
    ("post", "docs/{project_id}/public-link/"),
    ("post", "docs/{project_id}/public-link/rotate/"),
]

# (méthode, chemin) -> champs réellement lus par la vue.
BODIES = {
    ("post", "accounts/login/"): {"username", "password"},
    ("post", "accounts/me/change-password/"): {"current_password", "new_password"},
    ("post", "accounts/password-reset/request/"): {"identifier"},
    ("post", "tasks/"): {"project", "title"},
    ("post", "tasks/{id}/rename/"): {"title"},
    ("post", "tasks/{id}/update-description/"): {"description"},
    ("post", "tasks/{id}/update-estimated-hours/"): {"estimated_hours"},
    ("post", "tasks/{id}/update-deadline/"): {"deadline"},
    ("post", "tasks/{id}/update-type/"): {"task_type"},
    ("post", "tasks/{id}/update-priority/"): {"priority"},
    ("post", "tasks/{id}/validate/"): {"assignee"},
    ("post", "tasks/{id}/reject/"): {"rejection_reason"},
    ("post", "tasks/{id}/cancel/"): {"cancellation_reason"},
    ("post", "tasks/{id}/assign/"): {"assignee"},
    ("post", "tasks/{id}/complete/"): {"time_spent"},
    ("post", "tasks/types/"): {"label", "icon", "team", "project"},
    ("post", "incidents/"): {"title", "project", "team", "external_reference_id"},
    ("post", "incidents/{id}/resolve/"): {"resolution_comment", "time_spent"},
    ("post", "incidents/{id}/cancel/"): {"cancellation_reason"},
    ("post", "incidents/{id}/update-description/"): {"description"},
    ("post", "projects/"): {"name"},
    ("post", "projects/{id}/update-details/"): {"name", "phase"},
    ("post", "projects/{id}/versions/"): {"label"},
    ("post", "budgeting/projects/{project_id}/lines/"): {"label"},
    ("post", "communication/projects/{project_id}/messages/"): {"subject", "body"},
    ("post", "planning/events/"): {"title"},
    ("post", "dashboards/global/"): {"title"},
    ("patch", "docs/{project_id}/appearance/"): {"theme_colors", "show_powered_by"},
    ("post", "docs/{project_id}/entries/"): {"kind", "title"},
    ("patch", "docs/{project_id}/entries/{entry_id}/"): {"title", "version_id"},
    ("post", "docs/{project_id}/pages/"): {"title", "section"},
    ("patch", "docs/{project_id}/pages/{page_id}/"): {"title", "parent_id"},
    ("patch", "docs/{project_id}/contributors/"): {"rows"},
    ("patch", "docs/{project_id}/public-link/slug/"): {"slug"},
}

# (méthode, chemin) -> (statut de succès, champ attendu dans la réponse).
RESPONSES = {
    ("post", "tasks/"): ("201", "status"),
    ("post", "tasks/{id}/comments/"): ("201", "content"),
    ("post", "incidents/{id}/comments/"): ("201", "content"),
    ("post", "projects/{id}/versions/"): ("201", "label"),
    ("post", "accounts/login/"): ("200", "access"),
    ("post", "accounts/invitations/{token}/resend/"): ("201", "token"),
    ("patch", "projects/{id}/spec-sections/{section_key}/"): ("200", "section_key"),
}


def _resolve(schema, content):
    body = next(iter(content.values()))["schema"]
    if "$ref" in body:
        return schema["components"]["schemas"][body["$ref"].split("/")[-1]]
    return body


class OpenApiContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        GENERATOR_STATS.reset()
        cls.schema = SchemaGenerator().get_schema(request=None, public=True)
        cls.error_count = sum(GENERATOR_STATS._error_cache.values())

    def _op(self, method, path):
        return self.schema["paths"][f"{PREFIX}{path}"][method]

    def test_generation_has_no_error(self):
        self.assertEqual(self.error_count, 0)

    def test_actions_without_body_declare_none(self):
        for method, path in NO_BODY:
            with self.subTest(path=path):
                self.assertNotIn("requestBody", self._op(method, path))

    def test_bodies_declare_the_fields_the_view_reads(self):
        for (method, path), fields in BODIES.items():
            with self.subTest(path=path):
                body = _resolve(self.schema, self._op(method, path)["requestBody"]["content"])
                self.assertLessEqual(fields, set(body["properties"]))

    def test_responses_declare_real_status_and_shape(self):
        for (method, path), (status, field) in RESPONSES.items():
            with self.subTest(path=path):
                response = self._op(method, path)["responses"][status]
                self.assertIn(field, _resolve(self.schema, response["content"])["properties"])

    def test_uploads_are_multipart(self):
        for path in ("docs/{project_id}/pages/{page_id}/attachments/", "projects/{id}/cover/"):
            with self.subTest(path=path):
                self.assertIn("multipart/form-data", self._op("post", path)["requestBody"]["content"])

    def test_identifiers_are_typed_as_uuid(self):
        parameters = self._op("post", "docs/{project_id}/pages/{page_id}/publish/")["parameters"]
        self.assertEqual({p["schema"].get("format") for p in parameters if p["in"] == "path"}, {"uuid"})

    def test_operation_ids_are_unique(self):
        ids = [op["operationId"] for path in self.schema["paths"].values() for op in path.values()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_security_schemes_are_the_real_ones(self):
        self.assertEqual(set(self.schema["components"]["securitySchemes"]), {"jwtAuth", "apiKeyAuth"})

    def test_public_documentation_requires_no_authentication(self):
        self.assertEqual(self._op("get", "docs/public/{token}/")["security"], [{}])

    def test_query_parameters_of_hand_written_views_are_declared(self):
        names = {p["name"] for p in self._op("get", "planning/calendar/")["parameters"]}
        self.assertLessEqual({"from", "to", "owners", "projects", "outlook"}, names)


@override_settings(DEBUG=True)
class ApiDocumentationAccessTests(APITestCase):
    """Le réglage de dev (`AllowAny` par défaut) est figé à l'import des vues :
    on rétablit ici le défaut de production pour tester le filtrage réel."""

    def setUp(self):
        patcher = mock.patch("rest_framework.views.APIView.permission_classes", [IsAuthenticated])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.admin = User.objects.create(username="admin", organisation_role="admin")

    def _schema(self):
        response = self.client.get(SCHEMA_URL, HTTP_ACCEPT="application/vnd.oai.openapi+json")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_swagger_page_opens_without_authentication(self):
        self.assertEqual(self.client.get(SHELL_URL).status_code, 200)

    def test_swagger_page_may_load_its_cdn_without_inline_scripts(self):
        csp = self.client.get(SHELL_URL)["Content-Security-Policy"]
        self.assertIn("script-src 'self' https://cdn.jsdelivr.net;", csp)
        self.assertNotIn("script-src 'self' 'unsafe-inline'", csp)

    def test_swagger_script_is_served_by_awtodo(self):
        response = self.client.get(SHELL_URL, {"script": ""})
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response["Content-Type"])

    def test_csp_exception_is_limited_to_the_swagger_page(self):
        self.assertNotIn("cdn.jsdelivr.net", self.client.get(SCHEMA_URL)["Content-Security-Policy"])

    def test_anonymous_schema_only_describes_public_endpoints(self):
        paths = self._schema()["paths"]
        self.assertIn(f"{PREFIX}accounts/login/", paths)
        self.assertIn(f"{PREFIX}docs/public/{{token}}/", paths)
        self.assertNotIn(f"{PREFIX}tasks/", paths)
        self.assertNotIn(f"{PREFIX}integrations/api-keys/", paths)
        self.assertNotIn(f"{PREFIX}docs/{{project_id}}/appearance/", paths)

    def test_anonymous_schema_keeps_authorize_available(self):
        schemes = self._schema()["components"]["securitySchemes"]
        self.assertEqual(set(schemes), {"jwtAuth", "apiKeyAuth"})

    def test_schema_refuses_invalid_key(self):
        self.client.credentials(HTTP_AUTHORIZATION="Api-Key faux")
        self.assertEqual(self.client.get(SCHEMA_URL).status_code, 401)

    def test_schema_with_api_key_describes_the_api(self):
        _, raw_key = generate_api_key(actor=self.admin, organisation=self.admin.organisation, name="QWEASE")
        self.client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key}")
        self.assertIn(f"{PREFIX}tasks/", self._schema()["paths"])

    def test_schema_with_jwt_describes_the_api(self):
        token = RefreshToken.for_user(self.admin).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertIn(f"{PREFIX}tasks/", self._schema()["paths"])
