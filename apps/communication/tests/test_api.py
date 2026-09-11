from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Organisation, User
from apps.communication.models import CommunicationChannel, CommunicationMessage, O365Connection
from apps.incidents.services import create_incident
from apps.projects.models import Project, ProjectMembership


@override_settings(
    DEBUG=True,
    REST_FRAMEWORK={
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
        "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.DebugUserIdAuthentication"],
    },
)
class CommunicationApiTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org")
        self.manager = User.objects.create(username="cp", organisation=self.org)
        self.member = User.objects.create(username="mbr", organisation=self.org)
        self.reader = User.objects.create(username="lect", organisation=self.org)
        self.org_admin = User.objects.create(
            username="admin", organisation=self.org, organisation_role="admin"
        )
        self.project = Project.objects.create(name="P", organisation=self.org)
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        ProjectMembership.objects.create(project=self.project, user=self.reader, role="lecteur")

    def _as(self, user):
        self.client.credentials(HTTP_X_DEBUG_USER_ID=str(user.id))

    def _channels_url(self):
        return f"/api/v1/communication/projects/{self.project.id}/channels/"

    # --- Canaux -------------------------------------------------------
    def test_manager_creates_email_channel(self):
        self._as(self.manager)
        r = self.client.post(
            self._channels_url(),
            {"channel_type": "email", "label": "Support", "email": "support@x.io"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(CommunicationChannel.objects.filter(project=self.project).count(), 1)

    def test_member_cannot_create_channel(self):
        self._as(self.member)
        r = self.client.post(
            self._channels_url(),
            {"channel_type": "email", "label": "X", "email": "x@x.io"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_email_channel_requires_address(self):
        self._as(self.manager)
        r = self.client.post(
            self._channels_url(), {"channel_type": "email", "label": "X"}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_teams_channel_requires_webhook(self):
        self._as(self.manager)
        r = self.client.post(
            self._channels_url(), {"channel_type": "teams", "label": "#canal"}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_reader_has_no_access_to_communication(self):
        self._as(self.reader)
        r = self.client.get(self._channels_url())
        self.assertEqual(r.status_code, 404)

    def test_archive_channel(self):
        channel = CommunicationChannel.objects.create(
            project=self.project, channel_type="email", label="X", email="x@x.io"
        )
        self._as(self.manager)
        r = self.client.delete(f"{self._channels_url()}{channel.id}/")
        self.assertEqual(r.status_code, 204)
        channel.refresh_from_db()
        self.assertEqual(channel.status, "archived")
        # N'apparaît plus dans la liste des canaux actifs par défaut.
        self.assertEqual(len(self.client.get(self._channels_url()).data), 0)

    # --- Messages ---------------------------------------------------
    def test_member_composes_pending_message(self):
        channel = CommunicationChannel.objects.create(
            project=self.project, channel_type="email", label="X", email="x@x.io"
        )
        self._as(self.member)
        r = self.client.post(
            f"/api/v1/communication/projects/{self.project.id}/messages/",
            {"subject": "Point", "body": "Bonjour", "channel_ids": [str(channel.id)]},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        message = CommunicationMessage.objects.get()
        self.assertEqual(message.status, "en_attente")  # rien n'est envoyé dans cette passe
        self.assertEqual(message.trigger, "manuel")
        self.assertEqual(message.created_by, self.member)

    def test_compose_requires_a_channel(self):
        self._as(self.member)
        r = self.client.post(
            f"/api/v1/communication/projects/{self.project.id}/messages/",
            {"subject": "X", "body": "Y", "channel_ids": []},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_reader_cannot_compose(self):
        channel = CommunicationChannel.objects.create(
            project=self.project, channel_type="email", label="X", email="x@x.io"
        )
        self._as(self.reader)
        r = self.client.post(
            f"/api/v1/communication/projects/{self.project.id}/messages/",
            {"subject": "X", "body": "Y", "channel_ids": [str(channel.id)]},
            format="json",
        )
        self.assertEqual(r.status_code, 404)  # onglet inaccessible au lecteur

    # --- Connexion O365 -------------------------------------------
    def test_org_admin_updates_o365_connection(self):
        self._as(self.org_admin)
        r = self.client.put(
            "/api/v1/communication/o365/",
            {"tenant_id": "t", "client_id": "c", "client_secret": "s", "sender_mailbox": "no-reply@x.io"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_configured"])
        self.assertNotIn("client_secret", r.data)  # jamais renvoyé en clair
        self.assertTrue(O365Connection.objects.get(organisation=self.org).is_configured)

    def test_non_admin_cannot_update_o365_connection(self):
        self._as(self.manager)
        r = self.client.put(
            "/api/v1/communication/o365/", {"tenant_id": "t"}, format="json"
        )
        self.assertEqual(r.status_code, 403)

    # --- Incident : auteur transmis par le ticketing ---------------
    def test_incident_carries_author_from_ticketing(self):
        incident = create_incident(
            title="Bug",
            project=self.project,
            author_name="Client X",
            author_email="client@ext.io",
            actor=None,
        )
        self.assertEqual(incident.author_name, "Client X")
        self.assertEqual(incident.author_email, "client@ext.io")
