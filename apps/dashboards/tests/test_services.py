from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import Organisation, Team, TeamMembership, User
from apps.budgeting.services import add_budget_line
from apps.dashboards.services import (
    DashboardPermissionError,
    DashboardValidationError,
    compute_custom_widget,
    compute_widget_data,
    create_widget,
    get_dashboard,
    remove_widget,
)
from apps.projects.models import ProjectMembership
from apps.projects.services import create_project
from apps.tasks.services import create_task


class _BaseDashboardTestCase(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Org Dash")
        self.chef = User.objects.create_user(username="chef-dash", organisation=self.org)
        self.team = Team.objects.create(name="Équipe Dash", organisation=self.org, created_by=self.chef)
        TeamMembership.objects.create(team=self.team, user=self.chef)
        self.project = create_project(actor=self.chef, name="Projet Dash", project_type="collaboratif", team=self.team)
        self.member = User.objects.create_user(username="member-dash", organisation=self.org)
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")


class GroupWidgetPermissionTests(_BaseDashboardTestCase):
    def test_plain_member_cannot_create_group_widget_on_project(self):
        with self.assertRaises(DashboardPermissionError):
            create_widget(
                actor=self.member,
                scope="projet",
                project=self.project,
                widget_type="defaut",
                metric_key="project_user_stats",
            )

    def test_manager_can_create_group_widget_on_project(self):
        widget = create_widget(
            actor=self.chef,
            scope="projet",
            project=self.project,
            widget_type="defaut",
            metric_key="project_user_stats",
        )
        self.assertEqual(widget.visibility, "groupe")

    def test_group_widget_becomes_restricted_after_owner_demoted(self):
        widget = create_widget(
            actor=self.chef,
            scope="projet",
            project=self.project,
            widget_type="defaut",
            metric_key="project_user_stats",
        )
        # Le chef de projet est rétrogradé en simple membre après coup.
        membership = ProjectMembership.objects.get(project=self.project, user=self.chef)
        membership.role = "membre"
        membership.save(update_fields=["role"])

        data = compute_widget_data(actor=self.chef, widget=widget)
        self.assertTrue(data.get("restricted"))

    def test_custom_widget_with_assignee_group_by_is_forced_to_group_visibility(self):
        # Un membre ne peut même pas tenter de déclarer "individuel" pour
        # contourner la restriction — create_widget lève avant même d'y
        # arriver, car le group_by="assignee" force toujours "groupe".
        with self.assertRaises(DashboardPermissionError):
            create_widget(
                actor=self.member,
                scope="projet",
                project=self.project,
                widget_type="personnalise",
                config={"source": "tasks", "aggregation": "count", "field": None, "group_by": "assignee"},
                visibility="individuel",
            )


class GlobalGroupScopeTests(TestCase):
    """Un acteur chef de projet d'un seul projet ne voit ses données "groupe"
    globales que sur ce projet-là, jamais sur un projet où il n'est que
    contributeur."""

    def setUp(self):
        self.org = Organisation.objects.create(name="Org Dash Global")
        self.actor = User.objects.create_user(username="actor-dash-g", organisation=self.org)

        self.team_a = Team.objects.create(name="Équipe A", organisation=self.org, created_by=self.actor)
        TeamMembership.objects.create(team=self.team_a, user=self.actor)
        self.managed_project = create_project(
            actor=self.actor, name="Projet dirigé", project_type="collaboratif", team=self.team_a
        )

        self.other_chef = User.objects.create_user(username="other-chef-dash-g", organisation=self.org)
        self.team_b = Team.objects.create(name="Équipe B", organisation=self.org, created_by=self.other_chef)
        TeamMembership.objects.create(team=self.team_b, user=self.other_chef)
        TeamMembership.objects.create(team=self.team_b, user=self.actor)
        self.contributor_only_project = create_project(
            actor=self.other_chef, name="Projet contributeur", project_type="collaboratif", team=self.team_b
        )
        ProjectMembership.objects.create(project=self.contributor_only_project, user=self.actor, role="membre")

        create_task(actor=self.actor, project=self.managed_project, title="Tâche dirigée", task_type="ajout")
        create_task(
            actor=self.other_chef, project=self.contributor_only_project, title="Tâche autre projet", task_type="ajout"
        )

    def test_global_group_widget_scoped_to_managed_projects_only(self):
        # `visibility="groupe"` demandé explicitement : un widget personnalisé
        # "individuel" agrège légitimement sur tous les projets contributeur
        # (même principe que les métriques "individuel" par défaut, déjà
        # visibles projet par projet pour tout contributeur) — seule la
        # portée "groupe" doit se restreindre aux projets réellement dirigés.
        widget = create_widget(
            actor=self.actor,
            scope="global",
            widget_type="personnalise",
            config={"source": "tasks", "aggregation": "count", "field": None, "group_by": "status"},
            visibility="groupe",
        )
        self.assertEqual(widget.visibility, "groupe")

        data = compute_widget_data(actor=self.actor, widget=widget)
        total = sum(point["value"] for point in data["data"])
        # Une seule tâche dans le périmètre (le projet dirigé) — celle du
        # projet où `actor` n'est que contributeur ne doit jamais apparaître.
        self.assertEqual(total, 1)

    def test_contributor_without_any_managed_project_cannot_create_global_group_widget(self):
        plain = User.objects.create_user(username="plain-dash-g", organisation=self.org)
        ProjectMembership.objects.create(project=self.managed_project, user=plain, role="membre")

        with self.assertRaises(DashboardPermissionError):
            create_widget(
                actor=plain,
                scope="global",
                widget_type="defaut",
                metric_key="current_workload_by_user",
            )


class CustomWidgetConfigTests(_BaseDashboardTestCase):
    def test_rejects_field_not_in_catalog(self):
        with self.assertRaises(DashboardValidationError):
            create_widget(
                actor=self.chef,
                scope="projet",
                project=self.project,
                widget_type="personnalise",
                config={"source": "tasks", "aggregation": "avg", "field": "not_a_real_field", "group_by": "none"},
            )

    def test_rejects_field_with_count_aggregation(self):
        with self.assertRaises(DashboardValidationError):
            create_widget(
                actor=self.chef,
                scope="projet",
                project=self.project,
                widget_type="personnalise",
                config={"source": "tasks", "aggregation": "count", "field": "time_spent", "group_by": "none"},
            )

    def test_recompute_rejects_config_mutated_to_invalid_field_without_crashing_dashboard(self):
        widget = create_widget(
            actor=self.chef,
            scope="projet",
            project=self.project,
            widget_type="personnalise",
            config={"source": "tasks", "aggregation": "avg", "field": "time_spent", "group_by": "none"},
        )
        # Simule un catalogue qui aurait changé depuis la création du widget.
        widget.config = {"source": "tasks", "aggregation": "avg", "field": "plus_dans_le_catalogue", "group_by": "none"}
        widget.save(update_fields=["config"])

        data = compute_widget_data(actor=self.chef, widget=widget)
        self.assertTrue(data.get("restricted"))


class OtherUsersWidgetTests(_BaseDashboardTestCase):
    def test_removing_widget_of_another_user_is_rejected(self):
        widget = create_widget(
            actor=self.chef, scope="global", widget_type="defaut", metric_key="task_hours_total"
        )
        with self.assertRaises(DashboardPermissionError):
            remove_widget(actor=self.member, widget=widget)


class BudgetCustomAggregationTests(_BaseDashboardTestCase):
    def test_sum_amount_uses_orm_annotation_not_python_property(self):
        add_budget_line(actor=self.chef, project=self.project, category="opex", label="Licences", quantity=3, unit_price="10.00")
        add_budget_line(actor=self.chef, project=self.project, category="capex", label="Serveur", quantity=1, unit_price="500.00")

        result = compute_custom_widget(
            config={"source": "budget", "aggregation": "sum", "field": "amount", "group_by": "none"},
            project_ids=[self.project.id],
        )
        self.assertEqual(result["type"], "scalar")
        self.assertEqual(Decimal(str(result["value"])), Decimal("530.00"))

    def test_sum_amount_grouped_by_category(self):
        add_budget_line(actor=self.chef, project=self.project, category="opex", label="Licences", quantity=2, unit_price="10.00")
        add_budget_line(actor=self.chef, project=self.project, category="capex", label="Serveur", quantity=1, unit_price="500.00")

        result = compute_custom_widget(
            config={"source": "budget", "aggregation": "sum", "field": "amount", "group_by": "category"},
            project_ids=[self.project.id],
        )
        by_label = {point["label"]: point["value"] for point in result["data"]}
        self.assertEqual(Decimal(str(by_label["opex"])), Decimal("20.00"))
        self.assertEqual(Decimal(str(by_label["capex"])), Decimal("500.00"))


class DashboardScopingLeakTests(TestCase):
    """Un lecteur/contributeur sans droit "groupe" sur un projet A ne doit
    jamais voir, via le dashboard global, les données d'un projet B où il
    n'est pas non plus habilité."""

    def setUp(self):
        self.org = Organisation.objects.create(name="Org Dash Leak")
        self.actor = User.objects.create_user(username="actor-dash-leak", organisation=self.org)
        self.team = Team.objects.create(name="Équipe Leak", organisation=self.org, created_by=self.actor)
        TeamMembership.objects.create(team=self.team, user=self.actor)
        self.project = create_project(actor=self.actor, name="Projet Leak", project_type="collaboratif", team=self.team)
        create_task(actor=self.actor, project=self.project, title="T", task_type="ajout")

    def test_individual_global_widget_only_covers_contributor_projects(self):
        widget = create_widget(
            actor=self.actor,
            scope="global",
            widget_type="defaut",
            metric_key="task_hours_total",
        )
        entries = get_dashboard(actor=self.actor, scope="global")
        self.assertEqual(len(entries), 1)
        self.assertFalse(entries[0]["data"].get("restricted"))
        self.assertEqual(entries[0]["widget"].id, widget.id)
