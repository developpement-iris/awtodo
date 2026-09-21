"""Horaires de travail (session du 2026-09-18) : modèle hebdomadaire
récurrent, exceptions par semaine calendaire, délégation via CalendarShare."""

from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.planning.models import CalendarShare, WorkingHoursDay, WorkingHoursWeekOverride
from apps.planning.services import (
    PlanningPermissionError,
    PlanningValidationError,
    clear_working_hours_override,
    create_share,
    get_working_hours,
    update_working_hours,
)

MON = [{"weekday": 0, "enabled": True, "start": "08:00", "end": "17:00"}]


class WorkingHoursServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="wh-user")
        self.other = User.objects.create(username="wh-other")

    def test_default_schedule_is_monday_to_friday(self):
        data = get_working_hours(actor=self.user, target_user=self.user)

        self.assertFalse(data["is_override"])
        enabled = {d["weekday"] for d in data["days"] if d["enabled"]}
        self.assertEqual(enabled, {0, 1, 2, 3, 4})
        self.assertEqual(data["days"][0]["start"], "09:00")

    def test_update_base_schedule(self):
        import datetime

        update_working_hours(
            actor=self.user,
            target_user=self.user,
            days=[{"weekday": 0, "enabled": True, "start": datetime.time(8, 0), "end": datetime.time(17, 0)}],
        )

        day = WorkingHoursDay.objects.get(user=self.user, weekday=0)
        self.assertEqual(day.start, datetime.time(8, 0))
        self.assertEqual(day.end, datetime.time(17, 0))

    def test_disabling_a_day_works(self):
        import datetime

        update_working_hours(
            actor=self.user,
            target_user=self.user,
            days=[{"weekday": 1, "enabled": False, "start": datetime.time(9, 0), "end": datetime.time(18, 0)}],
        )

        day = WorkingHoursDay.objects.get(user=self.user, weekday=1)
        self.assertFalse(day.enabled)

    def test_invalid_range_rejected(self):
        import datetime

        with self.assertRaises(PlanningValidationError):
            update_working_hours(
                actor=self.user,
                target_user=self.user,
                days=[{"weekday": 0, "enabled": True, "start": datetime.time(18, 0), "end": datetime.time(9, 0)}],
            )

    def test_week_override_takes_precedence(self):
        import datetime

        week_start = datetime.date(2026, 9, 21)  # un lundi
        update_working_hours(
            actor=self.user,
            target_user=self.user,
            week_start=week_start,
            days=[{"weekday": 0, "enabled": True, "start": datetime.time(7, 0), "end": datetime.time(12, 0)}],
        )

        override_data = get_working_hours(actor=self.user, target_user=self.user, week_start=week_start)
        self.assertTrue(override_data["is_override"])
        self.assertEqual(override_data["days"][0]["start"], "07:00")

        # Le modèle de base n'est pas affecté.
        base_data = get_working_hours(actor=self.user, target_user=self.user)
        self.assertFalse(base_data["is_override"])
        self.assertEqual(base_data["days"][0]["start"], "09:00")

    def test_clear_override_returns_to_base(self):
        import datetime

        week_start = datetime.date(2026, 9, 21)
        update_working_hours(
            actor=self.user,
            target_user=self.user,
            week_start=week_start,
            days=[{"weekday": 0, "enabled": True, "start": datetime.time(7, 0), "end": datetime.time(12, 0)}],
        )
        self.assertTrue(WorkingHoursWeekOverride.objects.filter(user=self.user, week_start=week_start).exists())

        clear_working_hours_override(actor=self.user, target_user=self.user, week_start=week_start)

        self.assertFalse(WorkingHoursWeekOverride.objects.filter(user=self.user, week_start=week_start).exists())
        data = get_working_hours(actor=self.user, target_user=self.user, week_start=week_start)
        self.assertFalse(data["is_override"])

    def test_stranger_cannot_view_or_manage(self):
        with self.assertRaises(PlanningPermissionError):
            get_working_hours(actor=self.other, target_user=self.user)
        with self.assertRaises(PlanningPermissionError):
            update_working_hours(actor=self.other, target_user=self.user, days=MON)

    def test_plain_share_grants_view_but_not_manage(self):
        create_share(actor=self.user, grantee=self.other)

        get_working_hours(actor=self.other, target_user=self.user)  # ne lève pas
        with self.assertRaises(PlanningPermissionError):
            update_working_hours(actor=self.other, target_user=self.user, days=MON)

    def test_delegated_share_grants_manage(self):
        import datetime

        create_share(actor=self.user, grantee=self.other, can_manage_work_hours=True)

        update_working_hours(
            actor=self.other,
            target_user=self.user,
            days=[{"weekday": 0, "enabled": True, "start": datetime.time(7, 30), "end": datetime.time(16, 0)}],
        )
        day = WorkingHoursDay.objects.get(user=self.user, weekday=0)
        self.assertEqual(day.start, datetime.time(7, 30))


@override_settings(
    DEBUG=True,
    REST_FRAMEWORK={
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
        "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.DebugUserIdAuthentication"],
    },
)
class WorkingHoursApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(username="wh-api-user")
        self.delegate = User.objects.create(username="wh-api-delegate")

    def _as(self, user):
        self.client.credentials(HTTP_X_DEBUG_USER_ID=str(user.id))

    def test_get_own_schedule(self):
        self._as(self.user)
        r = self.client.get("/api/v1/planning/working-hours/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["days"]), 7)

    def test_patch_own_schedule(self):
        self._as(self.user)
        r = self.client.patch(
            "/api/v1/planning/working-hours/",
            {"days": [{"weekday": 0, "enabled": True, "start": "08:30", "end": "16:30"}]},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["days"][0]["start"], "08:30")

    def test_patch_week_override_via_api(self):
        self._as(self.user)
        r = self.client.patch(
            "/api/v1/planning/working-hours/",
            {
                "week_start": "2026-09-21",
                "days": [{"weekday": 0, "enabled": False, "start": "09:00", "end": "18:00"}],
            },
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_override"])

        r2 = self.client.delete("/api/v1/planning/working-hours/?week=2026-09-21")
        self.assertEqual(r2.status_code, 200)
        self.assertFalse(r2.data["is_override"])

    def test_delegate_without_grant_forbidden(self):
        self._as(self.delegate)
        r = self.client.patch(
            f"/api/v1/planning/working-hours/?user={self.user.id}",
            {"user": str(self.user.id), "days": MON},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_delegate_with_grant_allowed(self):
        CalendarShare.objects.create(owner=self.user, grantee=self.delegate, can_manage_work_hours=True)
        self._as(self.delegate)
        r = self.client.patch(
            "/api/v1/planning/working-hours/",
            {"user": str(self.user.id), "days": MON},
            format="json",
        )
        self.assertEqual(r.status_code, 200)

    def test_share_create_with_manage_flag(self):
        self._as(self.user)
        r = self.client.post(
            "/api/v1/planning/shares/",
            {"grantee": str(self.delegate.id), "can_manage_work_hours": True},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["can_manage_work_hours"])
