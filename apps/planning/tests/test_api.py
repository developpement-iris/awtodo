from django.core import mail
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.incidents.models import Incident
from apps.notifications.models import Notification
from apps.planning.models import CalendarEvent, ScheduledBlock
from apps.projects.models import Project, ProjectMembership, ProjectVersion
from apps.tasks.models import Task

FROM = "2026-06-01T00:00:00+02:00"
TO = "2026-06-30T00:00:00+02:00"


@override_settings(
    DEBUG=True,
    REST_FRAMEWORK={
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
        "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.DebugUserIdAuthentication"],
    },
)
class PlanningApiTests(APITestCase):
    def setUp(self):
        self.mgr = User.objects.create(username="mgr", email="mgr@x.io")
        self.member = User.objects.create(username="mbr", email="mbr@x.io")
        self.outsider = User.objects.create(username="out")
        self.project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=self.project, user=self.mgr, role="chef_de_projet")
        ProjectMembership.objects.create(project=self.project, user=self.member, role="membre")
        self.version = ProjectVersion.objects.create(project=self.project, label="v1", is_current=True)

    def _as(self, user):
        self.client.credentials(HTTP_X_DEBUG_USER_ID=str(user.id))

    def _calendar(self, user, **params):
        self._as(user)
        q = {"from": FROM, "to": TO, **params}
        return self.client.get("/api/v1/planning/calendar/", q)

    # --- Événements personnels ------------------------------------------
    def test_create_event_appears_in_calendar(self):
        self._as(self.member)
        r = self.client.post(
            "/api/v1/planning/events/",
            {"title": "Point équipe", "start": "2026-06-10T09:00:00+02:00", "end": "2026-06-10T10:00:00+02:00"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        cal = self._calendar(self.member).data
        self.assertEqual(len(cal["events"]), 1)
        self.assertEqual(cal["events"][0]["title"], "Point équipe")

    def test_recurring_event_is_expanded(self):
        self._as(self.member)
        self.client.post(
            "/api/v1/planning/events/",
            {
                "title": "Daily",
                "start": "2026-06-01T09:00:00+02:00",
                "end": "2026-06-01T09:15:00+02:00",
                "recurrence_rule": "FREQ=DAILY;COUNT=5",
            },
            format="json",
        )
        cal = self._calendar(self.member).data
        self.assertEqual(len(cal["events"]), 5)
        self.assertTrue(all(o["is_recurring"] for o in cal["events"]))

    def test_invalid_recurrence_rule_rejected(self):
        self._as(self.member)
        r = self.client.post(
            "/api/v1/planning/events/",
            {
                "title": "X",
                "start": "2026-06-01T09:00:00+02:00",
                "end": "2026-06-01T10:00:00+02:00",
                "recurrence_rule": "FREQ=BOGUS",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_sub_daily_recurrence_rejected(self):
        self._as(self.member)
        r = self.client.post(
            "/api/v1/planning/events/",
            {
                "title": "X",
                "start": "2026-06-01T09:00:00+02:00",
                "end": "2026-06-01T10:00:00+02:00",
                "recurrence_rule": "FREQ=MINUTELY;COUNT=100",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_stranger_cannot_edit_event(self):
        # Un tiers qui ne voit pas l'événement obtient 404 (scoping "gratuit"
        # du get_queryset, cohérent avec le reste du projet) ; un participant
        # qui le voit obtient 403 (voir test_participant_flow_and_notification).
        event = CalendarEvent.objects.create(
            owner=self.member, title="A", start="2026-06-10T09:00:00+02:00", end="2026-06-10T10:00:00+02:00"
        )
        self._as(self.mgr)
        r = self.client.patch(f"/api/v1/planning/events/{event.id}/", {"title": "B"}, format="json")
        self.assertIn(r.status_code, (403, 404))

    def test_cancel_event_removes_it_from_calendar(self):
        event = CalendarEvent.objects.create(
            owner=self.member, title="A", start="2026-06-10T09:00:00+02:00", end="2026-06-10T10:00:00+02:00"
        )
        self._as(self.member)
        r = self.client.post(f"/api/v1/planning/events/{event.id}/cancel/")
        self.assertEqual(r.status_code, 204)
        self.assertEqual(self._calendar(self.member).data["events"], [])

    def test_end_before_start_rejected(self):
        self._as(self.member)
        r = self.client.post(
            "/api/v1/planning/events/",
            {"title": "X", "start": "2026-06-10T10:00:00+02:00", "end": "2026-06-10T09:00:00+02:00"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    # --- Participants --------------------------------------------------
    def test_participant_flow_and_notification(self):
        event = CalendarEvent.objects.create(
            owner=self.mgr, title="Revue", start="2026-06-10T09:00:00+02:00", end="2026-06-10T10:00:00+02:00"
        )
        self._as(self.mgr)
        r = self.client.post(
            f"/api/v1/planning/events/{event.id}/participants/", {"user": str(self.member.id)}, format="json"
        )
        self.assertEqual(r.status_code, 201)
        self.assertTrue(
            Notification.objects.filter(recipient=self.member, verb="event_invited", event=event).exists()
        )
        self.assertTrue(mail.outbox)

        # Le participant voit l'événement sur son propre calendrier.
        cal = self._calendar(self.member).data
        self.assertEqual(len(cal["events"]), 1)
        self.assertTrue(cal["events"][0]["read_only"])

        # Il peut répondre...
        self._as(self.member)
        r = self.client.post(
            f"/api/v1/planning/events/{event.id}/respond/", {"response": "accepte"}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        # ...mais pas éditer.
        r = self.client.patch(f"/api/v1/planning/events/{event.id}/", {"title": "X"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_outsider_to_event_cannot_respond(self):
        event = CalendarEvent.objects.create(
            owner=self.mgr, title="Revue", start="2026-06-10T09:00:00+02:00", end="2026-06-10T10:00:00+02:00"
        )
        self._as(self.outsider)
        r = self.client.post(
            f"/api/v1/planning/events/{event.id}/respond/", {"response": "accepte"}, format="json"
        )
        self.assertIn(r.status_code, (403, 404))

    # --- Créneaux tâches ---------------------------------------------
    def _task_for(self, user):
        return Task.objects.create(
            project=self.project, version=self.version, title="T", task_type="ajout",
            status="assignee", assignee=user,
        )

    def test_schedule_assigned_task(self):
        task = self._task_for(self.member)
        self._as(self.member)
        r = self.client.post(
            "/api/v1/planning/blocks/",
            {"task": str(task.id), "start": "2026-06-09T14:00:00+02:00", "end": "2026-06-09T16:00:00+02:00"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        cal = self._calendar(self.member).data
        self.assertEqual(len(cal["blocks"]), 1)
        self.assertEqual(cal["blocks"][0]["task"]["id"], str(task.id))
        task.refresh_from_db()
        self.assertEqual(task.status, "assignee")  # statut inchangé

    def test_cannot_schedule_task_not_assigned_to_me(self):
        task = self._task_for(self.mgr)
        self._as(self.member)
        r = self.client.post(
            "/api/v1/planning/blocks/",
            {"task": str(task.id), "start": "2026-06-09T14:00:00+02:00", "end": "2026-06-09T16:00:00+02:00"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_block_move_keeps_task_status(self):
        task = self._task_for(self.member)
        block = ScheduledBlock.objects.create(
            owner=self.member, task=task, start="2026-06-09T14:00:00+02:00", end="2026-06-09T16:00:00+02:00"
        )
        self._as(self.member)
        r = self.client.patch(
            f"/api/v1/planning/blocks/{block.id}/",
            {"start": "2026-06-10T14:00:00+02:00", "end": "2026-06-10T16:00:00+02:00"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, "assignee")

    def test_task_can_be_scheduled_multiple_times(self):
        task = self._task_for(self.member)
        self._as(self.member)
        for day in ("09", "10"):
            r = self.client.post(
                "/api/v1/planning/blocks/",
                {
                    "task": str(task.id),
                    "start": f"2026-06-{day}T14:00:00+02:00",
                    "end": f"2026-06-{day}T16:00:00+02:00",
                },
                format="json",
            )
            self.assertEqual(r.status_code, 201)
        self.assertEqual(len(self._calendar(self.member).data["blocks"]), 2)

    def test_cancel_block_removes_it(self):
        task = self._task_for(self.member)
        block = ScheduledBlock.objects.create(
            owner=self.member, task=task, start="2026-06-09T14:00:00+02:00", end="2026-06-09T15:00:00+02:00"
        )
        self._as(self.member)
        r = self.client.post(f"/api/v1/planning/blocks/{block.id}/cancel/")
        self.assertEqual(r.status_code, 204)
        self.assertEqual(self._calendar(self.member).data["blocks"], [])

    def test_block_requires_exactly_one_target(self):
        self._as(self.member)
        r = self.client.post(
            "/api/v1/planning/blocks/",
            {"start": "2026-06-09T14:00:00+02:00", "end": "2026-06-09T16:00:00+02:00"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    # --- Planning projet -------------------------------------------
    def test_project_planning_manager_creates_member_reads(self):
        self._as(self.mgr)
        r = self.client.post(
            f"/api/v1/planning/projects/{self.project.id}/entries/",
            {
                "title": "Jalon 1", "kind": "jalon",
                "start": "2026-06-15T09:00:00+02:00", "end": "2026-06-15T10:00:00+02:00",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201)

        self._as(self.member)
        r = self.client.get(
            f"/api/v1/planning/projects/{self.project.id}/entries/", {"from": FROM, "to": TO}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["entries"]), 1)
        self.assertFalse(r.data["can_manage"])

        # Le membre voit aussi l'entrée dans son calendrier personnel.
        self.assertEqual(len(self._calendar(self.member).data["project_entries"]), 1)

    def test_member_cannot_create_project_entry(self):
        self._as(self.member)
        r = self.client.post(
            f"/api/v1/planning/projects/{self.project.id}/entries/",
            {"title": "X", "start": "2026-06-15T09:00:00+02:00", "end": "2026-06-15T10:00:00+02:00"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_outsider_gets_404_on_project_planning(self):
        self._as(self.outsider)
        r = self.client.get(
            f"/api/v1/planning/projects/{self.project.id}/entries/", {"from": FROM, "to": TO}
        )
        self.assertEqual(r.status_code, 404)

    # --- Partage de calendrier ------------------------------------
    def test_share_overlay_visible_then_revoked(self):
        CalendarEvent.objects.create(
            owner=self.mgr, title="Privé mgr", start="2026-06-12T09:00:00+02:00", end="2026-06-12T10:00:00+02:00"
        )
        self._as(self.mgr)
        r = self.client.post(
            "/api/v1/planning/shares/", {"grantee": str(self.member.id)}, format="json"
        )
        self.assertEqual(r.status_code, 201)
        share_id = r.data["id"]

        cal = self._calendar(self.member).data
        self.assertEqual(len(cal["shared"]), 1)
        self.assertEqual(len(cal["shared"][0]["occurrences"]), 1)
        self.assertTrue(cal["shared"][0]["occurrences"][0]["read_only"])

        # Le bénéficiaire peut révoquer lui-même.
        self._as(self.member)
        r = self.client.post(f"/api/v1/planning/shares/{share_id}/revoke/")
        self.assertEqual(r.status_code, 204)
        self.assertEqual(self._calendar(self.member).data["shared"], [])

    def test_shared_calendar_includes_owner_task_blocks(self):
        task = self._task_for(self.mgr)
        ScheduledBlock.objects.create(
            owner=self.mgr, task=task, start="2026-06-12T14:00:00+02:00", end="2026-06-12T16:00:00+02:00"
        )
        self._as(self.mgr)
        self.client.post("/api/v1/planning/shares/", {"grantee": str(self.member.id)}, format="json")

        shared = self._calendar(self.member).data["shared"]
        self.assertEqual(len(shared), 1)
        self.assertEqual(len(shared[0]["blocks"]), 1)
        self.assertEqual(shared[0]["blocks"][0]["task"]["id"], str(task.id))
        # Le créneau ne fuite pas dans "mes" blocs à moi.
        self.assertEqual(self._calendar(self.member).data["blocks"], [])

    def test_cannot_share_with_self(self):
        self._as(self.mgr)
        r = self.client.post("/api/v1/planning/shares/", {"grantee": str(self.mgr.id)}, format="json")
        self.assertEqual(r.status_code, 400)

    # --- Fenêtre du calendrier -----------------------------------
    def test_calendar_requires_from_and_to(self):
        self._as(self.member)
        self.assertEqual(self.client.get("/api/v1/planning/calendar/").status_code, 400)

    def test_calendar_window_capped(self):
        self._as(self.member)
        r = self.client.get(
            "/api/v1/planning/calendar/",
            {"from": "2026-01-01T00:00:00+01:00", "to": "2026-12-31T00:00:00+01:00"},
        )
        self.assertEqual(r.status_code, 400)

    def test_debug_header_ignored_without_debug(self):
        with override_settings(DEBUG=False):
            r = self.client.get("/api/v1/planning/calendar/", {"from": FROM, "to": TO})
            self.assertIn(r.status_code, (401, 403))


@override_settings(
    DEBUG=True,
    REST_FRAMEWORK={
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
        "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.DebugUserIdAuthentication"],
    },
)
class ProjectPlanningPermissionFlagTests(APITestCase):
    def test_flag_exposed_on_project(self):
        mgr = User.objects.create(username="mgr")
        member = User.objects.create(username="mbr")
        project = Project.objects.create(name="P", project_type="collaboratif")
        ProjectMembership.objects.create(project=project, user=mgr, role="chef_de_projet")
        ProjectMembership.objects.create(project=project, user=member, role="membre")

        self.client.credentials(HTTP_X_DEBUG_USER_ID=str(mgr.id))
        r = self.client.get(f"/api/v1/projects/{project.id}/")
        self.assertTrue(r.data["permissions"]["can_manage_project_planning"])

        self.client.credentials(HTTP_X_DEBUG_USER_ID=str(member.id))
        r = self.client.get(f"/api/v1/projects/{project.id}/")
        self.assertFalse(r.data["permissions"]["can_manage_project_planning"])
