from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Invitation, Organisation, Team, TeamMembership, User
from apps.accounts.services import (
    AccountPermissionError,
    AccountValidationError,
    accept_invitation,
    create_invitation,
)
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import create_project


class CreateInternalInvitationTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.admin = User.objects.create_user(username="admin5", organisation=self.org, organisation_role="admin")
        self.chef = User.objects.create_user(
            username="chef5", organisation=self.org, organisation_role="chef_de_projet"
        )
        self.team = Team.objects.create(name="Équipe X", organisation=self.org, created_by=self.chef)
        TeamMembership.objects.create(team=self.team, user=self.chef)
        self.other_team = Team.objects.create(name="Équipe Y", organisation=self.org, created_by=self.admin)
        self.plain_member = User.objects.create_user(username="member5", organisation=self.org)

    def test_admin_invites_new_internal_account(self):
        invitation = create_invitation(actor=self.admin, email="new@example.com", first_name="New", last_name="Guy")

        self.assertEqual(invitation.status, "pending")
        self.assertEqual(invitation.user.account_type, "interne")
        self.assertEqual(invitation.user.account_status, "pending")
        self.assertEqual(invitation.user.organisation, self.org)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("new@example.com", mail.outbox[0].to)

    def test_invitation_email_contains_an_absolute_clickable_link(self):
        invitation = create_invitation(actor=self.admin, email="linktest@example.com")

        sent = mail.outbox[0]
        expected_url = f"http://localhost:5173/invitations/{invitation.token}/"
        # Texte brut : lien absolu, pas un simple chemin relatif (invalide
        # dans un client mail réel) — voir apps/accounts/services.py >
        # _send_invitation_email, correctif du 2026-08-06 (soir).
        self.assertIn(expected_url, sent.body)
        # Version HTML : un vrai bouton cliquable (balise <a>), pas juste le
        # lien en texte.
        html_alternative = next(content for content, mimetype in sent.alternatives if mimetype == "text/html")
        self.assertIn(f'href="{expected_url}"', html_alternative)

    def test_chef_de_projet_invites_to_own_team(self):
        invitation = create_invitation(actor=self.chef, email="new2@example.com", team=self.team)

        self.assertEqual(invitation.team, self.team)

    def test_chef_de_projet_cannot_invite_to_foreign_team(self):
        with self.assertRaises(AccountPermissionError):
            create_invitation(actor=self.chef, email="new3@example.com", team=self.other_team)

    def test_plain_member_cannot_invite(self):
        with self.assertRaises(AccountPermissionError):
            create_invitation(actor=self.plain_member, email="new4@example.com")

    def test_inviting_existing_email_reuses_user(self):
        existing = User.objects.create_user(
            username="existing1", organisation=self.org, email="existing1@example.com"
        )

        invitation = create_invitation(actor=self.admin, email="existing1@example.com")

        self.assertEqual(invitation.user, existing)


class CreateExternalInvitationTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.chef = User.objects.create_user(username="chef6", organisation=self.org)
        self.project = create_project(actor=self.chef, name="Projet", project_type="individuel")
        self.other_member = User.objects.create_user(username="member6", organisation=self.org)
        ProjectMembership.objects.create(project=self.project, user=self.other_member, role="membre")

    def test_project_manager_invites_external_account(self):
        invitation = create_invitation(actor=self.chef, email="external@example.com", project=self.project)

        self.assertEqual(invitation.user.account_type, "externe")
        self.assertEqual(invitation.project, self.project)
        self.assertEqual(invitation.user.organisation, self.project.organisation)

    def test_non_manager_cannot_invite_external_account(self):
        with self.assertRaises(AccountPermissionError):
            create_invitation(actor=self.other_member, email="external2@example.com", project=self.project)


class AcceptInvitationTests(TestCase):
    VALID_PASSWORD = "Un-mot-de-passe-valide-1"

    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.admin = User.objects.create_user(username="admin6", organisation=self.org, organisation_role="admin")
        self.team = Team.objects.create(name="Équipe Z", organisation=self.org, created_by=self.admin)
        TeamMembership.objects.create(team=self.team, user=self.admin)

    def test_accepting_activates_account_and_joins_team(self):
        invitation = create_invitation(actor=self.admin, email="invitee1@example.com", team=self.team)

        accepted = accept_invitation(token=invitation.token, password=self.VALID_PASSWORD)

        self.assertEqual(accepted.status, "accepted")
        self.assertIsNotNone(accepted.accepted_at)
        invitation.user.refresh_from_db()
        self.assertEqual(invitation.user.account_status, "active")
        self.assertTrue(TeamMembership.objects.filter(team=self.team, user=invitation.user).exists())

    def test_accepting_sets_a_usable_password(self):
        invitation = create_invitation(actor=self.admin, email="invitee1b@example.com", team=self.team)
        self.assertFalse(invitation.user.has_usable_password())

        accept_invitation(token=invitation.token, password=self.VALID_PASSWORD)

        invitation.user.refresh_from_db()
        self.assertTrue(invitation.user.has_usable_password())
        self.assertTrue(invitation.user.check_password(self.VALID_PASSWORD))

    def test_accepting_project_invitation_joins_project(self):
        chef = User.objects.create_user(username="chef7", organisation=self.org)
        project = create_project(actor=chef, name="Projet ext", project_type="individuel")
        invitation = create_invitation(actor=chef, email="invitee2@example.com", project=project)

        accept_invitation(token=invitation.token, password=self.VALID_PASSWORD)

        self.assertTrue(ProjectMembership.objects.filter(project=project, user=invitation.user, role="membre").exists())

    def test_cannot_accept_twice(self):
        invitation = create_invitation(actor=self.admin, email="invitee3@example.com", team=self.team)
        accept_invitation(token=invitation.token, password=self.VALID_PASSWORD)

        with self.assertRaises(AccountValidationError):
            accept_invitation(token=invitation.token, password=self.VALID_PASSWORD)

    def test_unknown_token_is_rejected(self):
        import uuid

        with self.assertRaises(AccountValidationError):
            accept_invitation(token=uuid.uuid4())

    def test_missing_password_is_rejected(self):
        invitation = create_invitation(actor=self.admin, email="invitee4@example.com", team=self.team)

        with self.assertRaises(AccountValidationError):
            accept_invitation(token=invitation.token)

    def test_weak_password_is_rejected(self):
        invitation = create_invitation(actor=self.admin, email="invitee5@example.com", team=self.team)

        with self.assertRaises(AccountValidationError):
            accept_invitation(token=invitation.token, password="123")


