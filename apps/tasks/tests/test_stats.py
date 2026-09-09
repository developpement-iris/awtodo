from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership, ProjectVersion

from .. import services
from ..models import Task


class ProjectUserStatsServiceTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.manager = User.objects.create_user(username="stats-manager")
        self.member = User.objects.create_user(username="stats-member")
        self.other_member = User.objects.create_user(username="stats-other")
        self.outsider = User.objects.create_user(username="stats-outsider")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        ProjectMembership.objects.create(project=self.project, user=self.other_member, role="membre")

        Task.objects.create(
            project=self.project, version=self.version, title="Terminée", task_type="correction",
            status="archivee", assignee=self.member, time_spent="4.5",
        )
        Task.objects.create(
            project=self.project, version=self.version, title="Terminée 2", task_type="correction",
            status="archivee", assignee=self.member, time_spent="2.0",
        )
        Task.objects.create(
            project=self.project, version=self.version, title="En cours", task_type="correction",
            status="en_cours", assignee=self.member,
        )
        Task.objects.create(
            project=self.project, version=self.version, title="Terminée autre", task_type="correction",
            status="archivee", assignee=self.other_member, time_spent="1.0",
        )

    def test_manager_sees_all_members(self):
        stats = services.get_project_user_stats(actor=self.manager, project=self.project)

        users = {row["user"].id for row in stats}
        self.assertEqual(users, {self.manager.id, self.member.id, self.other_member.id})

    def test_member_row_values_correct(self):
        stats = services.get_project_user_stats(actor=self.manager, project=self.project)
        member_row = next(row for row in stats if row["user"].id == self.member.id)

        self.assertEqual(member_row["tasks_done"], 2)
        self.assertEqual(member_row["tasks_in_progress"], 1)
        self.assertEqual(member_row["hours_spent"], 6.5)

    def test_plain_member_sees_only_self(self):
        stats = services.get_project_user_stats(actor=self.member, project=self.project)

        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["user"].id, self.member.id)
        self.assertEqual(stats[0]["tasks_done"], 2)

    def test_outsider_cannot_view_stats(self):
        with self.assertRaises(services.TaskPermissionError):
            services.get_project_user_stats(actor=self.outsider, project=self.project)


class ProjectTaskInsightsServiceTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Insights")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)
        self.manager = User.objects.create_user(username="insights-manager")
        self.member = User.objects.create_user(username="insights-member")
        self.other_member = User.objects.create_user(username="insights-other")
        self.outsider = User.objects.create_user(username="insights-outsider")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        ProjectMembership.objects.create(project=self.project, user=self.other_member, role="membre")

        today = timezone.now().date()

        on_time = Task.objects.create(
            project=self.project, version=self.version, title="À temps", task_type="correction",
            status="archivee", assignee=self.member, time_spent="3.0", priority="haute",
            deadline=today + timedelta(days=2),
        )
        Task.all_objects.filter(pk=on_time.pk).update(
            created_at=timezone.now() - timedelta(days=5), updated_at=timezone.now(),
        )

        late = Task.objects.create(
            project=self.project, version=self.version, title="En retard", task_type="correction",
            status="archivee", assignee=self.other_member, time_spent="1.0", priority="critique",
            deadline=today - timedelta(days=3),
        )
        Task.all_objects.filter(pk=late.pk).update(
            created_at=timezone.now() - timedelta(days=10), updated_at=timezone.now(),
        )

        Task.objects.create(
            project=self.project, version=self.version, title="Sans deadline", task_type="correction",
            status="archivee", assignee=self.member, time_spent="2.0", priority="basse",
        )
        Task.objects.create(
            project=self.project, version=self.version, title="En cours", task_type="correction",
            status="en_cours", assignee=self.manager, priority="moyenne",
        )

    def test_hours_total_sums_completed_tasks_only(self):
        insights = services.get_project_task_insights(actor=self.manager, project=self.project)
        self.assertEqual(insights["hours_total"], 6)

    def test_deadline_compliance_counts(self):
        insights = services.get_project_task_insights(actor=self.manager, project=self.project)
        self.assertEqual(insights["tasks_on_time"], 1)
        self.assertEqual(insights["tasks_late"], 1)

    def test_contributors_count_distinct_assignees(self):
        insights = services.get_project_task_insights(actor=self.manager, project=self.project)
        self.assertEqual(insights["contributors_count"], 3)

    def test_priority_breakdown(self):
        insights = services.get_project_task_insights(actor=self.manager, project=self.project)
        self.assertEqual(
            insights["priority_breakdown"],
            {"basse": 1, "moyenne": 1, "haute": 1, "critique": 1},
        )

    def test_avg_lead_time_is_none_without_completed_tasks(self):
        empty_project = Project.objects.create(name="Vide")
        ProjectMembership.objects.create(project=empty_project, user=self.manager, role="chef_de_projet")

        insights = services.get_project_task_insights(actor=self.manager, project=empty_project)

        self.assertIsNone(insights["avg_lead_time_days"])

    def test_member_can_view_insights(self):
        insights = services.get_project_task_insights(actor=self.member, project=self.project)
        self.assertIn("hours_total", insights)

    def test_outsider_cannot_view_insights(self):
        with self.assertRaises(services.TaskPermissionError):
            services.get_project_task_insights(actor=self.outsider, project=self.project)


