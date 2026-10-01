from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from apps.accounts.models import Organisation, Team, TeamMembership, User
from apps.dashboards.services import create_widget
from apps.projects.models import ProjectMembership
from apps.projects.services import create_project


@override_settings(
    DEBUG=True,
    REST_FRAMEWORK={
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
        "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.DebugUserIdAuthentication"],
    },
)
class DashboardApiTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org Dash API")
        self.chef = User.objects.create_user(username="chef-dash-api", organisation=self.org)
        self.team = Team.objects.create(name="Équipe Dash API", organisation=self.org, created_by=self.chef)
        TeamMembership.objects.create(team=self.team, user=self.chef)
        self.project = create_project(actor=self.chef, name="Projet Dash API", project_type="collaboratif", team=self.team)
        self.other_user = User.objects.create_user(username="other-dash-api", organisation=self.org)

    def _as(self, user):
        self.client.credentials(HTTP_X_DEBUG_USER_ID=str(user.id))

    def test_create_and_list_project_dashboard_widget(self):
        self._as(self.chef)
        r = self.client.post(
            f"/api/v1/dashboards/projects/{self.project.id}/",
            {"widget_type": "defaut", "metric_key": "task_hours_total"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)

        r = self.client.get(f"/api/v1/dashboards/projects/{self.project.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["widgets"]), 1)
        self.assertEqual(r.json()["widgets"][0]["metric_key"], "task_hours_total")

    def test_second_group_widget_does_not_repeat_the_permission_check(self):
        """Garde-fou N+1 : `is_project_manager` est vérifié par widget
        "groupe", mais ne doit coûter qu'UNE requête pour tout le dashboard
        (cache `prefetched_project_roles`), pas une par widget. Deux widgets
        de la **même** métrique ont un coût de données identique — toute
        requête supplémentaire au-delà de ce doublement vient forcément de la
        vérification de permission qui se répéterait sans le cache."""
        self._as(self.chef)
        create_widget(
            actor=self.chef,
            scope="projet",
            project=self.project,
            widget_type="defaut",
            metric_key="current_workload_by_user",
        )
        with CaptureQueriesContext(connection) as ctx_one:
            r = self.client.get(f"/api/v1/dashboards/projects/{self.project.id}/")
        self.assertEqual(r.status_code, 200)
        one_widget_queries = len(ctx_one.captured_queries)

        create_widget(
            actor=self.chef,
            scope="projet",
            project=self.project,
            widget_type="defaut",
            metric_key="current_workload_by_user",
        )
        with CaptureQueriesContext(connection) as ctx_two:
            r = self.client.get(f"/api/v1/dashboards/projects/{self.project.id}/")
        self.assertEqual(r.status_code, 200)
        two_widget_queries = len(ctx_two.captured_queries)

        # Le doublement du coût de données (même métrique x2) plus une petite
        # marge — pas une 3e vérification de permission en plus.
        self.assertLessEqual(two_widget_queries, 2 * one_widget_queries + 3)

    def test_patch_position_of_another_users_widget_returns_404(self):
        widget = create_widget(
            actor=self.chef, scope="global", widget_type="defaut", metric_key="task_hours_total"
        )
        self._as(self.other_user)
        r = self.client.patch(
            f"/api/v1/dashboards/widgets/{widget.id}/", {"x": 1, "y": 1, "w": 2, "h": 2}, format="json"
        )
        self.assertEqual(r.status_code, 404)

    def test_delete_another_users_widget_returns_404(self):
        widget = create_widget(
            actor=self.chef, scope="global", widget_type="defaut", metric_key="task_hours_total"
        )
        self._as(self.other_user)
        r = self.client.delete(f"/api/v1/dashboards/widgets/{widget.id}/")
        self.assertEqual(r.status_code, 404)

    def test_catalog_hides_group_metrics_from_plain_member(self):
        member = User.objects.create_user(username="plain-dash-api", organisation=self.org)
        ProjectMembership.objects.create(project=self.project, user=member, role="membre")
        self._as(member)
        r = self.client.get(f"/api/v1/dashboards/catalog/?scope=projet&project_id={self.project.id}")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("project_user_stats", r.json()["default_metrics"])

    def test_reader_cannot_access_project_dashboard(self):
        reader = User.objects.create_user(username="reader-dash-api", organisation=self.org)
        ProjectMembership.objects.create(project=self.project, user=reader, role="lecteur")
        self._as(reader)
        r = self.client.get(f"/api/v1/dashboards/projects/{self.project.id}/")
        self.assertEqual(r.status_code, 404)
