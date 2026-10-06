from unittest.mock import Mock, patch

from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Organisation, User
from apps.communication.models import CommunicationChannel, CommunicationDelivery, CommunicationMessage, O365Connection
from apps.incidents.services import create_incident
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task


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

    def _make_channel(self, **kwargs):
        defaults = {
            "project": self.project,
            "label": "X",
            "teams_channel_id": "19:abc@thread.tacv2",
            "teams_channel_name": "#suivi-projet",
            "teams_webhook_url": "https://prod-00.westeurope.logic.azure.com/x",
        }
        defaults.update(kwargs)
        return CommunicationChannel.objects.create(**defaults)

    # --- Canaux -------------------------------------------------------
    def test_manager_creates_teams_channel(self):
        self._as(self.manager)
        r = self.client.post(
            self._channels_url(),
            {
                "label": "Support",
                "teams_channel_id": "19:abc@thread.tacv2",
                "teams_channel_name": "#suivi-projet",
                "teams_webhook_url": "https://prod-00.westeurope.logic.azure.com/x",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(CommunicationChannel.objects.filter(project=self.project).count(), 1)

    def test_manager_creates_channel_with_long_power_automate_url(self):
        # Régression (session du 2026-10-06) : une URL de déclenchement Power
        # Platform signée (SAS) dépasse couramment 200 caractères, la limite
        # par défaut d'un URLField Django — provoquait un 500 non géré à
        # l'INSERT sur Postgres (silencieux sur SQLite, utilisé par les
        # tests, d'où l'assertion explicite sur `max_length` en plus du 201).
        self.assertEqual(CommunicationChannel._meta.get_field("teams_webhook_url").max_length, 1000)
        long_url = "https://prod-00.westeurope.logic.azure.com/workflows/" + ("a" * 220) + "?sig=" + ("b" * 100)
        self.assertGreater(len(long_url), 200)
        self._as(self.manager)
        r = self.client.post(
            self._channels_url(),
            {
                "label": "Support",
                "teams_channel_id": "19:abc@thread.tacv2",
                "teams_channel_name": "#suivi-projet",
                "teams_webhook_url": long_url,
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(
            CommunicationChannel.objects.get(project=self.project).teams_webhook_url, long_url
        )

    def test_member_cannot_create_channel(self):
        self._as(self.member)
        r = self.client.post(
            self._channels_url(),
            {"label": "X", "teams_channel_id": "1", "teams_channel_name": "#x", "teams_webhook_url": "https://x.io/y"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_teams_channel_requires_webhook(self):
        self._as(self.manager)
        r = self.client.post(
            self._channels_url(),
            {"label": "#canal", "teams_channel_id": "1", "teams_channel_name": "#canal"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_teams_channel_requires_channel_id(self):
        self._as(self.manager)
        r = self.client.post(
            self._channels_url(),
            {"label": "#canal", "teams_channel_name": "#canal", "teams_webhook_url": "https://x.io/y"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_reader_has_no_access_to_communication(self):
        self._as(self.reader)
        r = self.client.get(self._channels_url())
        self.assertEqual(r.status_code, 404)

    def test_archive_channel(self):
        channel = self._make_channel()
        self._as(self.manager)
        r = self.client.delete(f"{self._channels_url()}{channel.id}/")
        self.assertEqual(r.status_code, 204)
        channel.refresh_from_db()
        self.assertEqual(channel.status, "archived")
        # N'apparaît plus dans la liste des canaux actifs par défaut.
        self.assertEqual(len(self.client.get(self._channels_url()).data), 0)

    # --- Messages ---------------------------------------------------
    @patch("apps.communication.tasks.requests.post")
    def test_member_composes_and_sends_message(self, mock_post):
        mock_post.return_value = Mock(status_code=200, text="ok")
        channel = self._make_channel()
        self._as(self.member)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(
                f"/api/v1/communication/projects/{self.project.id}/messages/",
                {"subject": "Point", "body": "Bonjour", "channel_ids": [str(channel.id)]},
                format="json",
            )
        self.assertEqual(r.status_code, 201)
        message = CommunicationMessage.objects.get()
        self.assertEqual(message.status, "envoye")  # CELERY_TASK_ALWAYS_EAGER : envoi synchrone dans le test
        self.assertEqual(message.trigger, "manuel")
        self.assertEqual(message.created_by, self.member)
        delivery = CommunicationDelivery.objects.get(message=message, channel=channel)
        self.assertEqual(delivery.status, "envoye")
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["channel_id"], channel.teams_channel_id)
        self.assertEqual(payload["channel_name"], channel.teams_channel_name)
        self.assertEqual(payload["subject"], "Point")

    @patch("apps.communication.tasks.requests.post")
    def test_channel_failure_does_not_block_others(self, mock_post):
        ok_channel = self._make_channel(label="OK", teams_channel_id="1")
        ko_channel = self._make_channel(label="KO", teams_channel_id="2")

        def _side_effect(url, json, timeout):
            if json["channel_id"] == "2":
                return Mock(status_code=500, text="boom")
            return Mock(status_code=202, text="")

        mock_post.side_effect = _side_effect
        self._as(self.member)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(
                f"/api/v1/communication/projects/{self.project.id}/messages/",
                {"subject": "X", "body": "Y", "channel_ids": [str(ok_channel.id), str(ko_channel.id)]},
                format="json",
            )
        self.assertEqual(r.status_code, 201)
        message = CommunicationMessage.objects.get()
        self.assertEqual(message.status, "echec")
        self.assertEqual(
            CommunicationDelivery.objects.get(message=message, channel=ok_channel).status, "envoye"
        )
        self.assertEqual(
            CommunicationDelivery.objects.get(message=message, channel=ko_channel).status, "echec"
        )

    # --- Gabarit de payload personnalisable (session du 2026-09-28) -----
    def test_custom_payload_template_resolves_task_fields(self):
        version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        task = Task.objects.create(
            project=self.project, version=version, title="Corriger le bug", task_type="correction", priority="haute"
        )
        channel = self._make_channel(
            payload_template={
                "titre_tache": "{{task.title}}",
                "priorite": "{{task.priority}}",
                "source": "awtodo-custom",  # valeur littérale, pas un placeholder
                "inconnu": "{{task.champ_qui_n_existe_pas}}",
            }
        )
        with patch("apps.communication.tasks.requests.post") as mock_post:
            mock_post.return_value = Mock(status_code=200, text="ok")
            self._as(self.member)
            with self.captureOnCommitCallbacks(execute=True):
                r = self.client.post(
                    f"/api/v1/communication/projects/{self.project.id}/messages/",
                    {
                        "subject": "Point",
                        "body": "Bonjour",
                        "channel_ids": [str(channel.id)],
                        "task_id": str(task.id),
                    },
                    format="json",
                )
        self.assertEqual(r.status_code, 201)
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["titre_tache"], "Corriger le bug")
        self.assertEqual(payload["priorite"], "haute")
        self.assertEqual(payload["source"], "awtodo-custom")
        self.assertEqual(payload["inconnu"], "")  # champ inconnu résolu en chaîne vide, jamais une erreur
        # Les champs par défaut (subject/body/...) ne sont plus envoyés dès
        # qu'un gabarit personnalisé est défini — le gabarit remplace
        # entièrement le payload par défaut, pas un complément.
        self.assertNotIn("subject", payload)
        self.assertEqual(str(r.data["task"]), str(task.id))

    def test_channel_rejects_invalid_payload_template(self):
        self._as(self.manager)
        r = self.client.post(
            self._channels_url(),
            {
                "label": "X",
                "teams_channel_id": "1",
                "teams_channel_name": "#x",
                "teams_webhook_url": "https://x.io/y",
                "payload_template": {"cle": ["pas", "une", "chaine"]},
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_compose_rejects_task_from_another_project(self):
        other_project = Project.objects.create(name="Autre", organisation=self.org)
        version = ProjectVersion.objects.create(project=other_project, label="v1", is_current=True)
        task = Task.objects.create(
            project=other_project, version=version, title="Ailleurs", task_type="correction"
        )
        channel = self._make_channel()
        self._as(self.member)
        r = self.client.post(
            f"/api/v1/communication/projects/{self.project.id}/messages/",
            {"subject": "X", "body": "Y", "channel_ids": [str(channel.id)], "task_id": str(task.id)},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_compose_requires_a_channel(self):
        self._as(self.member)
        r = self.client.post(
            f"/api/v1/communication/projects/{self.project.id}/messages/",
            {"subject": "X", "body": "Y", "channel_ids": []},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_reader_cannot_compose(self):
        channel = self._make_channel()
        self._as(self.reader)
        r = self.client.post(
            f"/api/v1/communication/projects/{self.project.id}/messages/",
            {"subject": "X", "body": "Y", "channel_ids": [str(channel.id)]},
            format="json",
        )
        self.assertEqual(r.status_code, 404)  # onglet inaccessible au lecteur

    # --- Connexion O365 (synchro Outlook uniquement) ----------------
    def test_org_admin_updates_o365_connection(self):
        self._as(self.org_admin)
        r = self.client.put(
            "/api/v1/communication/o365/",
            {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
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
