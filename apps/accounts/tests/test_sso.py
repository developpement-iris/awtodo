"""Connexion Microsoft (session du 2026-11-16) : jetons signés avec une clé RSA
générée localement, le client JWKS de Microsoft étant remplacé par un faux qui
renvoie cette clé."""

import time
from unittest import mock

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts import sso
from apps.accounts.models import Invitation, Organisation, Team, TeamMembership, User
from apps.accounts.services import AccountValidationError, login_with_microsoft

TENANT = "11111111-2222-3333-4444-555555555555"
CLIENT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_token(key=PRIVATE_KEY, **overrides):
    now = int(time.time())
    claims = {
        "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
        "aud": CLIENT,
        "tid": TENANT,
        "oid": "oid-alice",
        "iat": now,
        "nbf": now,
        "exp": now + 3600,
        "name": "Alice Martin",
        "preferred_username": "alice@entreprise.fr",
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})


class FakeJwksClient:
    def get_signing_key_from_jwt(self, token):
        return mock.Mock(key=PRIVATE_KEY.public_key())


@override_settings(MICROSOFT_SSO_TENANT_ID=TENANT, MICROSOFT_SSO_CLIENT_ID=CLIENT)
class VerifyTokenTests(TestCase):
    def setUp(self):
        patcher = mock.patch.object(sso, "_jwks_client", return_value=FakeJwksClient())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_valid_token(self):
        claims = sso.verify_microsoft_id_token(make_token())
        self.assertEqual(claims["oid"], "oid-alice")

    def test_rejects_wrong_audience(self):
        with self.assertRaises(sso.MicrosoftTokenError):
            sso.verify_microsoft_id_token(make_token(aud="autre-application"))

    def test_rejects_other_tenant(self):
        other = "99999999-2222-3333-4444-555555555555"
        with self.assertRaises(sso.MicrosoftTokenError):
            sso.verify_microsoft_id_token(make_token(tid=other, iss=f"https://login.microsoftonline.com/{other}/v2.0"))

    def test_rejects_expired_token(self):
        with self.assertRaises(sso.MicrosoftTokenError):
            sso.verify_microsoft_id_token(make_token(exp=int(time.time()) - 3600))

    def test_rejects_foreign_signature(self):
        forged = make_token(key=rsa.generate_private_key(public_exponent=65537, key_size=2048))
        with self.assertRaises(sso.MicrosoftTokenError):
            sso.verify_microsoft_id_token(forged)

    def test_rejects_token_without_oid(self):
        with self.assertRaises(sso.MicrosoftTokenError):
            sso.verify_microsoft_id_token(make_token(oid=None))

    @override_settings(MICROSOFT_SSO_TENANT_ID="")
    def test_disabled_when_not_configured(self):
        self.assertFalse(sso.sso_config()["enabled"])
        with self.assertRaises(sso.MicrosoftTokenError):
            sso.verify_microsoft_id_token(make_token())


class LoginWithMicrosoftServiceTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")

    def claims(self, **overrides):
        claims = {"oid": "oid-alice", "preferred_username": "Alice@Entreprise.fr", "name": "Alice Martin"}
        claims.update(overrides)
        return claims

    def test_creates_internal_member_account(self):
        user = login_with_microsoft(self.claims())
        self.assertEqual(user.email, "alice@entreprise.fr")
        self.assertEqual(user.username, "alice")
        self.assertEqual((user.first_name, user.last_name), ("Alice", "Martin"))
        self.assertEqual(user.azure_oid, "oid-alice")
        self.assertEqual((user.account_type, user.account_status, user.organisation_role), ("interne", "active", "membre"))
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.team_memberships.exists())

    def test_second_login_reuses_account(self):
        first = login_with_microsoft(self.claims())
        again = login_with_microsoft(self.claims(preferred_username="autre@entreprise.fr"))
        self.assertEqual(first, again)
        self.assertEqual(User.objects.filter(azure_oid="oid-alice").count(), 1)

    def test_links_existing_account_by_email(self):
        existing = User.objects.create_user(username="amartin", email="alice@entreprise.fr", organisation=self.org)
        existing.set_password("Un-mot-de-passe-valide-1")
        existing.save()
        user = login_with_microsoft(self.claims())
        self.assertEqual(user, existing)
        existing.refresh_from_db()
        self.assertEqual(existing.azure_oid, "oid-alice")
        self.assertTrue(existing.check_password("Un-mot-de-passe-valide-1"))

    def test_refuses_email_linked_to_another_identity(self):
        User.objects.create_user(username="amartin", email="alice@entreprise.fr", azure_oid="oid-autre", organisation=self.org)
        with self.assertRaises(AccountValidationError):
            login_with_microsoft(self.claims())

    def test_refuses_deactivated_account(self):
        User.objects.create_user(
            username="amartin", email="alice@entreprise.fr", organisation=self.org, account_status="desactive", is_active=False
        )
        with self.assertRaises(AccountValidationError):
            login_with_microsoft(self.claims())

    def test_activates_pending_invitee_with_invitation_group(self):
        admin = User.objects.create_user(username="admin", organisation=self.org, organisation_role="admin")
        team = Team.objects.create(name="Dev", organisation=self.org, created_by=admin)
        invitee = User.objects.create_user(
            username="alice", email="alice@entreprise.fr", organisation=self.org, account_status="pending"
        )
        invitation = Invitation.objects.create(
            email=invitee.email, user=invitee, organisation=self.org, team=team, invited_by=admin
        )
        user = login_with_microsoft(self.claims())
        self.assertEqual(user, invitee)
        self.assertEqual(user.account_status, "active")
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, "accepted")
        self.assertTrue(TeamMembership.objects.filter(team=team, user=invitee).exists())

    def test_requires_an_email(self):
        with self.assertRaises(AccountValidationError):
            login_with_microsoft({"oid": "oid-x"})


@override_settings(MICROSOFT_SSO_TENANT_ID=TENANT, MICROSOFT_SSO_CLIENT_ID=CLIENT)
class MicrosoftLoginApiTests(APITestCase):
    def setUp(self):
        Organisation.objects.create(name="Org A")
        patcher = mock.patch.object(sso, "_jwks_client", return_value=FakeJwksClient())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_config_is_public(self):
        response = self.client.get("/api/v1/accounts/sso/microsoft/config/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"enabled": True, "tenant_id": TENANT, "client_id": CLIENT})

    def test_login_returns_awtodo_tokens(self):
        response = self.client.post("/api/v1/accounts/sso/microsoft/login/", {"id_token": make_token()}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["user"]["email"], "alice@entreprise.fr")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        me = self.client.get("/api/v1/accounts/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["username"], "alice")

    def test_invalid_token_is_refused(self):
        response = self.client.post("/api/v1/accounts/sso/microsoft/login/", {"id_token": "pas-un-jeton"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(azure_oid="oid-alice").exists())