# Permission par défaut `IsAuthenticated` comme en staging/production (et non
# l'`AllowAny` de dev) : c'est la seule config qui vérifie réellement que
# `retrieve`/`accept` restent joignables par un invité anonyme via le
# `get_permissions` de `InvitationViewSet`. Régression du lien d'activation
# "expiré ou invalide" en prod, session du 2026-09-09.
@override_settings(
    DEBUG=True,
    REST_FRAMEWORK={
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "apps.accounts.authentication.DebugUserIdAuthentication",
            "rest_framework.authentication.SessionAuthentication",
        ],
    },
)
class InvitationApiTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org A")
        self.admin = User.objects.create_user(username="admin7", organisation=self.org, organisation_role="admin")
        self.chef = User.objects.create_user(username="chef8", organisation=self.org)
        self.project = create_project(actor=self.chef, name="Projet API", project_type="individuel")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_create_internal_invitation_via_api(self):
        response = self.client.post(
            "/api/v1/accounts/invitations/",
            {"email": "apiuser@example.com", "first_name": "Api", "last_name": "User"},
            content_type="application/json",
            **self.as_user(self.admin),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "pending")

    def test_get_invitation_by_token_is_public(self):
        create_response = self.client.post(
            "/api/v1/accounts/invitations/",
            {"email": "apiuser2@example.com"},
            content_type="application/json",
            **self.as_user(self.admin),
        )
        token = create_response.json()["token"]

        response = self.client.get(f"/api/v1/accounts/invitations/{token}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "apiuser2@example.com")

    def test_accept_invitation_via_api_is_public(self):
        create_response = self.client.post(
            "/api/v1/accounts/invitations/",
            {"email": "apiuser3@example.com"},
            content_type="application/json",
            **self.as_user(self.admin),
        )
        token = create_response.json()["token"]

        response = self.client.post(
            f"/api/v1/accounts/invitations/{token}/accept/",
            {"password": "Un-mot-de-passe-valide-1"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "accepted")

    def test_accept_invitation_without_password_returns_400(self):
        create_response = self.client.post(
            "/api/v1/accounts/invitations/",
            {"email": "apiuser3b@example.com"},
            content_type="application/json",
            **self.as_user(self.admin),
        )
        token = create_response.json()["token"]

        response = self.client.post(f"/api/v1/accounts/invitations/{token}/accept/")

        self.assertEqual(response.status_code, 400)

    def test_invite_external_via_project_endpoint(self):
        response = self.client.post(
            f"/api/v1/projects/{self.project.id}/members/invite/",
            {"email": "externalapi@example.com"},
            content_type="application/json",
            **self.as_user(self.chef),
        )

        self.assertEqual(response.status_code, 201)
        invitation = Invitation.objects.get(email="externalapi@example.com")
        self.assertEqual(invitation.project, self.project)
        self.assertEqual(invitation.user.account_type, "externe")

    def test_non_manager_cannot_invite_external_via_project_endpoint(self):
        # Doit être membre du projet (sinon la portée par appartenance renvoie
        # 404 avant même d'atteindre la vérification de rôle — voir CLAUDE.md
        # > "Scoping des listes par appartenance") mais pas chef de projet,
        # pour tester précisément la restriction de rôle visée par ce test.
        outsider = User.objects.create_user(username="outsider3", organisation=self.org)
        ProjectMembership.objects.create(project=self.project, user=outsider, role="membre")

        response = self.client.post(
            f"/api/v1/projects/{self.project.id}/members/invite/",
            {"email": "externalapi2@example.com"},
            content_type="application/json",
            **self.as_user(outsider),
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_lists_org_invitations(self):
        self.client.post(
            "/api/v1/accounts/invitations/",
            {"email": "listtest@example.com"},
            content_type="application/json",
            **self.as_user(self.admin),
        )

        response = self.client.get("/api/v1/accounts/invitations/", **self.as_user(self.admin))

        self.assertEqual(response.status_code, 200)
        emails = [item["email"] for item in response.json()]
        self.assertIn("listtest@example.com", emails)

    def test_plain_member_cannot_list_invitations(self):
        plain = User.objects.create_user(username="plain1", organisation=self.org)

        response = self.client.get("/api/v1/accounts/invitations/", **self.as_user(plain))

        self.assertEqual(response.status_code, 403)

    def test_resend_marks_old_expired_and_creates_new(self):
        create_response = self.client.post(
            "/api/v1/accounts/invitations/",
            {"email": "resend@example.com"},
            content_type="application/json",
            **self.as_user(self.admin),
        )
        token = create_response.json()["token"]

        resend_response = self.client.post(f"/api/v1/accounts/invitations/{token}/resend/", **self.as_user(self.admin))

        self.assertEqual(resend_response.status_code, 201)
        self.assertNotEqual(resend_response.json()["token"], token)
        old = Invitation.objects.get(token=token)
        self.assertEqual(old.status, "expired")
