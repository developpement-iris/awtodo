from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from django.test import TestCase
from django.utils import timezone

from apps.planning.services import MAX_OCCURRENCES, expand_occurrences


class _Source:
    def __init__(self, start, end, rule=""):
        self.id = id(self)
        self.start = start
        self.end = end
        self.recurrence_rule = rule


def _paris(year, month, day, hour=9, minute=0):
    return timezone.make_aware(datetime(year, month, day, hour, minute))


class ExpandOccurrencesTests(TestCase):
    def test_single_event_inside_window(self):
        src = _Source(_paris(2026, 6, 10, 9), _paris(2026, 6, 10, 10))
        occ = expand_occurrences([src], _paris(2026, 6, 1), _paris(2026, 6, 30))
        self.assertEqual(len(occ), 1)
        self.assertEqual(occ[0]["start"], src.start)

    def test_single_event_outside_window(self):
        src = _Source(_paris(2026, 1, 10, 9), _paris(2026, 1, 10, 10))
        occ = expand_occurrences([src], _paris(2026, 6, 1), _paris(2026, 6, 30))
        self.assertEqual(occ, [])

    def test_event_straddling_window_start_is_included(self):
        src = _Source(_paris(2026, 6, 1, 8), _paris(2026, 6, 1, 12))
        occ = expand_occurrences([src], _paris(2026, 6, 1, 10), _paris(2026, 6, 2))
        self.assertEqual(len(occ), 1)

    def test_daily_count(self):
        src = _Source(_paris(2026, 6, 1, 9), _paris(2026, 6, 1, 10), "FREQ=DAILY;COUNT=3")
        occ = expand_occurrences([src], _paris(2026, 6, 1), _paris(2026, 6, 30))
        self.assertEqual(len(occ), 3)
        self.assertEqual(
            [o["start"].date().isoformat() for o in occ],
            ["2026-06-01", "2026-06-02", "2026-06-03"],
        )

    def test_weekly_byday_within_two_weeks(self):
        # 2026-06-02 is a Tuesday.
        src = _Source(_paris(2026, 6, 2, 14), _paris(2026, 6, 2, 15), "FREQ=WEEKLY;BYDAY=TU")
        occ = expand_occurrences([src], _paris(2026, 6, 1), _paris(2026, 6, 15))
        self.assertEqual([o["start"].date().isoformat() for o in occ], ["2026-06-02", "2026-06-09"])

    def test_weekly_interval_two(self):
        src = _Source(_paris(2026, 6, 2, 14), _paris(2026, 6, 2, 15), "FREQ=WEEKLY;INTERVAL=2;BYDAY=TU")
        occ = expand_occurrences([src], _paris(2026, 6, 1), _paris(2026, 7, 1))
        self.assertEqual(
            [o["start"].date().isoformat() for o in occ],
            ["2026-06-02", "2026-06-16", "2026-06-30"],
        )

    def test_until_bounds_series(self):
        src = _Source(
            _paris(2026, 6, 1, 9),
            _paris(2026, 6, 1, 10),
            "FREQ=DAILY;UNTIL=20260603T235959Z",
        )
        occ = expand_occurrences([src], _paris(2026, 6, 1), _paris(2026, 6, 30))
        self.assertEqual(len(occ), 3)

    def test_monthly(self):
        src = _Source(_paris(2026, 1, 15, 9), _paris(2026, 1, 15, 10), "FREQ=MONTHLY")
        occ = expand_occurrences([src], _paris(2026, 3, 1), _paris(2026, 5, 31))
        self.assertEqual([o["start"].date().isoformat() for o in occ], ["2026-03-15", "2026-04-15", "2026-05-15"])

    def test_window_only_returns_overlapping_occurrences(self):
        src = _Source(_paris(2026, 1, 1, 9), _paris(2026, 1, 1, 10), "FREQ=DAILY")
        occ = expand_occurrences([src], _paris(2026, 6, 10), _paris(2026, 6, 13))
        self.assertEqual([o["start"].date().isoformat() for o in occ], ["2026-06-10", "2026-06-11", "2026-06-12"])

    def test_dst_spring_forward_keeps_wall_clock(self):
        # Europe/Paris switches to summer time on 2026-03-29.
        src = _Source(_paris(2026, 3, 24, 14), _paris(2026, 3, 24, 15), "FREQ=WEEKLY;BYDAY=TU")
        occ = expand_occurrences([src], _paris(2026, 3, 23), _paris(2026, 4, 8))
        local_hours = {timezone.localtime(o["start"]).hour for o in occ}
        self.assertEqual(local_hours, {14})
        # The UTC offset must actually differ across the boundary.
        utc_hours = {o["start"].astimezone(dt_timezone.utc).hour for o in occ}
        self.assertEqual(len(utc_hours), 2)

    def test_invalid_rule_is_skipped(self):
        src = _Source(_paris(2026, 6, 1, 9), _paris(2026, 6, 1, 10), "FREQ=NONSENSE;;;")
        occ = expand_occurrences([src], _paris(2026, 6, 1), _paris(2026, 6, 30))
        self.assertEqual(occ, [])

    def test_infinite_rule_is_capped(self):
        src = _Source(_paris(2020, 1, 1, 9), _paris(2020, 1, 1, 10), "FREQ=DAILY")
        occ = expand_occurrences([src], _paris(2020, 1, 1), _paris(2026, 1, 1))
        self.assertLessEqual(len(occ), MAX_OCCURRENCES)

    def test_results_sorted_by_start(self):
        a = _Source(_paris(2026, 6, 20, 9), _paris(2026, 6, 20, 10))
        b = _Source(_paris(2026, 6, 5, 9), _paris(2026, 6, 5, 10))
        occ = expand_occurrences([a, b], _paris(2026, 6, 1), _paris(2026, 6, 30))
        self.assertEqual([o["start"] for o in occ], sorted(o["start"] for o in occ))
