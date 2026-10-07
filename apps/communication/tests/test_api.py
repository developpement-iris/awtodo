from unittest.mock import Mock, patch

from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Organisation, Team, User
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


# --- Canaux au niveau groupe (session du 2026-10-07) -----------------------


@override_settings(
    DEBUG=True,
    REST_FRAMEWORK={
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
        "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.DebugUserIdAuthentication"],
    },
)
class TeamScopedChannelApiTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org")
        self.team = Team.objects.create(name="Groupe", organisation=self.org)
        # Deux projets collaboratifs du même groupe, chacun avec son propre
        # chef de projet — vérifie que la règle "chef de projet d'UN projet
        # du groupe" n'est pas limitée au chef du projet courant.
        self.manager_a = User.objects.create(username="cp_a", organisation=self.org)
        self.manager_b = User.objects.create(username="cp_b", organisation=self.org)
        self.member = User.objects.create(username="mbr", organisation=self.org)
        self.outsider = User.objects.create(username="out", organisation=self.org)
        self.project_a = Project.objects.create(name="A", organisation=self.org, team=self.team, project_type="collaboratif")
        self.project_b = Project.objects.create(name="B", organisation=self.org, team=self.team, project_type="collaboratif")
        self.lone_project = Project.objects.create(name="Seul", organisation=self.org)  # pas de groupe
        ProjectMembership.objects.create(project=self.project_a, user=self.manager_a, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project_a, user=self.member, role="membre")
        ProjectMembership.objects.create(project=self.project_b, user=self.manager_b, role="chef_de_projet")
        # `manager_b` est aussi simple membre (pas chef) de `project_a` — un
        # scénario réaliste pour tester que le droit "canal groupe" vient de
        # son rôle de chef de projet ailleurs dans le groupe (project_b), pas
        # de son rôle sur le projet dont on ouvre l'onglet (project_a, où il
        # n'est que contributeur).
        ProjectMembership.objects.create(project=self.project_a, user=self.manager_b, role="membre")
        ProjectMembership.objects.create(project=self.lone_project, user=self.outsider, role="chef_de_projet")

    def _as(self, user):
        self.client.credentials(HTTP_X_DEBUG_USER_ID=str(user.id))

    def _channels_url(self, project):
        return f"/api/v1/communication/projects/{project.id}/channels/"

    def _payload(self, **overrides):
        payload = {
            "label": "Groupe Teams",
            "teams_channel_id": "19:abc@thread.tacv2",
            "teams_channel_name": "#groupe",
            "teams_webhook_url": "https://prod-00.westeurope.logic.azure.com/x",
            "scope": "team",
        }
        payload.update(overrides)
        return payload

    def test_manager_of_another_project_in_the_group_can_create_team_channel(self):
        # Chef de projet de B, crée un canal groupe depuis l'onglet de A.
        self._as(self.manager_b)
        r = self.client.post(self._channels_url(self.project_a), self._payload(), format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["scope"], "team")
        channel = CommunicationChannel.objects.get()
        self.assertIsNone(channel.project_id)
        self.assertEqual(channel.team_id, self.team.id)

    def test_member_cannot_create_team_channel(self):
        self._as(self.member)
        r = self.client.post(self._channels_url(self.project_a), self._payload(), format="json")
        self.assertEqual(r.status_code, 403)

    def test_individual_project_without_team_rejects_team_scope(self):
        self._as(self.outsider)
        r = self.client.post(self._channels_url(self.lone_project), self._payload(), format="json")
        self.assertEqual(r.status_code, 400)

    def test_team_channel_visible_from_every_project_of_the_group(self):
        self._as(self.manager_a)
        self.client.post(self._channels_url(self.project_a), self._payload(), format="json")
        r_a = self.client.get(self._channels_url(self.project_a))
        self._as(self.manager_b)  # seul manager_b a accès à project_b
        r_b = self.client.get(self._channels_url(self.project_b))
        self.assertEqual(len(r_a.data), 1)
        self.assertEqual(len(r_b.data), 1)
        self.assertEqual(r_a.data[0]["id"], r_b.data[0]["id"])

    def test_project_scoped_channel_not_visible_from_sibling_project(self):
        self._as(self.manager_a)
        self.client.post(self._channels_url(self.project_a), self._payload(scope="project"), format="json")
        r_a = self.client.get(self._channels_url(self.project_a))
        self._as(self.manager_b)  # seul manager_b a accès à project_b
        r_b = self.client.get(self._channels_url(self.project_b))
        self.assertEqual(len(r_a.data), 1)
        self.assertEqual(len(r_b.data), 0)

    def test_manager_of_sibling_project_can_archive_team_channel(self):
        self._as(self.manager_a)
        create_resp = self.client.post(self._channels_url(self.project_a), self._payload(), format="json")
        channel_id = create_resp.data["id"]
        self._as(self.manager_b)
        r = self.client.delete(f"{self._channels_url(self.project_b)}{channel_id}/")
        self.assertEqual(r.status_code, 204)
        self.assertEqual(CommunicationChannel.all_objects.get(id=channel_id).status, "archived")

    @patch("apps.communication.tasks.requests.post")
    def test_compose_can_target_a_team_channel_from_sibling_project(self, mock_post):
        mock_post.return_value = Mock(status_code=200, text="ok")
        self._as(self.manager_a)
        create_resp = self.client.post(self._channels_url(self.project_a), self._payload(), format="json")
        channel_id = create_resp.data["id"]
        self._as(self.manager_b)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(
                f"/api/v1/communication/projects/{self.project_b.id}/messages/",
                {"subject": "X", "body": "Y", "channel_ids": [channel_id]},
                format="json",
            )
        self.assertEqual(r.status_code, 201)
        delivery = CommunicationDelivery.objects.get()
        self.assertEqual(delivery.status, "envoye")
