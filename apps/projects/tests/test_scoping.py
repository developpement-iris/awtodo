from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.incidents.models import Incident
from apps.tasks.models import Task

from .. import services
from ..models import Project, ProjectMembership, ProjectVersion


def _version(project):
    return ProjectVersion.objects.create(project=project, label="v1", is_current=True)


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
class ProjectListScopingApiTests(APITestCase):
    """Voir CLAUDE.md > "Scoping des listes par appartenance"."""

    def setUp(self):
        self.member = User.objects.create_user(username="member-scope")
        self.outsider = User.objects.create_user(username="outsider-scope")
        self.platform_admin = User.objects.create_user(username="platform-admin-scope", is_platform_admin=True)
        self.project = Project.objects.create(name="Projet privé")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_member_sees_project_in_list(self):
        response = self.client.get("/api/v1/projects/", **self.as_user(self.member))

        ids = [item["id"] for item in response.json()]
        self.assertIn(str(self.project.id), ids)

    def test_outsider_does_not_see_project_in_list(self):
        response = self.client.get("/api/v1/projects/", **self.as_user(self.outsider))

        ids = [item["id"] for item in response.json()]
        self.assertNotIn(str(self.project.id), ids)

    def test_outsider_gets_404_on_detail(self):
        response = self.client.get(f"/api/v1/projects/{self.project.id}/", **self.as_user(self.outsider))

        self.assertEqual(response.status_code, 404)

    def test_member_gets_200_on_detail(self):
        response = self.client.get(f"/api/v1/projects/{self.project.id}/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)

    def test_anonymous_sees_no_projects(self):
        response = self.client.get("/api/v1/projects/")

        self.assertEqual(response.json(), [])

    def test_platform_admin_sees_every_project(self):
        response = self.client.get("/api/v1/projects/", **self.as_user(self.platform_admin))

        ids = [item["id"] for item in response.json()]
        self.assertIn(str(self.project.id), ids)

    def test_organisation_admin_gets_no_special_exception(self):
        # Voir CLAUDE.md : `organisation_role=admin` ne voit que ses propres
        # projets, comme n'importe qui — pas d'exception de rang ici.
        org_admin = User.objects.create_user(username="org-admin-scope", organisation_role="admin")

        response = self.client.get("/api/v1/projects/", **self.as_user(org_admin))

        ids = [item["id"] for item in response.json()]
        self.assertNotIn(str(self.project.id), ids)

    def test_task_list_scoped_to_accessible_projects(self):
        task = Task.objects.create(project=self.project, version=_version(self.project), title="Tâche privée", task_type="correction")

        member_response = self.client.get("/api/v1/tasks/", **self.as_user(self.member))
        outsider_response = self.client.get("/api/v1/tasks/", **self.as_user(self.outsider))

        self.assertIn(str(task.id), [item["id"] for item in member_response.json()])
        self.assertNotIn(str(task.id), [item["id"] for item in outsider_response.json()])

    def test_task_detail_404_for_outsider(self):
        task = Task.objects.create(project=self.project, version=_version(self.project), title="Tâche privée", task_type="correction")

        response = self.client.get(f"/api/v1/tasks/{task.id}/", **self.as_user(self.outsider))

        self.assertEqual(response.status_code, 404)

    def test_incident_list_scoped_to_accessible_projects(self):
        incident = Incident.objects.create(project=self.project, title="Incident privé")

        member_response = self.client.get("/api/v1/incidents/", **self.as_user(self.member))
        outsider_response = self.client.get("/api/v1/incidents/", **self.as_user(self.outsider))

        self.assertIn(str(incident.id), [item["id"] for item in member_response.json()])
        self.assertNotIn(str(incident.id), [item["id"] for item in outsider_response.json()])

    def test_incident_detail_404_for_outsider(self):
        incident = Incident.objects.create(project=self.project, title="Incident privé")

        response = self.client.get(f"/api/v1/incidents/{incident.id}/", **self.as_user(self.outsider))

        self.assertEqual(response.status_code, 404)

    def test_externe_account_sees_only_its_invited_project(self):
        # Reproduit l'état obtenu après acceptation d'une invitation externe
        # (voir CLAUDE.md > "Comptes et invitations") : une ProjectMembership
        # sur un seul projet, aucune autre appartenance.
        other_project = Project.objects.create(name="Autre projet")
        ProjectMembership.objects.create(project=other_project, user=self.member, role="membre")
        externe = User.objects.create_user(username="externe-scope", account_type="externe")
        ProjectMembership.objects.create(project=self.project, user=externe, role="membre")

        response = self.client.get("/api/v1/projects/", **self.as_user(externe))

        ids = [item["id"] for item in response.json()]
        self.assertEqual(ids, [str(self.project.id)])


class AccessibleProjectsServiceTests(APITestCase):
    """Teste directement `services.accessible_projects` (pas seulement via l'API)."""

    def test_anonymous_user_sees_nothing(self):
        self.assertEqual(list(services.accessible_projects(None)), [])

    def test_platform_admin_sees_active_and_closed_projects(self):
        # `accessible_projects` est statut-agnostique depuis le "Filtre d'état
        # généralisé" (voir docs/modeles-et-api.md) : un projet clôturé reste
        # accessible par appartenance, seul `ProjectFilterSet` décide de ce
        # qui apparaît par défaut dans la liste (voir tests API ci-dessous).
        member = User.objects.create_user(username="pa-member")
        admin = User.objects.create_user(username="pa-admin", is_platform_admin=True)
        active_project = Project.objects.create(name="Actif")
        closed_project = Project.objects.create(name="Clôturé", status="cloture")
        ProjectMembership.objects.create(project=active_project, user=member, role="membre")

        visible = set(services.accessible_projects(admin).values_list("id", flat=True))

        self.assertIn(active_project.id, visible)
        self.assertIn(closed_project.id, visible)


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
class ProjectStatusFilterApiTests(APITestCase):
    """Voir docs/modeles-et-api.md > "Filtre d'état généralisé"."""

    def setUp(self):
        self.member = User.objects.create_user(username="status-filter-member")
        self.active_project = Project.objects.create(name="Actif", status="actif")
        self.closed_project = Project.objects.create(name="Clôturé", status="cloture")
        ProjectMembership.objects.create(project=self.active_project, user=self.member, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.closed_project, user=self.member, role="chef_de_projet")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_closed_project_hidden_by_default(self):
        response = self.client.get("/api/v1/projects/", **self.as_user(self.member))

        ids = [item["id"] for item in response.json()]
        self.assertIn(str(self.active_project.id), ids)
        self.assertNotIn(str(self.closed_project.id), ids)

    def test_closed_project_visible_when_explicitly_requested(self):
        response = self.client.get("/api/v1/projects/", {"status": "cloture"}, **self.as_user(self.member))

        ids = [item["id"] for item in response.json()]
        self.assertNotIn(str(self.active_project.id), ids)
        self.assertIn(str(self.closed_project.id), ids)

    def test_detail_of_closed_project_still_reachable(self):
        # Le filtre par défaut ne doit s'appliquer qu'aux listes, jamais à la
        # résolution d'un objet précis (voir `ListOnlyFilterMixin`) — sinon
        # `reopen` serait impossible à atteindre sur un projet clôturé.
        response = self.client.get(f"/api/v1/projects/{self.closed_project.id}/", **self.as_user(self.member))

        self.assertEqual(response.status_code, 200)
