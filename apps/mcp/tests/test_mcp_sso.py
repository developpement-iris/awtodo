"""Connexion Microsoft sur la page OAuth du connecteur (session du 2026-11-20)."""

from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.core import signing
from django.test import TestCase, override_settings

from apps.accounts import sso
from apps.accounts.models import User
from apps.accounts.tests.test_sso import CLIENT, TENANT, FakeJwksClient, make_token

from ..views import SSO_NONCE_COOKIE, SSO_STATE_SALT

NEXT = "/o/authorize/?client_id=abc&response_type=code"


@override_settings(MICROSOFT_SSO_TENANT_ID=TENANT, MICROSOFT_SSO_CLIENT_ID=CLIENT)
class McpMicrosoftLoginTests(TestCase):
    def setUp(self):
        patcher = mock.patch.object(sso, "_jwks_client", return_value=FakeJwksClient())
        patcher.start()
        self.addCleanup(patcher.stop)

    def _start(self):
        response = self.client.get("/o/sso/microsoft/", {"next": NEXT})
        self.assertEqual(response.status_code, 302)
        params = {k: v[0] for k, v in parse_qs(urlparse(response["Location"]).query).items()}
        return response, params

    def _callback(self, params, **token_claims):
        token = make_token(nonce=params["nonce"], **token_claims)
        return self.client.post("/o/sso/microsoft/callback/", {"id_token": token, "state": params["state"]})

    def test_login_page_shows_microsoft_button(self):
        response = self.client.get("/o/login/", {"next": NEXT})
        self.assertContains(response, "Se connecter avec Microsoft")

    @override_settings(MICROSOFT_SSO_TENANT_ID="", MICROSOFT_SSO_CLIENT_ID="")
    def test_button_hidden_when_sso_not_configured(self):
        self.assertNotContains(self.client.get("/o/login/"), "Se connecter avec Microsoft")

    def test_start_redirects_to_microsoft(self):
        response, params = self._start()
        self.assertTrue(response["Location"].startswith(f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/authorize?"))
        self.assertEqual(params["client_id"], CLIENT)
        self.assertEqual(params["response_type"], "id_token")
        self.assertEqual(params["response_mode"], "form_post")
        self.assertEqual(params["redirect_uri"], "http://testserver/o/sso/microsoft/callback/")
        self.assertEqual(response.cookies[SSO_NONCE_COOKIE].value, params["nonce"])

    def test_callback_opens_session_and_resumes_oauth(self):
        _, params = self._start()
        response = self._callback(params)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], NEXT)
        user = User.objects.get(azure_oid="oid-alice")
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_callback_rejects_wrong_nonce(self):
        _, params = self._start()
        token = make_token(nonce="autre-nonce")
        response = self.client.post("/o/sso/microsoft/callback/", {"id_token": token, "state": params["state"]})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_callback_rejects_flow_started_in_another_browser(self):
        _, params = self._start()
        self.client.cookies.pop(SSO_NONCE_COOKIE)
        response = self._callback(params)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_callback_rejects_forged_state(self):
        response = self.client.post("/o/sso/microsoft/callback/", {"id_token": make_token(), "state": "falsifie"})
        self.assertEqual(response.status_code, 400)

    def test_callback_ignores_external_next(self):
        nonce = "n-1"
        state = signing.dumps({"next": "https://pirate.example/", "nonce": nonce}, salt=SSO_STATE_SALT)
        self.client.cookies[SSO_NONCE_COOKIE] = nonce
        response = self.client.post("/o/sso/microsoft/callback/", {"id_token": make_token(nonce=nonce), "state": state})
        self.assertEqual(response["Location"], "/")

    def test_deactivated_account_refused(self):
        User.objects.create_user(username="alice", email="alice@entreprise.fr", azure_oid="oid-alice", account_status="desactive", is_active=False)
        _, params = self._start()
        response = self._callback(params)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "désactivé", status_code=400)

    def test_microsoft_error_shows_message(self):
        _, params = self._start()
        response = self.client.post("/o/sso/microsoft/callback/", {"error": "access_denied", "state": params["state"]})
        self.assertContains(response, "annulée", status_code=400)
