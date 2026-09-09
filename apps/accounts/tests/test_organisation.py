from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Organisation, User
from apps.accounts.services import (
    AccountPermissionError,
    AccountValidationError,
    create_organisation,
    set_organisation_role,
)


class SetOrganisationRoleTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.other_org = Organisation.objects.create(name="Org B")
        self.admin = User.objects.create_user(username="admin1", organisation=self.org, organisation_role="admin")
        self.member = User.objects.create_user(username="member1", organisation=self.org, organisation_role="membre")
        self.outsider = User.objects.create_user(
            username="outsider1", organisation=self.other_org, organisation_role="admin"
        )

    def test_admin_promotes_member(self):
        updated = set_organisation_role(actor=self.admin, target_user=self.member, role="chef_de_projet")

        self.assertEqual(updated.organisation_role, "chef_de_projet")

    def test_non_admin_cannot_change_role(self):
        member2 = User.objects.create_user(username="member2", organisation=self.org)

        with self.assertRaises(AccountPermissionError):
            set_organisation_role(actor=self.member, target_user=member2, role="admin")

    def test_admin_cannot_change_role_outside_own_organisation(self):
        with self.assertRaises(AccountPermissionError):
            set_organisation_role(actor=self.admin, target_user=self.outsider, role="membre")

    def test_invalid_role_is_rejected(self):
        with self.assertRaises(AccountValidationError):
            set_organisation_role(actor=self.admin, target_user=self.member, role="super-admin")


class CreateOrganisationServiceTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org existante")
        self.platform_admin = User.objects.create_user(
            username="platform", organisation=self.org, is_platform_admin=True
        )
        self.regular_admin = User.objects.create_user(
            username="regular", organisation=self.org, organisation_role="admin"
        )

    def test_platform_admin_creates_organisation_and_first_admin(self):
        organisation, admin_user = create_organisation(
            actor=self.platform_admin,
            organisation_name="Nouvelle Org",
            admin_name="Jean Dupont",
            admin_email="jean.dupont@example.com",
        )

        self.assertEqual(organisation.name, "Nouvelle Org")
        self.assertEqual(admin_user.organisation, organisation)
        self.assertEqual(admin_user.organisation_role, "admin")
        self.assertEqual(admin_user.first_name, "Jean")
        self.assertEqual(admin_user.last_name, "Dupont")
        self.assertEqual(admin_user.username, "jean.dupont")

    def test_organisation_admin_without_platform_flag_is_rejected(self):
        with self.assertRaises(AccountPermissionError):
            create_organisation(
                actor=self.regular_admin,
                organisation_name="Autre Org",
                admin_name="Marie Curie",
                admin_email="marie@example.com",
            )

    def test_username_collision_is_disambiguated(self):
        User.objects.create_user(username="jean.dupont", organisation=self.org)

        _, admin_user = create_organisation(
            actor=self.platform_admin,
            organisation_name="Encore une Org",
            admin_name="Jean Dupont",
            admin_email="jean.dupont@example.com",
        )

        self.assertEqual(admin_user.username, "jean.dupont2")


@override_settings(
    DEBUG=True,
    REST_FRAMEWORK={
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "apps.accounts.authentication.DebugUserIdAuthentication",
            "rest_framework.authentication.SessionAuthentication",
        ],
    },
)
class OrganisationApiTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org existante")
        self.platform_admin = User.objects.create_user(
            username="platform", organisation=self.org, is_platform_admin=True
        )
        self.regular_user = User.objects.create_user(username="regular", organisation=self.org)

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_platform_admin_lists_organisations(self):
        response = self.client.get("/api/v1/accounts/organisations/", **self.as_user(self.platform_admin))

        self.assertEqual(response.status_code, 200)

    def test_non_platform_admin_cannot_list_organisations(self):
        response = self.client.get("/api/v1/accounts/organisations/", **self.as_user(self.regular_user))

        self.assertEqual(response.status_code, 403)

    def test_platform_admin_creates_organisation(self):
        response = self.client.post(
            "/api/v1/accounts/organisations/",
            {"organisation_name": "Filiale Est", "admin_name": "Ana Costa", "admin_email": "ana@example.com"},
            **self.as_user(self.platform_admin),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["name"], "Filiale Est")
        self.assertEqual(response.json()["admin"]["organisation_role"], "admin")

    def test_non_platform_admin_cannot_create_organisation(self):
        response = self.client.post(
            "/api/v1/accounts/organisations/",
            {"organisation_name": "Filiale Ouest", "admin_name": "Ana Costa", "admin_email": "ana2@example.com"},
            **self.as_user(self.regular_user),
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_changes_organisation_role_of_member(self):
        member = User.objects.create_user(username="member3", organisation=self.org)
        admin = User.objects.create_user(username="admin3", organisation=self.org, organisation_role="admin")

        response = self.client.patch(
            f"/api/v1/accounts/users/{member.id}/organisation-role/",
            {"organisation_role": "chef_de_projet"},
            content_type="application/json",
            **self.as_user(admin),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["organisation_role"], "chef_de_projet")

    def test_non_admin_cannot_change_organisation_role(self):
        member = User.objects.create_user(username="member4", organisation=self.org)

        response = self.client.patch(
            f"/api/v1/accounts/users/{member.id}/organisation-role/",
            {"organisation_role": "admin"},
            content_type="application/json",
            **self.as_user(self.regular_user),
        )

        self.assertEqual(response.status_code, 403)
