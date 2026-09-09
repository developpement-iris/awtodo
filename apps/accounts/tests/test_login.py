from django.test import TestCase
from rest_framework.test import APITestCase

from apps.accounts.models import Organisation, User
from apps.accounts.services import AccountValidationError, authenticate_user


class AuthenticateUserServiceTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.user = User.objects.create_user(username="alice-login", organisation=self.org)
        self.user.set_password("Un-mot-de-passe-valide-1")
        self.user.save(update_fields=["password"])

    def test_correct_credentials_succeed(self):
        user = authenticate_user(username="alice-login", password="Un-mot-de-passe-valide-1")

        self.assertEqual(user, self.user)

    def test_wrong_password_rejected(self):
        with self.assertRaises(AccountValidationError):
            authenticate_user(username="alice-login", password="wrong")

    def test_unknown_username_rejected(self):
        with self.assertRaises(AccountValidationError):
            authenticate_user(username="nobody", password="whatever")

    def test_pending_account_rejected(self):
        pending = User.objects.create_user(username="bob-pending", organisation=self.org, account_status="pending")
        pending.set_password("Un-mot-de-passe-valide-1")
        pending.save(update_fields=["password"])

        with self.assertRaises(AccountValidationError):
            authenticate_user(username="bob-pending", password="Un-mot-de-passe-valide-1")


class LoginApiTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.user = User.objects.create_user(username="carole-login", organisation=self.org)
        self.user.set_password("Un-mot-de-passe-valide-1")
        self.user.save(update_fields=["password"])

    def test_login_returns_tokens_and_user(self):
        response = self.client.post(
            "/api/v1/accounts/login/",
            {"username": "carole-login", "password": "Un-mot-de-passe-valide-1"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("access", payload)
        self.assertIn("refresh", payload)
        self.assertEqual(payload["user"]["username"], "carole-login")

    def test_login_with_wrong_password_returns_400(self):
        response = self.client.post(
            "/api/v1/accounts/login/",
            {"username": "carole-login", "password": "wrong"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_me_requires_authentication(self):
        response = self.client.get("/api/v1/accounts/me/")

        self.assertEqual(response.status_code, 401)

    def test_me_with_jwt_from_login_returns_user(self):
        login_response = self.client.post(
            "/api/v1/accounts/login/",
            {"username": "carole-login", "password": "Un-mot-de-passe-valide-1"},
            content_type="application/json",
        )
        access = login_response.json()["access"]

        response = self.client.get("/api/v1/accounts/me/", HTTP_AUTHORIZATION=f"Bearer {access}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "carole-login")
