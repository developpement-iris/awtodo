import datetime

from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.models import AuditLogEntry

from .. import services
from ..models import Project, ProjectMembership


class ProjectDetailsServiceTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="details-manager")
        self.member = User.objects.create_user(username="details-member")
        self.project = Project.objects.create(name="Projet Test", description="Avant")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def test_phase_is_unset_by_default(self):
        self.assertIsNone(self.project.phase)

    def test_manager_updates_details(self):
        services.update_project_details(
            actor=self.manager,
            project=self.project,
            name="  Nouveau nom  ",
            description="Après",
            priority="haute",
            phase="developpement",
            deadline=datetime.date(2027, 1, 15),
        )

        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Nouveau nom")
        self.assertEqual(self.project.description, "Après")
        self.assertEqual(self.project.priority, "haute")
        self.assertEqual(self.project.phase, "developpement")
        self.assertEqual(self.project.deadline, datetime.date(2027, 1, 15))

    def test_partial_update_leaves_other_fields(self):
        services.update_project_details(actor=self.manager, project=self.project, phase="a_l_etude")

        self.project.refresh_from_db()
        self.assertEqual(self.project.phase, "a_l_etude")
        self.assertEqual(self.project.description, "Avant")

    def test_member_cannot_update_details(self):
        with self.assertRaises(services.ProjectPermissionError):
            services.update_project_details(actor=self.member, project=self.project, phase="livraison")

    def test_empty_name_rejected(self):
        with self.assertRaises(services.ProjectValidationError):
            services.update_project_details(actor=self.manager, project=self.project, name="   ")

    def test_deadline_and_already_in_production_incompatible(self):
        with self.assertRaises(services.ProjectValidationError):
            services.update_project_details(
                actor=self.manager,
                project=self.project,
                already_in_production=True,
                deadline=datetime.date(2027, 1, 15),
            )

    def test_checking_already_in_production_clears_existing_deadline(self):
        self.project.deadline = datetime.date(2027, 1, 15)
        self.project.save()

        services.update_project_details(actor=self.manager, project=self.project, already_in_production=True)

        self.project.refresh_from_db()
        self.assertTrue(self.project.already_in_production)
        self.assertIsNone(self.project.deadline)

    def test_changes_are_audited(self):
        services.update_project_details(actor=self.manager, project=self.project, phase="en_ecriture")

        entry = AuditLogEntry.objects.get(project=self.project, field_name="phase")
        self.assertEqual(entry.new_value, "En écriture")

    def test_permission_flag(self):
        self.assertTrue(services.get_project_permissions(self.manager, self.project)["can_edit_details"])
        self.assertFalse(services.get_project_permissions(self.member, self.project)["can_edit_details"])

    def test_phase_at_creation(self):
        project = services.create_project(
            actor=self.manager, name="Avec phase", project_type="individuel", phase="a_l_etude"
        )
        self.assertEqual(project.phase, "a_l_etude")


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
class ProjectDetailsApiTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="details-manager-api")
        self.member = User.objects.create_user(username="details-member-api")
        self.project = Project.objects.create(name="Projet Test")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.url = f"/api/v1/projects/{self.project.id}/update-details/"

    def as_user(self, user):
        return {"HTTP_X_DEBUG_USER_ID": str(user.id)}

    def test_manager_updates_via_api(self):
        response = self.client.post(
            self.url, {"phase": "livraison", "deadline": None}, format="json", **self.as_user(self.manager)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["phase"], "livraison")
        self.assertEqual(response.json()["phase_display"], "Livraison")

    def test_phase_can_be_cleared(self):
        self.project.phase = "livraison"
        self.project.save()

        response = self.client.post(self.url, {"phase": None}, format="json", **self.as_user(self.manager))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["phase"])

    def test_invalid_phase_rejected(self):
        response = self.client.post(self.url, {"phase": "termine"}, format="json", **self.as_user(self.manager))

        self.assertEqual(response.status_code, 400)

    def test_member_forbidden(self):
        response = self.client.post(self.url, {"phase": "livraison"}, format="json", **self.as_user(self.member))

        self.assertEqual(response.status_code, 403)


class ProjectCoverImageTests(ProjectDetailsApiTests):
    def test_cover_image_set_and_cleared(self):
        response = self.client.post(
            self.url, {"cover_image": "portail-client"}, format="json", **self.as_user(self.manager)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["cover_image"], "portail-client")

        response = self.client.post(self.url, {"cover_image": ""}, format="json", **self.as_user(self.manager))
        self.assertEqual(response.json()["cover_image"], "")

    def test_unknown_cover_image_rejected(self):
        response = self.client.post(
            self.url, {"cover_image": "../../etc/passwd"}, format="json", **self.as_user(self.manager)
        )
        self.assertEqual(response.status_code, 400)
