from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership

from .. import services
from ..models import BudgetLine


class BudgetLineServiceTests(APITestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.manager = User.objects.create_user(username="budget-manager")
        self.member = User.objects.create_user(username="budget-member")
        self.outsider = User.objects.create_user(username="budget-outsider")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def test_manager_adds_opex_line(self):
        line = services.add_budget_line(
            actor=self.manager, project=self.project, category="opex", label="Licences SaaS", quantity="5", unit_price="20.00",
        )

        self.assertEqual(line.amount, 100)
        self.assertEqual(BudgetLine.objects.filter(project=self.project).count(), 1)

    def test_member_cannot_add_line(self):
        with self.assertRaises(services.BudgetPermissionError):
            services.add_budget_line(
                actor=self.member, project=self.project, category="capex", label="Serveur", quantity="1", unit_price="2000",
            )

    def test_member_can_view_lines(self):
        services.add_budget_line(
            actor=self.manager, project=self.project, category="opex", label="Licences", quantity="1", unit_price="10",
        )

        lines = services.get_budget_lines(actor=self.member, project=self.project)

        self.assertEqual(len(lines), 1)

    def test_outsider_cannot_view_lines(self):
        with self.assertRaises(services.BudgetPermissionError):
            services.get_budget_lines(actor=self.outsider, project=self.project)

    def test_remove_line_is_soft_delete(self):
        line = services.add_budget_line(
            actor=self.manager, project=self.project, category="capex", label="Matériel", quantity="1", unit_price="500",
        )

        services.remove_budget_line(actor=self.manager, line=line)

        self.assertEqual(BudgetLine.objects.filter(project=self.project).count(), 0)
        self.assertEqual(BudgetLine.all_objects.filter(project=self.project).count(), 1)
        line.refresh_from_db()
        self.assertEqual(line.status, "removed")

    def test_invalid_category_rejected(self):
        with self.assertRaises(services.BudgetValidationError):
            services.add_budget_line(
                actor=self.manager, project=self.project, category="wrong", label="X", quantity="1", unit_price="1",
            )

    def test_fractional_quantity_rejected(self):
        with self.assertRaises(services.BudgetValidationError):
            services.add_budget_line(
                actor=self.manager, project=self.project, category="opex", label="X", quantity="2.5", unit_price="10",
            )

    def test_integer_quantity_accepted(self):
        line = services.add_budget_line(
            actor=self.manager, project=self.project, category="opex", label="X", quantity="4", unit_price="10",
        )

        self.assertEqual(line.quantity, 4)
        self.assertIsInstance(line.quantity, int)

    def test_summary_only_includes_managed_projects(self):
        other_project = Project.objects.create(name="Autre projet")
        ProjectMembership.objects.create(project=other_project, user=self.manager, role="membre")
        services.add_budget_line(
            actor=self.manager, project=self.project, category="opex", label="A", quantity="2", unit_price="50",
        )
        services.add_budget_line(
            actor=self.manager, project=self.project, category="capex", label="B", quantity="1", unit_price="300",
        )

        summary = services.get_budget_summary_for_manager(actor=self.manager)

        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["project"], self.project)
        self.assertEqual(summary[0]["opex_total"], 100)
        self.assertEqual(summary[0]["capex_total"], 300)


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
class BudgetLineApiTests(APITestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Projet Test")
        self.manager = User.objects.create_user(username="budget-manager-api")
        self.member = User.objects.create_user(username="budget-member-api")
        self.outsider = User.objects.create_user(username="budget-outsider-api")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_manager_creates_line_via_api(self):
        response = self.client.post(
            f"/api/v1/budgeting/projects/{self.project.id}/lines/",
            {"category": "opex", "label": "Abonnement", "quantity": "3", "unit_price": "15"},
            content_type="application/json",
            **self.as_user(self.manager),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["amount"], "45.00")

    def test_fractional_quantity_rejected_via_api(self):
        response = self.client.post(
            f"/api/v1/budgeting/projects/{self.project.id}/lines/",
            {"category": "opex", "label": "Abonnement", "quantity": "2.5", "unit_price": "15"},
            content_type="application/json",
            **self.as_user(self.manager),
        )

        self.assertEqual(response.status_code, 400)

    def test_member_cannot_create_line_via_api(self):
        response = self.client.post(
            f"/api/v1/budgeting/projects/{self.project.id}/lines/",
            {"category": "opex", "label": "Abonnement", "quantity": "3", "unit_price": "15"},
            content_type="application/json",
            **self.as_user(self.member),
        )

        self.assertEqual(response.status_code, 403)

    def test_outsider_gets_404_on_lines(self):
        response = self.client.get(
            f"/api/v1/budgeting/projects/{self.project.id}/lines/", **self.as_user(self.outsider)
        )

        self.assertEqual(response.status_code, 404)

    def test_manager_removes_line_via_api(self):
        create = self.client.post(
            f"/api/v1/budgeting/projects/{self.project.id}/lines/",
            {"category": "capex", "label": "Matériel", "quantity": "1", "unit_price": "999"},
            content_type="application/json",
            **self.as_user(self.manager),
        )
        line_id = create.json()["id"]

        response = self.client.post(f"/api/v1/budgeting/{line_id}/remove/", **self.as_user(self.manager))

        self.assertEqual(response.status_code, 200)

        list_response = self.client.get(
            f"/api/v1/budgeting/projects/{self.project.id}/lines/", **self.as_user(self.manager)
        )
        self.assertEqual(list_response.json(), [])

    def test_summary_endpoint(self):
        self.client.post(
            f"/api/v1/budgeting/projects/{self.project.id}/lines/",
            {"category": "opex", "label": "A", "quantity": "1", "unit_price": "100"},
            content_type="application/json",
            **self.as_user(self.manager),
        )

        response = self.client.get("/api/v1/budgeting/summary/", **self.as_user(self.manager))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["project_id"], str(self.project.id))
        self.assertEqual(payload[0]["opex_total"], "100.00")
