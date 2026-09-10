from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from apps.accounts.models import Team, TeamMembership, User
from apps.incidents.models import Incident
from apps.tasks.models import Task

from ..models import Project, ProjectMembership, ProjectVersion


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
class ListEndpointQueryBudgetTests(APITestCase):
    """Garde-fou anti-régression N+1 sur les endpoints de liste (voir CLAUDE.md
    > "Scoping des listes par appartenance" et le cache d'appartenances
    `prefetched_project_roles` / `prefetched_team_memberships`).

    Le nombre de requêtes doit rester ~constant quel que soit le nombre de
    lignes — on charge volontairement beaucoup de données puis on plafonne.
    Les bornes ont du mou (le coût réel est bien plus bas) pour ne pas casser
    au moindre `select_related` ajouté ailleurs ; ce qui compte est qu'elles
    ne dépendent pas du volume.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="perf-budget")
        others = [User.objects.create_user(username=f"perf-co-{i}") for i in range(4)]
        team = Team.objects.create(name="Groupe perf", created_by=cls.user)
        for member in [cls.user, *others]:
            TeamMembership.objects.create(team=team, user=member)

        for i in range(12):
            collaboratif = i % 2 == 0
            project = Project.objects.create(
                name=f"Projet {i}",
                project_type="collaboratif" if collaboratif else "individuel",
                team=team if collaboratif else None,
            )
            version = ProjectVersion.objects.create(project=project, label="v1", is_current=True)
            ProjectMembership.objects.create(project=project, user=cls.user, role="chef_de_projet")
            if collaboratif:
                for member in others:
                    ProjectMembership.objects.create(project=project, user=member, role="membre")
            for j in range(8):
                Task.objects.create(
                    project=project,
                    version=version,
                    title=f"Tâche {i}-{j}",
                    task_type="correction",
                    assignee=others[j % 4] if collaboratif else cls.user,
                    status="assignee",
                )
            for j in range(3):
                Incident.objects.create(
                    project=project,
                    team=team if collaboratif else None,
                    title=f"Incident {i}-{j}",
                )

    def _auth(self):
        return {"HTTP_X_DEBUG_USER_ID": str(self.user.id)}

    def _assert_budget(self, url, max_queries, expected_rows):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url, **self._auth())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), expected_rows)
        self.assertLessEqual(
            len(ctx.captured_queries),
            max_queries,
            f"{url} a émis {len(ctx.captured_queries)} requêtes (budget {max_queries}) — "
            f"probable régression N+1.\n"
            + "\n".join(q["sql"][:200] for q in ctx.captured_queries),
        )

    def test_projects_list_query_budget(self):
        self._assert_budget("/api/v1/projects/", max_queries=15, expected_rows=12)

    def test_tasks_list_query_budget(self):
        self._assert_budget("/api/v1/tasks/", max_queries=15, expected_rows=96)

    def test_incidents_list_query_budget(self):
        self._assert_budget("/api/v1/incidents/", max_queries=15, expected_rows=36)
