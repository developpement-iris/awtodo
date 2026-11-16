"""Charge par personne et phases de la feuille de route (session du
2026-11-14)."""

from datetime import date, datetime

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.planning import workload
from apps.planning.models import ProjectPlanningEntry, ScheduledBlock
from apps.planning.services import (
    PlanningValidationError,
    get_workload,
)
from apps.projects.models import Project, ProjectMembership
from apps.tasks.models import Task


def local(*args):
    return timezone.make_aware(datetime(*args))


class HalfDayTests(TestCase):
    def test_afternoon_only(self):
        self.assertEqual(workload.half_days(local(2027, 1, 5, 14), local(2027, 1, 5, 17)), {(date(2027, 1, 5), "pm")})

    def test_morning_only(self):
        self.assertEqual(workload.half_days(local(2027, 1, 5, 9), local(2027, 1, 5, 12)), {(date(2027, 1, 5), "am")})

    def test_spanning_noon_counts_both(self):
        self.assertEqual(
            workload.half_days(local(2027, 1, 5, 11), local(2027, 1, 5, 14)),
            {(date(2027, 1, 5), "am"), (date(2027, 1, 5), "pm")},
        )

    def test_ending_exactly_at_one_pm_is_morning_only(self):
        self.assertEqual(workload.half_days(local(2027, 1, 5, 9), local(2027, 1, 5, 13)), {(date(2027, 1, 5), "am")})

    def test_over_two_days(self):
        slots = workload.half_days(local(2027, 1, 5, 14), local(2027, 1, 6, 11))
        self.assertEqual(slots, {(date(2027, 1, 5), "pm"), (date(2027, 1, 6), "am")})

    def test_empty_interval(self):
        self.assertEqual(workload.half_days(local(2027, 1, 5, 14), local(2027, 1, 5, 14)), set())

    def test_periods_by_month_are_clipped(self):
        periods = workload.build_periods(date(2027, 1, 15), date(2027, 3, 10), "month")
        self.assertEqual([p["key"] for p in periods], ["2027-01", "2027-02", "2027-03"])
        self.assertEqual(periods[0]["start"], date(2027, 1, 15))
        self.assertEqual(periods[1]["end"], date(2027, 2, 28))
        self.assertEqual(periods[2]["end"], date(2027, 3, 10))

    def test_periods_by_week(self):
        periods = workload.build_periods(date(2027, 1, 4), date(2027, 1, 17), "week")
        self.assertEqual([p["key"] for p in periods], ["2027-W01", "2027-W02"])

    def test_working_days(self):
        self.assertEqual(workload.working_days(date(2027, 1, 1), date(2027, 1, 31)), 21)


class WorkloadServiceTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create(username="cdp", email="cdp@x.io", first_name="Romain")
        self.alice = User.objects.create(username="alice", email="alice@x.io", first_name="Alice")
        self.reader = User.objects.create(username="lecteur", email="lecteur@x.io", first_name="Léo")
        self.stranger = User.objects.create(username="autre", email="autre@x.io", first_name="Zoé")
        self.project = Project.objects.create(name="Projet X", deadline=date(2027, 6, 30))
        Project.objects.filter(pk=self.project.pk).update(created_at=local(2026, 10, 1, 9))
        self.project.refresh_from_db()
        for user, role in ((self.manager, "chef_de_projet"), (self.alice, "membre"), (self.reader, "lecteur")):
            ProjectMembership.objects.create(project=self.project, user=user, role=role)

    def january(self, actor, **kwargs):
        return get_workload(actor=actor, first_day=date(2027, 1, 1), last_day=date(2027, 1, 31), **kwargs)

    def row(self, result, user):
        return next(r for r in result["people"] if r["user"]["id"] == str(user.id))

    def test_four_tuesday_afternoons_in_january(self):
        entry = ProjectPlanningEntry.objects.create(
            project=self.project,
            title="Atelier",
            kind="reunion",
            start=local(2027, 1, 5, 14),
            end=local(2027, 1, 5, 17),
            recurrence_rule="FREQ=WEEKLY;BYDAY=TU;COUNT=4",
        )
        entry.assignees.add(self.alice)

        cell = self.row(self.january(self.manager), self.alice)["periods"]["2027-01"]
        self.assertEqual(cell["half_days"], 4)
        self.assertEqual(cell["projects"][0]["afternoons"], 4)
        self.assertEqual(cell["projects"][0]["mornings"], 0)

    def test_all_day_entries_are_not_counted(self):
        entry = ProjectPlanningEntry.objects.create(
            project=self.project,
            title="Phase développement",
            kind="phase",
            all_day=True,
            start=local(2027, 1, 1),
            end=local(2027, 1, 31),
        )
        entry.assignees.add(self.alice)

        self.assertEqual(self.row(self.january(self.manager), self.alice)["periods"]["2027-01"]["half_days"], 0)

    def test_task_blocks_are_counted(self):
        task = Task.objects.create(project=self.project, title="Maquette", assignee=self.alice, status="assignee")
        ScheduledBlock.objects.create(owner=self.alice, task=task, start=local(2027, 1, 12, 9), end=local(2027, 1, 12, 12))

        cell = self.row(self.january(self.manager), self.alice)["periods"]["2027-01"]
        self.assertEqual(cell["half_days"], 1)
        self.assertEqual(cell["projects"][0]["mornings"], 1)

    def test_same_half_day_twice_counts_once(self):
        task = Task.objects.create(project=self.project, title="Maquette", assignee=self.alice, status="assignee")
        ScheduledBlock.objects.create(owner=self.alice, task=task, start=local(2027, 1, 12, 14), end=local(2027, 1, 12, 15))
        ScheduledBlock.objects.create(owner=self.alice, task=task, start=local(2027, 1, 12, 16), end=local(2027, 1, 12, 17))

        self.assertEqual(self.row(self.january(self.manager), self.alice)["periods"]["2027-01"]["half_days"], 1)

    def test_engaged_projects_count_excludes_readers(self):
        result = self.january(self.manager)
        self.assertEqual(self.row(result, self.alice)["periods"]["2027-01"]["projects_count"], 1)
        self.assertFalse(any(r["user"]["id"] == str(self.reader.id) for r in result["people"]))

    def test_reader_assigned_to_an_entry_is_not_counted(self):
        entry = ProjectPlanningEntry.objects.create(
            project=self.project, title="Revue", start=local(2027, 1, 5, 14), end=local(2027, 1, 5, 16)
        )
        entry.assignees.add(self.reader)

        cell = self.row(self.january(self.reader), self.reader)["periods"]["2027-01"]
        self.assertEqual(cell["half_days"], 0)
        self.assertEqual(cell["projects_count"], 0)

    def test_project_not_started_does_not_count(self):
        result = get_workload(actor=self.manager, first_day=date(2026, 9, 1), last_day=date(2026, 9, 30))
        self.assertEqual(self.row(result, self.alice)["periods"]["2026-09"]["projects_count"], 0)

    def test_project_finished_does_not_count(self):
        result = get_workload(actor=self.manager, first_day=date(2027, 7, 1), last_day=date(2027, 7, 31))
        self.assertEqual(self.row(result, self.alice)["periods"]["2027-07"]["projects_count"], 0)

    def test_member_only_sees_self(self):
        result = self.january(self.alice)
        self.assertEqual([r["user"]["id"] for r in result["people"]], [str(self.alice.id)])

    def test_manager_sees_contributors_of_managed_projects(self):
        ids = {r["user"]["id"] for r in self.january(self.manager)["people"]}
        self.assertEqual(ids, {str(self.manager.id), str(self.alice.id)})

    def test_org_admin_sees_everyone(self):
        self.stranger.organisation_role = "admin"
        self.stranger.save()
        ids = {r["user"]["id"] for r in self.january(self.stranger)["people"]}
        self.assertTrue({str(self.manager.id), str(self.alice.id), str(self.reader.id)} <= ids)

    def test_projects_the_viewer_cannot_see_are_hidden(self):
        secret = Project.objects.create(name="Projet secret")
        ProjectMembership.objects.create(project=secret, user=self.alice, role="membre")
        task = Task.objects.create(project=secret, title="T", assignee=self.alice, status="assignee")
        ScheduledBlock.objects.create(owner=self.alice, task=task, start=local(2027, 1, 7, 9), end=local(2027, 1, 7, 11))

        cell = self.row(self.january(self.manager), self.alice)["periods"]["2027-01"]
        self.assertEqual(cell["half_days"], 1)
        self.assertEqual(cell["hidden_half_days"], 1)
        self.assertEqual(cell["hidden_projects"], 1)
        self.assertNotIn("Projet secret", [p["name"] for p in cell["projects"]])

    def test_project_filter(self):
        other = Project.objects.create(name="Projet Y")
        ProjectMembership.objects.create(project=other, user=self.alice, role="membre")
        cell = self.row(self.january(self.manager, project_ids=[str(self.project.id)]), self.alice)["periods"]["2027-01"]
        self.assertEqual(cell["projects_count"], 1)

    def test_capacity_and_limits(self):
        result = self.january(self.manager)
        self.assertEqual(result["periods"][0]["capacity_half_days"], 42)
        with self.assertRaises(PlanningValidationError):
            get_workload(actor=self.manager, first_day=date(2027, 1, 1), last_day=date(2028, 6, 1))
        with self.assertRaises(PlanningValidationError):
            self.january(self.manager, granularity="day")


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
class WorkloadApiTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create(username="cdp-api", email="cdp-api@x.io")
        project = Project.objects.create(name="Projet X")
        ProjectMembership.objects.create(project=project, user=self.manager, role="chef_de_projet")

    def headers(self):
        return {"HTTP_X_DEBUG_USER_ID": str(self.manager.id)}

    def test_workload_endpoint(self):
        response = self.client.get(
            "/api/v1/planning/workload/?from=2027-01-01&to=2027-03-31&granularity=month", **self.headers()
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p["key"] for p in response.json()["periods"]], ["2027-01", "2027-02", "2027-03"])

    def test_workload_rejects_bad_dates(self):
        response = self.client.get("/api/v1/planning/workload/?from=janvier&to=2027-03-31", **self.headers())
        self.assertEqual(response.status_code, 400)
