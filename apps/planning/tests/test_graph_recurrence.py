"""Traduction RRULE → motif de récurrence Graph (session du 2026-09-22,
suite Outlook). Ne couvre que le sous-ensemble produit par l'éditeur front
(frontend/src/features/planning/recurrence.ts) — voir la docstring de
`build_graph_recurrence`."""

from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils.dateparse import parse_datetime

from apps.planning.graph_client import build_graph_recurrence


def _event(recurrence_rule, start="2026-10-02T09:00:00+02:00"):
    # SimpleNamespace suffit : build_graph_recurrence ne lit que
    # `.recurrence_rule` et `.start`, pas besoin d'un vrai CalendarEvent/DB.
    return SimpleNamespace(recurrence_rule=recurrence_rule, start=parse_datetime(start))


class BuildGraphRecurrenceTests(SimpleTestCase):
    def test_weekly_with_byday(self):
        # 2026-10-02 est un vendredi.
        result = build_graph_recurrence(_event("FREQ=WEEKLY;BYDAY=MO,WE"))
        self.assertEqual(result["pattern"], {"type": "weekly", "interval": 1, "daysOfWeek": ["monday", "wednesday"]})
        self.assertEqual(result["range"], {"type": "noEnd", "startDate": "2026-10-02"})

    def test_weekly_without_byday_derives_from_start_weekday(self):
        result = build_graph_recurrence(_event("FREQ=WEEKLY"))
        self.assertEqual(result["pattern"]["daysOfWeek"], ["friday"])

    def test_daily_with_interval(self):
        result = build_graph_recurrence(_event("FREQ=DAILY;INTERVAL=3"))
        self.assertEqual(result["pattern"], {"type": "daily", "interval": 3})

    def test_monthly_uses_start_day_of_month(self):
        result = build_graph_recurrence(_event("FREQ=MONTHLY", start="2026-10-15T09:00:00+02:00"))
        self.assertEqual(result["pattern"], {"type": "absoluteMonthly", "interval": 1, "dayOfMonth": 15})

    def test_yearly_uses_start_day_and_month(self):
        result = build_graph_recurrence(_event("FREQ=YEARLY", start="2026-03-15T09:00:00+02:00"))
        self.assertEqual(
            result["pattern"], {"type": "absoluteYearly", "interval": 1, "dayOfMonth": 15, "month": 3}
        )

    def test_until_produces_end_date_range(self):
        result = build_graph_recurrence(_event("FREQ=DAILY;UNTIL=20261231T235959Z"))
        self.assertEqual(result["range"], {"type": "endDate", "startDate": "2026-10-02", "endDate": "2026-12-31"})

    def test_count_produces_numbered_range(self):
        result = build_graph_recurrence(_event("FREQ=DAILY;COUNT=10"))
        self.assertEqual(result["range"], {"type": "numbered", "startDate": "2026-10-02", "numberOfOccurrences": 10})

    def test_no_end_condition_produces_no_end_range(self):
        result = build_graph_recurrence(_event("FREQ=DAILY"))
        self.assertEqual(result["range"], {"type": "noEnd", "startDate": "2026-10-02"})

    def test_unsupported_key_returns_none(self):
        # BYMONTHDAY : accepté par le backend (RRULE plus riche que ce que
        # l'éditeur produit), pas traduit — ignoré plutôt qu'approximé.
        self.assertIsNone(build_graph_recurrence(_event("FREQ=MONTHLY;BYMONTHDAY=15")))

    def test_unsupported_freq_returns_none(self):
        self.assertIsNone(build_graph_recurrence(_event("FREQ=SECONDLY")))

    def test_empty_rule_returns_none(self):
        self.assertIsNone(build_graph_recurrence(_event("")))
