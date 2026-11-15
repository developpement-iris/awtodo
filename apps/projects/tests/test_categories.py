"""Domaine et services d'un projet (session du 2026-11-14) : saisie assistée
par le chef de projet, quasi-doublons ramenés à l'orthographe existante."""

from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Organisation, User
from apps.common.models import AuditLogEntry

from .. import services
from ..models import Project, ProjectMembership


class ProjectCategoryServiceTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="cat-manager")
        self.member = User.objects.create_user(username="cat-member")
        self.project = Project.objects.create(name="Projet A", organisation=self.manager.organisation)
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.other = Project.objects.create(
            name="Projet B",
            organisation=self.manager.organisation,
            domain="Logistique",
            services=["Pôle Planning", "SAV"],
        )

    def test_defaults_are_empty(self):
        self.assertEqual(self.project.domain, "")
        self.assertEqual(self.project.services, [])

    def test_manager_sets_domain_and_services(self):
        services.update_project_details(
            actor=self.manager, project=self.project, domain="  Finance   et conformité ", services=["Réseau"]
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.domain, "Finance et conformité")
        self.assertEqual(self.project.services, ["Réseau"])

    def test_near_duplicates_take_existing_spelling(self):
        services.update_project_details(
            actor=self.manager, project=self.project, domain="logistique", services=["pole planning", "sav"]
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.domain, "Logistique")
        self.assertEqual(self.project.services, ["Pôle Planning", "SAV"])

    def test_duplicate_services_in_one_project_are_merged(self):
        services.update_project_details(
            actor=self.manager, project=self.project, services=["Réseau", "reseau", " ", "RÉSEAU"]
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.services, ["Réseau"])

    def test_domain_can_be_cleared(self):
        self.project.domain = "Logistique"
        self.project.save()
        services.update_project_details(actor=self.manager, project=self.project, domain="")
        self.project.refresh_from_db()
        self.assertEqual(self.project.domain, "")

    def test_too_many_services_rejected(self):
        with self.assertRaises(services.ProjectValidationError):
            services.update_project_details(
                actor=self.manager, project=self.project, services=[f"Service {i}" for i in range(11)]
            )

    def test_member_cannot_set_categories(self):
        with self.assertRaises(services.ProjectPermissionError):
            services.update_project_details(actor=self.member, project=self.project, domain="Logistique")

    def test_services_change_is_audited_readably(self):
        services.update_project_details(actor=self.manager, project=self.project, services=["Réseau", "SAV"])
        entry = AuditLogEntry.objects.get(project=self.project, field_name="services")
        self.assertEqual(entry.new_value, "Réseau, SAV")

    def test_suggestions_are_deduplicated_and_sorted(self):
        Project.objects.create(
            name="Projet C", organisation=self.manager.organisation, domain="logistique", services=["Achats"]
        )
        result = services.get_project_categories(actor=self.manager)
        self.assertEqual(result["domains"], ["Logistique"])
        self.assertEqual(result["services"], ["Achats", "Pôle Planning", "SAV"])

    def test_suggestions_ignore_other_organisations(self):
        elsewhere = Organisation.objects.create(name="Autre entreprise")
        Project.objects.create(name="Ailleurs", organisation=elsewhere, domain="Secret", services=["Caché"])
        result = services.get_project_categories(actor=self.manager)
        self.assertNotIn("Secret", result["domains"])
        self.assertNotIn("Caché", result["services"])


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
class ProjectCategoryApiTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="cat-manager-api")
        self.project = Project.objects.create(name="Projet A", organisation=self.manager.organisation)
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        Project.objects.create(name="Projet B", organisation=self.manager.organisation, domain="E-commerce")

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_update_details_accepts_categories(self):
        response = self.client.post(
            f"/api/v1/projects/{self.project.id}/update-details/",
            {"domain": "e-commerce", "services": ["Marketing"]},
            format="json",
            **self.as_user(self.manager),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["domain"], "E-commerce")
        self.assertEqual(response.json()["services"], ["Marketing"])

    def test_categories_endpoint(self):
        response = self.client.get("/api/v1/projects/categories/", **self.as_user(self.manager))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"domains": ["E-commerce"], "services": []})
