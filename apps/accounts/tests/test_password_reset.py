from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Organisation, PasswordResetRequest, User
from apps.accounts.services import (
    AccountValidationError,
    authenticate_user,
    confirm_password_reset,
    request_password_reset,
)


@override_settings(PASSWORD_RESET_DIRECT_LINK=False)
class RequestPasswordResetServiceTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.user = User.objects.create_user(
            username="oublie-pass", email="oublie@example.com", organisation=self.org
        )
        self.user.set_password("Un-mot-de-passe-valide-1")
        self.user.save(update_fields=["password"])

    def test_request_by_username_creates_pending_request_and_sends_email(self):
        reset = request_password_reset(identifier="oublie-pass")

        self.assertIsNotNone(reset)
        self.assertEqual(reset.status, "pending")
        self.assertEqual(reset.user, self.user)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("oublie@example.com", mail.outbox[0].to)

    def test_request_by_email_case_insensitive_also_works(self):
        reset = request_password_reset(identifier="OUBLIE@example.com")

        self.assertIsNotNone(reset)
        self.assertEqual(reset.user, self.user)

    def test_reset_link_in_email_is_absolute_and_clickable(self):
        request_password_reset(identifier="oublie-pass")
        reset = PasswordResetRequest.objects.get(user=self.user)

        self.assertIn(f"/reset-password/{reset.token}/", mail.outbox[0].body)
        self.assertTrue(mail.outbox[0].alternatives)
        html_body = mail.outbox[0].alternatives[0][0]
        self.assertIn(f'href="', html_body)
        self.assertIn(str(reset.token), html_body)

    def test_unknown_identifier_returns_none_without_error_or_email(self):
        # Pas d'énumération de comptes : ni exception, ni email — juste rien.
        result = request_password_reset(identifier="ne-existe-pas")

        self.assertIsNone(result)
        self.assertEqual(len(mail.outbox), 0)

    def test_pending_account_is_not_eligible(self):
        User.objects.create_user(
            username="jamais-active",
            email="pending@example.com",
            organisation=self.org,
            account_status="pending",
        )

        result = request_password_reset(identifier="jamais-active")

        self.assertIsNone(result)
        self.assertEqual(len(mail.outbox), 0)

    def test_blank_identifier_raises_validation_error(self):
        with self.assertRaises(AccountValidationError):
            request_password_reset(identifier="  ")

    def test_second_request_expires_the_first_pending_one(self):
        first = request_password_reset(identifier="oublie-pass")
        second = request_password_reset(identifier="oublie-pass")

        first.refresh_from_db()
        self.assertEqual(first.status, "expired")
        self.assertEqual(second.status, "pending")
        self.assertEqual(len(mail.outbox), 2)


@override_settings(PASSWORD_RESET_DIRECT_LINK=True)
class RequestPasswordResetDirectLinkTests(TestCase):
    """Mode "phase de test" : pas d'email, le jeton est quand même créé/tourné."""

    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.user = User.objects.create_user(
            username="direct-link", email="direct@example.com", organisation=self.org
        )
        self.user.set_password("Un-mot-de-passe-valide-1")
        self.user.save(update_fields=["password"])

    def test_creates_token_but_sends_no_email(self):
        reset = request_password_reset(identifier="direct-link")

        self.assertIsNotNone(reset)
        self.assertEqual(reset.status, "pending")
        self.assertEqual(len(mail.outbox), 0)

    def test_still_expires_previous_pending_request(self):
        first = request_password_reset(identifier="direct-link")
        request_password_reset(identifier="direct-link")

        first.refresh_from_db()
        self.assertEqual(first.status, "expired")
        self.assertEqual(len(mail.outbox), 0)


class ConfirmPasswordResetServiceTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.user = User.objects.create_user(
            username="confirme-pass", email="confirme@example.com", organisation=self.org
        )
        self.user.set_password("Ancien-mot-de-passe-1")
        self.user.save(update_fields=["password"])
        self.reset = PasswordResetRequest.objects.create(user=self.user)

    def test_valid_token_updates_password(self):
        confirm_password_reset(token=self.reset.token, password="Nouveau-mot-de-passe-2")

        updated = authenticate_user(username="confirme-pass", password="Nouveau-mot-de-passe-2")
        self.assertEqual(updated, self.user)

    def test_confirm_marks_request_used(self):
        confirm_password_reset(token=self.reset.token, password="Nouveau-mot-de-passe-2")

        self.reset.refresh_from_db()
        self.assertEqual(self.reset.status, "used")
        self.assertIsNotNone(self.reset.used_at)

    def test_reusing_token_after_confirm_fails(self):
        confirm_password_reset(token=self.reset.token, password="Nouveau-mot-de-passe-2")

        with self.assertRaises(AccountValidationError):
            confirm_password_reset(token=self.reset.token, password="Encore-un-autre-3")

    def test_unknown_token_raises(self):
        with self.assertRaises(AccountValidationError):
            confirm_password_reset(token="00000000-0000-0000-0000-000000000000", password="Peu-importe-4")

    def test_expired_token_rejected(self):
        self.reset.created_at = timezone.now() - timedelta(hours=2)
        self.reset.save(update_fields=["created_at"])

        with self.assertRaises(AccountValidationError):
            confirm_password_reset(token=self.reset.token, password="Nouveau-mot-de-passe-2")

    def test_weak_password_rejected_by_validators(self):
        with self.assertRaises(AccountValidationError):
            confirm_password_reset(token=self.reset.token, password="1234")

    def test_missing_password_rejected(self):
        with self.assertRaises(AccountValidationError):
            confirm_password_reset(token=self.reset.token, password="")


