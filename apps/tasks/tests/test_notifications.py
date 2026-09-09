from django.test import TestCase

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task
from apps.tasks.services import add_comment, assign_task, validate_task
from apps.tasks.signals import task_assigned, task_commented


class TaskSignalsTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.manager = User.objects.create_user(username="manager-notif")
        self.member = User.objects.create_user(username="member-notif")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Corriger le bug", task_type="correction",
            status="disponible",
        )

    def test_assign_task_sends_task_assigned_signal(self):
        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        task_assigned.connect(handler)
        try:
            assign_task(actor=self.manager, task=self.task, assignee=self.member)
        finally:
            task_assigned.disconnect(handler)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["task"], self.task)
        self.assertEqual(received[0]["actor"], self.manager)

    def test_validate_task_with_assignee_sends_task_assigned_signal(self):
        pending = Task.objects.create(
            project=self.project, version=self.version, title="Autre tâche", task_type="correction",
            status="en_attente_validation",
        )
        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        task_assigned.connect(handler)
        try:
            validate_task(actor=self.manager, task=pending, assignee=self.member)
        finally:
            task_assigned.disconnect(handler)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["task"], pending)
        self.assertEqual(received[0]["actor"], self.manager)

    def test_add_comment_sends_task_commented_signal(self):
        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        task_commented.connect(handler)
        try:
            comment = add_comment(actor=self.member, task=self.task, content="On regarde ça")
        finally:
            task_commented.disconnect(handler)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["task"], self.task)
        self.assertEqual(received[0]["comment"], comment)
        self.assertEqual(received[0]["actor"], self.member)
