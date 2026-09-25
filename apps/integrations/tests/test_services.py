from django.test import TestCase

from apps.accounts.models import Organisation, User
from apps.integrations.models import ApiKey
from apps.integrations.services import (
    IntegrationPermissionError,
    IntegrationValidationError,
    generate_api_key,
    list_api_keys,
    resolve_api_key,
    revoke_api_key,
)


class IntegrationServicesTestCase(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org")
        self.other_org = Organisation.objects.create(name="Autre org")
        self.admin = User.objects.create(username="admin", organisation=self.org, organisation_role="admin")
        self.member = User.objects.create(username="membre", organisation=self.org)
        self.platform_admin = User.objects.create(
            username="plat", organisation=self.other_org, is_platform_admin=True
        )


class GenerateApiKeyTests(IntegrationServicesTestCase):
    def test_org_admin_generates_key(self):
        api_key, raw_key = generate_api_key(actor=self.admin, organisation=self.org, name="GLPI")

        self.assertTrue(raw_key.startswith("awt_"))
        self.assertEqual(api_key.key_prefix, raw_key[:12])
        self.assertNotEqual(api_key.key_hash, raw_key)
        self.assertEqual(api_key.organisation, self.org)
        self.assertTrue(api_key.service_account.is_service_account)
        self.assertEqual(api_key.service_account.organisation, self.org)

    def test_platform_admin_generates_key_for_any_org(self):
        api_key, _ = generate_api_key(actor=self.platform_admin, organisation=self.org, name="GLPI")
        self.assertEqual(api_key.organisation, self.org)

    def test_member_cannot_generate_key(self):
        with self.assertRaises(IntegrationPermissionError):
            generate_api_key(actor=self.member, organisation=self.org, name="GLPI")

    def test_name_required(self):
        with self.assertRaises(IntegrationValidationError):
            generate_api_key(actor=self.admin, organisation=self.org, name="  ")

    def test_two_keys_share_the_same_service_account(self):
        first, _ = generate_api_key(actor=self.admin, organisation=self.org, name="GLPI")
        second, _ = generate_api_key(actor=self.admin, organisation=self.org, name="Power Automate")
        self.assertEqual(first.service_account_id, second.service_account_id)


class ListApiKeysTests(IntegrationServicesTestCase):
    def test_org_admin_lists_keys(self):
        generate_api_key(actor=self.admin, organisation=self.org, name="GLPI")
        keys = list_api_keys(actor=self.admin, organisation=self.org)
        self.assertEqual(keys.count(), 1)

    def test_member_cannot_list_keys(self):
        with self.assertRaises(IntegrationPermissionError):
            list_api_keys(actor=self.member, organisation=self.org)


class RevokeApiKeyTests(IntegrationServicesTestCase):
    def test_org_admin_revokes_key(self):
        api_key, _ = generate_api_key(actor=self.admin, organisation=self.org, name="GLPI")
        revoked = revoke_api_key(actor=self.admin, api_key=api_key)
        self.assertFalse(revoked.is_active)
        self.assertIsNotNone(revoked.revoked_at)

    def test_member_cannot_revoke_key(self):
        api_key, _ = generate_api_key(actor=self.admin, organisation=self.org, name="GLPI")
        with self.assertRaises(IntegrationPermissionError):
            revoke_api_key(actor=self.member, api_key=api_key)

    def test_cannot_revoke_twice(self):
        api_key, _ = generate_api_key(actor=self.admin, organisation=self.org, name="GLPI")
        revoke_api_key(actor=self.admin, api_key=api_key)
        with self.assertRaises(IntegrationValidationError):
            revoke_api_key(actor=self.admin, api_key=api_key)


class ResolveApiKeyTests(IntegrationServicesTestCase):
    def test_resolves_active_key(self):
        api_key, raw_key = generate_api_key(actor=self.admin, organisation=self.org, name="GLPI")
        resolved = resolve_api_key(raw_key)
        self.assertEqual(resolved.id, api_key.id)
        self.assertIsNotNone(ApiKey.objects.get(id=api_key.id).last_used_at)

    def test_unknown_key_resolves_to_none(self):
        self.assertIsNone(resolve_api_key("awt_does-not-exist"))

    def test_revoked_key_resolves_to_none(self):
        api_key, raw_key = generate_api_key(actor=self.admin, organisation=self.org, name="GLPI")
        revoke_api_key(actor=self.admin, api_key=api_key)
        self.assertIsNone(resolve_api_key(raw_key))