class PasswordResetApiTests(APITestCase):
    def setUp(self):
        # Le throttle DRF ("anon": 20/min, config/settings/base.py) est mis en
        # cache Django, jamais réinitialisé entre tests (seule la base l'est,
        # via la transaction de TestCase) — une suite complète accumule assez
        # d'appels anonymes pour déclencher un 429 dans des tests sans rapport
        # (constaté avant cette classe, pas introduit par elle). `cache.clear()`
        # évite au moins que CETTE classe hérite d'un quota déjà entamé ou en
        # laisse un pour la suivante — ne corrige pas le problème plus large
        # (hors périmètre de cette passe, signalé séparément).
        cache.clear()
        self.org = Organisation.objects.create(name="Org A")
        self.user = User.objects.create_user(username="api-pass", email="api@example.com", organisation=self.org)
        self.user.set_password("Ancien-mot-de-passe-1")
        self.user.save(update_fields=["password"])

    @override_settings(PASSWORD_RESET_DIRECT_LINK=False)
    def test_request_endpoint_always_returns_200_in_email_mode(self):
        response = self.client.post(
            "/api/v1/accounts/password-reset/request/",
            {"identifier": "api-pass"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        response_unknown = self.client.post(
            "/api/v1/accounts/password-reset/request/",
            {"identifier": "personne-de-ce-nom"},
            content_type="application/json",
        )
        self.assertEqual(response_unknown.status_code, 200)
        # Même message générique dans les deux cas — pas d'énumération.
        self.assertEqual(response.json()["detail"], response_unknown.json()["detail"])

    @override_settings(PASSWORD_RESET_DIRECT_LINK=True)
    def test_request_endpoint_returns_reset_path_in_direct_link_mode(self):
        response = self.client.post(
            "/api/v1/accounts/password-reset/request/",
            {"identifier": "api-pass"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        reset = PasswordResetRequest.objects.get(user=self.user)
        self.assertEqual(response.json()["reset_path"], f"/reset-password/{reset.token}/")
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(PASSWORD_RESET_DIRECT_LINK=True)
    def test_request_endpoint_404_on_unknown_identifier_in_direct_link_mode(self):
        response = self.client.post(
            "/api/v1/accounts/password-reset/request/",
            {"identifier": "personne-de-ce-nom"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_detail_endpoint_is_public_and_returns_status(self):
        reset = PasswordResetRequest.objects.create(user=self.user)

        response = self.client.get(f"/api/v1/accounts/password-reset/{reset.token}/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "pending")
        self.assertFalse(payload["is_expired"])

    def test_detail_endpoint_404_on_unknown_token(self):
        response = self.client.get("/api/v1/accounts/password-reset/00000000-0000-0000-0000-000000000000/")

        self.assertEqual(response.status_code, 404)

    def test_confirm_endpoint_is_public_and_updates_password(self):
        reset = PasswordResetRequest.objects.create(user=self.user)

        response = self.client.post(
            f"/api/v1/accounts/password-reset/{reset.token}/confirm/",
            {"password": "Tout-nouveau-mot-de-passe-5"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        login_response = self.client.post(
            "/api/v1/accounts/login/",
            {"username": "api-pass", "password": "Tout-nouveau-mot-de-passe-5"},
            content_type="application/json",
        )
        self.assertEqual(login_response.status_code, 200)

    def test_confirm_endpoint_rejects_already_used_token(self):
        reset = PasswordResetRequest.objects.create(user=self.user)
        self.client.post(
            f"/api/v1/accounts/password-reset/{reset.token}/confirm/",
            {"password": "Tout-nouveau-mot-de-passe-5"},
            content_type="application/json",
        )

        response = self.client.post(
            f"/api/v1/accounts/password-reset/{reset.token}/confirm/",
            {"password": "Encore-un-autre-6"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