class LeadTimeInsightsServiceTests(TestCase):
    def test_avg_lead_time_averages_days_to_completion(self):
        project = Project.objects.create(name="Lead Time")
        version = ProjectVersion.objects.create(project=project, label="v1", is_current=True)
        manager = User.objects.create_user(username="lead-time-manager")
        ProjectMembership.objects.create(project=project, user=manager, role="chef_de_projet")

        fast = Task.objects.create(
            project=project, version=version, title="Rapide", task_type="correction",
            status="archivee", assignee=manager, time_spent="1.0",
        )
        Task.all_objects.filter(pk=fast.pk).update(
            created_at=timezone.now() - timedelta(days=4), updated_at=timezone.now(),
        )
        slow = Task.objects.create(
            project=project, version=version, title="Lente", task_type="correction",
            status="archivee", assignee=manager, time_spent="1.0",
        )
        Task.all_objects.filter(pk=slow.pk).update(
            created_at=timezone.now() - timedelta(days=6), updated_at=timezone.now(),
        )

        insights = services.get_project_task_insights(actor=manager, project=project)

        self.assertEqual(insights["avg_lead_time_days"], 5.0)


class CompletionTrendServiceTests(TestCase):
    def test_trend_has_fixed_length_and_excludes_tasks_outside_window(self):
        project = Project.objects.create(name="Trend")
        version = ProjectVersion.objects.create(project=project, label="v1", is_current=True)
        manager = User.objects.create_user(username="trend-manager")
        ProjectMembership.objects.create(project=project, user=manager, role="chef_de_projet")

        Task.objects.create(
            project=project, version=version, title="Récente", task_type="correction",
            status="archivee", assignee=manager, time_spent="1.0",
        )
        old = Task.objects.create(
            project=project, version=version, title="Ancienne", task_type="correction",
            status="archivee", assignee=manager, time_spent="1.0",
        )
        Task.all_objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(weeks=20), updated_at=timezone.now() - timedelta(weeks=20),
        )

        insights = services.get_project_task_insights(actor=manager, project=project)
        trend = insights["completion_trend"]

        self.assertEqual(len(trend), services.COMPLETION_TREND_WEEKS)
        self.assertEqual(trend[-1]["count"], 1)
        self.assertEqual(sum(point["count"] for point in trend), 1)


class GlobalTaskStatsServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="global-stats-user")
        self.active_project = Project.objects.create(name="Actif", status="actif")
        self.closed_project = Project.objects.create(name="Clôturé", status="cloture")
        ProjectMembership.objects.create(project=self.active_project, user=self.user, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.closed_project, user=self.user, role="chef_de_projet")
        version = ProjectVersion.objects.create(project=self.active_project, label="v1", is_current=True)
        Task.objects.create(project=self.active_project, version=version, title="Faite", task_type="correction", status="archivee")
        Task.objects.create(project=self.active_project, version=version, title="En cours", task_type="correction", status="en_cours")

    def test_counts_accessible_projects_and_tasks(self):
        stats = services.get_global_task_stats(actor=self.user)

        self.assertEqual(stats["projects_total"], 2)
        self.assertEqual(stats["projects_active"], 1)
        self.assertEqual(stats["projects_closed"], 1)
        self.assertEqual(stats["tasks_done"], 1)
        self.assertEqual(stats["tasks_in_progress"], 1)

    def test_anonymous_raises(self):
        with self.assertRaises(services.TaskPermissionError):
            services.get_global_task_stats(actor=None)

    def test_includes_insight_fields(self):
        stats = services.get_global_task_stats(actor=self.user)

        self.assertIn("hours_total", stats)
        self.assertIn("avg_lead_time_days", stats)
        self.assertIn("tasks_on_time", stats)
        self.assertIn("tasks_late", stats)
        self.assertIn("contributors_count", stats)
        self.assertIn("priority_breakdown", stats)
        self.assertIn("completion_trend", stats)


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
class StatsApiTests(APITestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.manager = User.objects.create_user(username="stats-api-manager")
        self.member = User.objects.create_user(username="stats-api-member")
        self.outsider = User.objects.create_user(username="stats-api-outsider")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_manager_gets_project_stats(self):
        response = self.client.get(f"/api/v1/tasks/project-stats/{self.project.id}/", **self.as_user(self.manager))

        self.assertEqual(response.status_code, 200)
        users = {row["user"]["id"] for row in response.json()}
        self.assertEqual(users, {str(self.manager.id), str(self.member.id)})

    def test_outsider_gets_404_on_project_stats(self):
        response = self.client.get(f"/api/v1/tasks/project-stats/{self.project.id}/", **self.as_user(self.outsider))

        self.assertEqual(response.status_code, 404)

    def test_global_stats_returns_counts(self):
        response = self.client.get("/api/v1/tasks/global-stats/", **self.as_user(self.manager))

        self.assertEqual(response.status_code, 200)
        self.assertIn("projects_total", response.json())
        self.assertIn("priority_breakdown", response.json())

    def test_manager_gets_project_insights(self):
        response = self.client.get(f"/api/v1/tasks/project-insights/{self.project.id}/", **self.as_user(self.manager))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("hours_total", payload)
        self.assertIn("priority_breakdown", payload)

    def test_outsider_gets_404_on_project_insights(self):
        response = self.client.get(
            f"/api/v1/tasks/project-insights/{self.project.id}/", **self.as_user(self.outsider)
        )

        self.assertEqual(response.status_code, 404)
