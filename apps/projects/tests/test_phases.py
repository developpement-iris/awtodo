"""Phases personnalisées d'un projet (session du 2026-11-16) : un nom et une
échéance par phase, début calculé, phase actuelle déduite de la date du jour."""

import datetime

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.models import AuditLogEntry

from .. import services
from ..models import Project, ProjectMembership, ProjectPhase

D = datetime.date


class ProjectPhaseServiceTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="phases-cdp")
        self.member = User.objects.create_user(username="phases-membre")
        self.project = Project.objects.create(name="Projet phases")
        Project.objects.filter(pk=self.project.pk).update(
            created_at=timezone.make_aware(datetime.datetime(2026, 10, 1, 9))
        )
        self.project.refresh_from_db()
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")

    def save(self, phases, actor=None):
        return services.save_project_phases(actor=actor or self.manager, project=self.project, phases=phases)

    def test_periods_follow_each_other(self):
        self.save(
            [
                {"name": "Recette", "due_date": D(2027, 1, 31)},
                {"name": "Cadrage", "due_date": D(2026, 11, 15)},
                {"name": "Développement", "due_date": D(2026, 12, 31)},
            ]
        )
        periods = services.phase_periods(self.project)
        self.assertEqual([p["name"] for p in periods], ["Cadrage", "Développement", "Recette"])
        self.assertEqual(periods[0]["start_date"], D(2026, 10, 1))
        self.assertEqual(periods[1]["start_date"], D(2026, 11, 16))
        self.assertEqual(periods[2]["start_date"], D(2027, 1, 1))

    def test_current_phase(self):
        self.save([{"name": "Cadrage", "due_date": D(2026, 11, 15)}, {"name": "Dév", "due_date": D(2026, 12, 31)}])
        self.assertEqual(services.current_phase(self.project, today=D(2026, 11, 20))["name"], "Dév")
        self.assertEqual(services.current_phase(self.project, today=D(2026, 11, 15))["name"], "Cadrage")
        # Après la dernière échéance, la dernière phase reste la phase actuelle.
        self.assertEqual(services.current_phase(self.project, today=D(2027, 3, 1))["name"], "Dév")

    def test_no_phase(self):
        self.assertEqual(services.phase_periods(self.project), [])
        self.assertIsNone(services.current_phase(self.project))

    def test_update_rename_and_archive(self):
        phases = self.save([{"name": "Cadrage", "due_date": D(2026, 11, 15)}, {"name": "Dév", "due_date": D(2026, 12, 31)}])
        cadrage, dev = phases
        self.save([{"id": cadrage.id, "name": "Étude", "due_date": D(2026, 11, 20)}])
        cadrage.refresh_from_db()
        dev.refresh_from_db()
        self.assertEqual((cadrage.name, cadrage.due_date, cadrage.status), ("Étude", D(2026, 11, 20), "active"))
        self.assertEqual(dev.status, "archived")
        self.assertEqual(ProjectPhase.all_objects.filter(project=self.project).count(), 2)

    def test_validation(self):
        with self.assertRaises(services.ProjectValidationError):
            self.save([{"name": "  ", "due_date": D(2026, 11, 15)}])
        with self.assertRaises(services.ProjectValidationError):
            self.save([{"name": "A", "due_date": D(2026, 11, 15)}, {"name": "B", "due_date": D(2026, 11, 15)}])
        other = Project.objects.create(name="Autre")
        foreign = ProjectPhase.objects.create(project=other, name="X", due_date=D(2026, 11, 1))
        with self.assertRaises(services.ProjectValidationError):
            self.save([{"id": foreign.id, "name": "X", "due_date": D(2026, 11, 1)}])

    def test_member_cannot_edit_phases(self):
        with self.assertRaises(services.ProjectPermissionError):
            self.save([{"name": "Cadrage", "due_date": D(2026, 11, 15)}], actor=self.member)

    def test_changes_are_audited(self):
        self.save([{"name": "Cadrage", "due_date": D(2026, 11, 15)}])
        entry = AuditLogEntry.objects.get(project=self.project, verb="phases_updated")
        self.assertIn("Cadrage (15/11/2026)", entry.new_value)


class ProjectPhaseApiTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="phases-cdp-api")
        self.member = User.objects.create_user(username="phases-membre-api")
        self.project = Project.objects.create(name="Projet API")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.url = f"/api/v1/projects/{self.project.id}/phases/"

    def test_manager_saves_phases_and_reads_them_back(self):
        self.client.force_authenticate(self.manager)
        future = timezone.localdate() + datetime.timedelta(days=30)
        response = self.client.put(
            self.url, {"phases": [{"name": "Cadrage", "due_date": future.isoformat()}]}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["phases"][0]["name"], "Cadrage")
        self.assertEqual(response.data["current_phase"]["name"], "Cadrage")
        listed = self.client.get("/api/v1/projects/")
        row = next(p for p in listed.data if p["id"] == str(self.project.id))
        self.assertEqual(row["phases"][0]["due_date"], future.isoformat())

    def test_member_is_refused(self):
        self.client.force_authenticate(self.member)
        response = self.client.put(self.url, {"phases": []}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_invalid_payload(self):
        self.client.force_authenticate(self.manager)
        response = self.client.put(self.url, {"phases": [{"name": "A"}]}, format="json")
        self.assertEqual(response.status_code, 400)
