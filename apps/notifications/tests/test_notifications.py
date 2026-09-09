from django.test import TestCase

from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task


class NotificationModelTests(TestCase):
    def test_creates_notification_linked_to_task(self):
        recipient = User.objects.create_user(username="alice-notif")
        project = Project.objects.create(name="Projet Test")
        version = ProjectVersion.objects.create(project=project, label="v1", is_current=True)
        ProjectMembership.objects.create(project=project, user=recipient, role="membre")
        task = Task.objects.create(project=project, version=version, title="Corriger le bug", task_type="correction")

        notification = Notification.objects.create(
            recipient=recipient,
            verb="task_assigned",
            message="On vous a assigné une tâche.",
            task=task,
        )

        self.assertEqual(notification.recipient, recipient)
        self.assertEqual(notification.task, task)
        self.assertIsNone(notification.incident)
        self.assertFalse(notification.is_read)


from django.core import mail

from apps.accounts.models import Team, TeamMembership
from apps.incidents.models import Incident
from apps.tasks.services import add_comment as add_task_comment
from apps.tasks.services import assign_task
from apps.incidents.services import add_comment as add_incident_comment


class NotificationSignalIntegrationTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test Notif")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.manager = User.objects.create_user(username="manager-notif-2", email="manager@example.com")
        self.member = User.objects.create_user(username="member-notif-2", email="member@example.com")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Corriger le bug", task_type="correction",
            status="disponible",
        )

        self.team = Team.objects.create(name="Équipe Test Notif 2")
        TeamMembership.objects.create(team=self.team, user=self.member)
        TeamMembership.objects.create(team=self.team, user=self.manager)
        self.incident = Incident.objects.create(team=self.team, title="Panne réseau", assigned_to=self.member)

    def test_assign_task_creates_notification_and_sends_email(self):
        assign_task(actor=self.manager, task=self.task, assignee=self.member)

        notification = Notification.objects.get(recipient=self.member, verb="task_assigned")
        self.assertIn("Corriger le bug", notification.message)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["member@example.com"])

    def test_assign_task_to_self_does_not_notify(self):
        # `assign_task` n'est normalement jamais appelé par l'assigné
        # lui-même (c'est le rôle de `claim_task`), mais la garde de
        # `notify_task_assigned` doit rester silencieuse dans ce cas plutôt
        # que de planter, au cas où.
        assign_task(actor=self.manager, task=self.task, assignee=self.manager)

        self.assertFalse(Notification.objects.filter(verb="task_assigned").exists())

    def test_comment_on_unassigned_task_does_not_notify(self):
        add_task_comment(actor=self.member, task=self.task, content="Personne assigné, pas de destinataire")

        self.assertFalse(Notification.objects.filter(verb="task_commented").exists())

    def test_comment_by_assignee_does_not_self_notify(self):
        assign_task(actor=self.manager, task=self.task, assignee=self.member)
        mail.outbox.clear()

        add_task_comment(actor=self.member, task=self.task, content="Je m'en occupe")

        self.assertFalse(Notification.objects.filter(verb="task_commented").exists())

    def test_comment_by_someone_else_notifies_task_assignee(self):
        assign_task(actor=self.manager, task=self.task, assignee=self.member)
        mail.outbox.clear()

        add_task_comment(actor=self.manager, task=self.task, content="Des nouvelles ?")

        notification = Notification.objects.get(recipient=self.member, verb="task_commented")
        self.assertIn("Corriger le bug", notification.message)

    def test_comment_on_incident_notifies_assignee(self):
        add_incident_comment(actor=self.manager, incident=self.incident, content="Ça avance ?")

        notification = Notification.objects.get(recipient=self.member, verb="incident_commented")
        self.assertIn("Panne réseau", notification.message)


from django.test import override_settings
from rest_framework.test import APITestCase


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
class NotificationApiTests(APITestCase):
    def setUp(self):
        self.recipient = User.objects.create_user(username="notif-api-recipient")
        self.other_user = User.objects.create_user(username="notif-api-other")
        self.notification = Notification.objects.create(
            recipient=self.recipient, verb="task_assigned", message="Test"
        )

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_list_only_returns_own_notifications(self):
        Notification.objects.create(recipient=self.other_user, verb="task_assigned", message="Pas pour vous")

        response = self.client.get("/api/v1/notifications/", **self.as_user(self.recipient))

        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()]
        self.assertEqual(ids, [str(self.notification.id)])

    def test_mark_read(self):
        response = self.client.post(
            f"/api/v1/notifications/{self.notification.id}/mark-read/", **self.as_user(self.recipient)
        )

        self.assertEqual(response.status_code, 200)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_cannot_mark_read_someone_elses_notification(self):
        response = self.client.post(
            f"/api/v1/notifications/{self.notification.id}/mark-read/", **self.as_user(self.other_user)
        )

        # 404, pas 403 : get_queryset() scope déjà par destinataire, même
        # principe que le scoping par appartenance déjà en place ailleurs.
        self.assertEqual(response.status_code, 404)

    def test_mark_all_read(self):
        Notification.objects.create(recipient=self.recipient, verb="task_commented", message="Deuxième")

        response = self.client.post("/api/v1/notifications/mark-all-read/", **self.as_user(self.recipient))

        self.assertEqual(response.status_code, 204)
        self.assertEqual(Notification.objects.filter(recipient=self.recipient, is_read=False).count(), 0)

    def test_unread_count(self):
        Notification.objects.create(recipient=self.recipient, verb="task_commented", message="Deuxième")

        response = self.client.get("/api/v1/notifications/unread-count/", **self.as_user(self.recipient))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
