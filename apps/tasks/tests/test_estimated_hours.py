from django.test import TestCase

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task
from apps.tasks.services import create_task


class EstimatedHoursFieldTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test Estim")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.member = User.objects.create_user(username="member-estim")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def test_task_can_be_created_with_an_estimate(self):
        task = create_task(
            actor=self.member,
            project=self.project,
            title="Corriger le bug",
            task_type="correction",
            estimated_hours="4.5",
        )

        self.assertEqual(task.estimated_hours, 4.5)

    def test_task_estimate_defaults_to_none(self):
        task = create_task(actor=self.member, project=self.project, title="Sans estimation", task_type="correction")

        self.assertIsNone(task.estimated_hours)


from django.test import override_settings
from rest_framework.test import APITestCase

from apps.tasks.services import TaskPermissionError, update_task_estimated_hours


class UpdateEstimatedHoursServiceTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test Estim 2")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.member = User.objects.create_user(username="member-estim-2")
        self.outsider = User.objects.create_user(username="outsider-estim")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Corriger le bug", task_type="correction"
        )

    def test_member_can_set_estimate(self):
        update_task_estimated_hours(actor=self.member, task=self.task, estimated_hours="6")

        self.assertEqual(self.task.estimated_hours, 6)

    def test_member_can_clear_estimate(self):
        update_task_estimated_hours(actor=self.member, task=self.task, estimated_hours="6")

        update_task_estimated_hours(actor=self.member, task=self.task, estimated_hours=None)

        self.assertIsNone(self.task.estimated_hours)

    def test_outsider_cannot_set_estimate(self):
        with self.assertRaises(TaskPermissionError):
            update_task_estimated_hours(actor=self.outsider, task=self.task, estimated_hours="6")


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
class UpdateEstimatedHoursApiTests(APITestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test Estim API")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.member = User.objects.create_user(username="member-estim-api")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.task = Task.objects.create(
            project=self.project, version=self.version, title="Corriger le bug", task_type="correction"
        )

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_update_estimated_hours(self):
        response = self.client.post(
            f"/api/v1/tasks/{self.task.id}/update-estimated-hours/",
            {"estimated_hours": "3.5"},
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["estimated_hours"], "3.50")


from apps.tasks.services import get_project_task_insights


class TaskInsightsEstimateTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test Estim Insights")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.member = User.objects.create_user(username="member-estim-insights")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def make_archived_task(self, *, estimated_hours, time_spent):
        return Task.objects.create(
            project=self.project,
            version=self.version,
            title="Tâche terminée",
            task_type="correction",
            status="archivee",
            estimated_hours=estimated_hours,
            time_spent=time_spent,
        )

    def test_estimated_hours_total_sums_all_tasks_in_scope(self):
        self.make_archived_task(estimated_hours="4", time_spent="5")
        Task.objects.create(
            project=self.project, version=self.version, title="Pas terminée", task_type="correction",
            estimated_hours="2",
        )

        insights = get_project_task_insights(actor=self.member, project=self.project)

        self.assertEqual(insights["estimated_hours_total"], 6)

    def test_task_over_estimate_is_counted(self):
        self.make_archived_task(estimated_hours="4", time_spent="5")

        insights = get_project_task_insights(actor=self.member, project=self.project)

        self.assertEqual(insights["tasks_over_estimate"], 1)
        self.assertEqual(insights["tasks_under_estimate"], 0)

    def test_task_under_estimate_is_counted(self):
        self.make_archived_task(estimated_hours="4", time_spent="3")

        insights = get_project_task_insights(actor=self.member, project=self.project)

        self.assertEqual(insights["tasks_over_estimate"], 0)
        self.assertEqual(insights["tasks_under_estimate"], 1)

    def test_task_without_estimate_excluded_from_over_under_counts(self):
        self.make_archived_task(estimated_hours=None, time_spent="3")

        insights = get_project_task_insights(actor=self.member, project=self.project)

        self.assertEqual(insights["tasks_over_estimate"], 0)
        self.assertEqual(insights["tasks_under_estimate"], 0)
