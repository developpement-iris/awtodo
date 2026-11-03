import base64
import hashlib
import json
import secrets
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from oauth2_provider.models import AccessToken, Application

from apps.accounts.models import User
from apps.projects.models import Project
from apps.tasks.models import Task

from ..dispatch import ApiCallError, normalize_path

CALLBACK = "https://claude.ai/api/mcp/auth_callback"


def _mcp(client, payload, token=None):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return client.post("/mcp", data=json.dumps(payload), content_type="application/json", **headers)


def _token_for(user):
    app = Application.objects.create(
        name="Claude",
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris=CALLBACK,
    )
    token = secrets.token_urlsafe(24)
    AccessToken.objects.create(user=user, application=app, token=token, scope="mcp", expires=timezone.now() + timedelta(hours=1))
    return token


class OAuthDiscoveryTests(TestCase):
    def test_protected_resource_metadata_points_to_this_server(self):
        response = self.client.get("/.well-known/oauth-protected-resource/mcp")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["resource"], "http://testserver/mcp")
        self.assertEqual(data["authorization_servers"], ["http://testserver"])

    def test_authorization_server_metadata(self):
        data = self.client.get("/.well-known/oauth-authorization-server").json()
        self.assertEqual(data["authorization_endpoint"], "http://testserver/o/authorize/")
        self.assertEqual(data["token_endpoint"], "http://testserver/o/token/")
        self.assertEqual(data["registration_endpoint"], "http://testserver/o/register/")
        self.assertEqual(data["code_challenge_methods_supported"], ["S256"])
        self.assertIn("none", data["token_endpoint_auth_methods_supported"])

    def test_mcp_without_token_returns_challenge(self):
        response = _mcp(self.client, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(response.status_code, 401)
        self.assertIn('resource_metadata="http://testserver/.well-known/oauth-protected-resource/mcp"', response["WWW-Authenticate"])

    def test_invalid_token_rejected(self):
        response = _mcp(self.client, {"jsonrpc": "2.0", "id": 1, "method": "ping"}, token="nope")
        self.assertEqual(response.status_code, 401)
        self.assertIn('error="invalid_token"', response["WWW-Authenticate"])


class DynamicClientRegistrationTests(TestCase):
    def _register(self, redirect_uris):
        body = {
            "client_name": "Claude",
            "redirect_uris": redirect_uris,
            "grant_types": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_method": "none",
        }
        return self.client.post("/o/register/", data=json.dumps(body), content_type="application/json")

    def test_claude_callback_accepted(self):
        response = self._register([CALLBACK])
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(Application.objects.filter(client_id=response.json()["client_id"]).exists())

    def test_foreign_callback_refused(self):
        response = self._register(["https://evil.example/callback"])
        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(Application.objects.exists())

    def test_registered_client_cannot_change_its_callback(self):
        registration = self._register([CALLBACK]).json()
        response = self.client.put(
            f"/o/register/{registration['client_id']}/",
            data=json.dumps({"redirect_uris": ["https://evil.example/callback"]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {registration['registration_access_token']}",
        )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(Application.objects.get().redirect_uris, CALLBACK)

    def test_mixed_callbacks_refused(self):
        response = self._register([CALLBACK, "https://evil.example/callback"])
        self.assertIn(response.status_code, (401, 403))


class FullOAuthFlowTests(TestCase):
    """Parcours complet tel que claude.ai le déroule."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="alice", password="motdepasse-solide-42", first_name="Alice")

    def test_register_login_consent_token_then_call_tools(self):
        reg = self.client.post(
            "/o/register/",
            data=json.dumps({"client_name": "Claude", "redirect_uris": [CALLBACK], "token_endpoint_auth_method": "none"}),
            content_type="application/json",
        )
        client_id = reg.json()["client_id"]

        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": CALLBACK,
            "scope": "mcp",
            "state": "xyz",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": "http://testserver/mcp",
        }

        # Pas connecté → page de connexion Awtodo.
        response = self.client.get("/o/authorize/", params)
        self.assertEqual(response.status_code, 302)
        login_url = response["Location"]
        self.assertTrue(login_url.startswith("/o/login/"))

        next_url = parse_qs(urlparse(login_url).query)["next"][0]
        bad = self.client.post("/o/login/", {"username": "alice", "password": "faux", "next": next_url})
        self.assertEqual(bad.status_code, 400)
        response = self.client.post("/o/login/", {"username": "alice", "password": "motdepasse-solide-42", "next": next_url})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], next_url)

        # Écran de consentement, avec une CSP qui autorise le retour vers claude.ai.
        consent = self.client.get(next_url)
        self.assertEqual(consent.status_code, 200)
        self.assertContains(consent, "Autoriser")
        self.assertIn("https://claude.ai", consent["Content-Security-Policy"])

        form = consent.context["form"]
        data = {name: form[name].value() for name in form.fields if form[name].value() is not None}
        data["allow"] = "Autoriser"
        response = self.client.post(next_url, data)
        self.assertEqual(response.status_code, 302, getattr(response, "content", b""))
        redirect = urlparse(response["Location"])
        self.assertEqual(f"{redirect.scheme}://{redirect.netloc}{redirect.path}", CALLBACK)
        code = parse_qs(redirect.query)["code"][0]

        token_response = self.client.post(
            "/o/token/",
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": CALLBACK,
                "client_id": client_id,
                "code_verifier": verifier,
                "resource": "http://testserver/mcp",
            },
        )
        self.assertEqual(token_response.status_code, 200, token_response.content)
        tokens = token_response.json()
        self.assertIn("refresh_token", tokens)

        self.client.logout()
        init = _mcp(self.client, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}, tokens["access_token"])
        self.assertEqual(init.status_code, 200)
        self.assertEqual(init.json()["result"]["protocolVersion"], "2025-06-18")

        whoami = _mcp(
            self.client,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "awtodo_whoami", "arguments": {}}},
            tokens["access_token"],
        ).json()["result"]
        self.assertFalse(whoami["isError"])
        self.assertIn('"username": "alice"', whoami["content"][0]["text"])


class McpToolsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="bob")
        self.token = _token_for(self.user)

    def _call(self, name, arguments=None):
        payload = {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": name, "arguments": arguments or {}}}
        return _mcp(self.client, payload, self.token).json()["result"]

    def test_tools_list(self):
        result = _mcp(self.client, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, self.token).json()["result"]
        names = {tool["name"] for tool in result["tools"]}
        self.assertEqual(names, {"awtodo_whoami", "awtodo_list_endpoints", "awtodo_api_read", "awtodo_api_write"})

    def test_notification_is_accepted_without_body(self):
        response = _mcp(self.client, {"jsonrpc": "2.0", "method": "notifications/initialized"}, self.token)
        self.assertEqual(response.status_code, 202)

    def test_unknown_method(self):
        body = _mcp(self.client, {"jsonrpc": "2.0", "id": 1, "method": "resources/list"}, self.token).json()
        self.assertEqual(body["error"]["code"], -32601)

    def test_list_endpoints_summary_and_detail(self):
        summary = self._call("awtodo_list_endpoints")["content"][0]["text"]
        self.assertIn("tasks", summary)
        detail = self._call("awtodo_list_endpoints", {"area": "tasks"})["content"][0]["text"]
        self.assertIn("POST tasks/{id}/start/", detail)
        self.assertNotIn("accounts/login/", self._call("awtodo_list_endpoints", {"area": "accounts"})["content"][0]["text"])

    def test_read_respects_project_scoping(self):
        foreign = Project.objects.create(name="Projet d'un autre", project_type="individuel")
        result = self._call("awtodo_api_read", {"path": f"projects/{foreign.id}/"})
        self.assertTrue(result["isError"])
        self.assertIn("HTTP 404", result["content"][0]["text"])

    def test_write_creates_personal_task_as_the_user(self):
        result = self._call("awtodo_api_write", {"method": "POST", "path": "/api/v1/tasks", "body": {"title": "Depuis Claude", "task_type": "correction"}})
        self.assertFalse(result["isError"], result)
        self.assertIn("HTTP 201", result["content"][0]["text"])
        self.assertEqual(Task.objects.get(title="Depuis Claude").owner, self.user)

    def test_write_validation_error_is_reported(self):
        result = self._call("awtodo_api_write", {"method": "POST", "path": "tasks/", "body": {}})
        self.assertTrue(result["isError"])
        self.assertIn("HTTP 400", result["content"][0]["text"])

    def test_denied_endpoint(self):
        result = self._call("awtodo_api_write", {"method": "POST", "path": "integrations/api-keys/", "body": {}})
        self.assertTrue(result["isError"])
        self.assertIn("pas accessible", result["content"][0]["text"])

    def test_deactivated_account_loses_access(self):
        self.user.account_status = "desactive"
        self.user.is_active = False
        self.user.save()
        response = _mcp(self.client, {"jsonrpc": "2.0", "id": 1, "method": "ping"}, self.token)
        self.assertEqual(response.status_code, 401)


class NormalizePathTests(TestCase):
    def test_variants(self):
        for raw in ("tasks", "/tasks/", "/api/v1/tasks", "api/v1/tasks/"):
            self.assertEqual(normalize_path(raw), "tasks/")

    def test_rejects_query_and_traversal(self):
        for raw in ("tasks/?status=x", "tasks/../accounts/login/", ""):
            with self.assertRaises(ApiCallError):
                normalize_path(raw)
