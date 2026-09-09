from django.test import TestCase

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task, TaskComment


class TaskCommentModelTests(TestCase):
    def test_creates_comment_on_task(self):
        project = Project.objects.create(name="Projet Test")
        version = ProjectVersion.objects.create(project=project, label="v1", is_current=True)
        author = User.objects.create_user(username="alice")
        task = Task.objects.create(
            project=project, version=version, title="Corriger le bug", task_type="correction"
        )

        comment = TaskComment.objects.create(task=task, author=author, content="Je regarde ça")

        self.assertEqual(task.comments.count(), 1)
        self.assertEqual(comment.author, author)


from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.services import InvalidTransitionError, TaskPermissionError, add_comment


class AddCommentServiceTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.member = User.objects.create_user(username="member")
        self.outsider = User.objects.create_user(username="outsider")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Corriger le bug", task_type="correction"
        )

    def test_member_can_comment(self):
        comment = add_comment(actor=self.member, task=self.task, content="Je regarde ça")

        self.assertEqual(comment.author, self.member)
        self.assertEqual(comment.task, self.task)
        self.assertEqual(self.task.comments.count(), 1)

    def test_outsider_cannot_comment(self):
        with self.assertRaises(TaskPermissionError):
            add_comment(actor=self.outsider, task=self.task, content="Je ne devrais pas pouvoir")

    def test_empty_comment_is_rejected(self):
        with self.assertRaises(InvalidTransitionError):
            add_comment(actor=self.member, task=self.task, content="   ")


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
class TaskCommentApiTests(APITestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.member = User.objects.create_user(username="member-comment")
        self.outsider = User.objects.create_user(username="outsider-comment")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Corriger le bug", task_type="correction"
        )

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_member_can_add_comment(self):
        response = self.client.post(
            f"/api/v1/tasks/{self.task.id}/comments/",
            {"content": "On regarde ça"},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["content"], "On regarde ça")

    def test_outsider_cannot_add_comment(self):
        # 404, pas 403 : sans ProjectMembership, l'outsider sort du queryset
        # scopé (`accessible_projects`, TaskViewSet.get_queryset) avant même
        # la vérification d'autorisation dans `add_comment` — même raison que
        # `IncidentLifecycleApiTests.test_outsider_cannot_add_comment`
        # (apps/incidents/tests/test_api.py), pattern identique.
        response = self.client.post(
            f"/api/v1/tasks/{self.task.id}/comments/",
            {"content": "Je ne devrais pas pouvoir"},
            **self.as_user(self.outsider),
        )

        self.assertEqual(response.status_code, 404)

    def test_detail_includes_comments(self):
        self.client.post(
            f"/api/v1/tasks/{self.task.id}/comments/",
            {"content": "Premier commentaire"},
            **self.as_user(self.member),
        )

        response = self.client.get(f"/api/v1/tasks/{self.task.id}/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
        comments = response.json()["comments"]
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["content"], "Premier commentaire")
