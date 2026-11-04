"""Superposition des rendez-vous Outlook en lecture seule (session du
2026-11-03) — sens Outlook → Awtodo, affichage seulement, rien n'est stocké.
Les appels Microsoft Graph sont mockés."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase
from django.utils.dateparse import parse_datetime
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.communication.models import O365Connection
from apps.planning.graph_client import GraphSyncError, list_graph_busy_slots
from apps.planning.models import CalendarEvent
from apps.planning.services import get_calendar

FROM = "2026-11-02T00:00:00+01:00"
TO = "2026-11-09T00:00:00+01:00"


def _graph_item(item_id, subject="Réunion", start="2026-11-03T08:00:00.0000000", end="2026-11-03T09:00:00.0000000", **extra):
    return {
        "id": item_id,
        "seriesMasterId": extra.pop("seriesMasterId", None),
        "subject": subject,
        "start": {"dateTime": start, "timeZone": "UTC"},
        "end": {"dateTime": end, "timeZone": "UTC"},
        "isAllDay": extra.pop("isAllDay", False),
        "showAs": extra.pop("showAs", "busy"),
        "isCancelled": extra.pop("isCancelled", False),
    }


def _response(payload, status=200):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload
    response.text = ""
    return response


class ListGraphBusySlotsTests(TestCase):
    def setUp(self):
        self.connection = O365Connection(tenant_id="t", client_id="c", client_secret="s")

    @patch("apps.planning.graph_client._headers", return_value={})
    @patch("apps.planning.graph_client.requests.get")
    def test_follows_pagination_and_skips_free_and_cancelled(self, mock_get, _headers):
        mock_get.side_effect = [
            _response({"value": [_graph_item("a"), _graph_item("free", showAs="free")], "@odata.nextLink": "next"}),
            _response({"value": [_graph_item("b"), _graph_item("gone", isCancelled=True)]}),
        ]
        items = list_graph_busy_slots(
            self.connection, "u@x.com", parse_datetime(FROM), parse_datetime(TO)
        )
        self.assertEqual([i["id"] for i in items], ["a", "b"])
        self.assertEqual(items[0]["start"], datetime.fromisoformat("2026-11-03T08:00:00+00:00"))
        self.assertEqual(mock_get.call_args_list[1].args[0], "next")

    @patch("apps.planning.graph_client._headers", return_value={})
    @patch("apps.planning.graph_client.requests.get")
    def test_raises_on_graph_error(self, mock_get, _headers):
        mock_get.return_value = _response({}, status=403)
        with self.assertRaises(GraphSyncError):
            list_graph_busy_slots(self.connection, "u@x.com", parse_datetime(FROM), parse_datetime(TO))


class OutlookBusyOverlayTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="busy-user", email="busy-user@reparstores.com")
        self.start = parse_datetime(FROM)
        self.end = parse_datetime(TO)

    def _enable(self):
        self.user.outlook_calendar_sync_enabled = True
        self.user.save(update_fields=["outlook_calendar_sync_enabled"])
        O365Connection.objects.create(
            organisation=self.user.organisation,
            tenant_id="t",
            client_id="c",
            client_secret="s",
            is_enabled=True,
        )

    def _calendar(self, **kwargs):
        return get_calendar(actor=self.user, window_start=self.start, window_end=self.end, **kwargs)

    def _slot(self, item_id, series=None):
        return {
            "id": item_id,
            "series_master_id": series,
            "title": "RDV",
            "start": datetime.fromisoformat("2026-11-03T08:00:00+00:00"),
            "end": datetime.fromisoformat("2026-11-03T09:00:00+00:00"),
            "all_day": False,
        }

    @patch("apps.planning.services.list_graph_busy_slots")
    def test_not_included_unless_requested(self, mock_list):
        self._enable()
        self.assertNotIn("outlook", self._calendar())
        mock_list.assert_not_called()

    @patch("apps.planning.services.list_graph_busy_slots")
    def test_disabled_without_opt_in(self, mock_list):
        data = self._calendar(include_outlook=True)
        self.assertEqual(data["outlook"], {"status": "disabled", "items": []})
        mock_list.assert_not_called()

    @patch("apps.planning.services.list_graph_busy_slots")
    def test_returns_slots_and_excludes_awtodo_copies(self, mock_list):
        self._enable()
        CalendarEvent.objects.filter(id=self._make_event().id).update(outlook_event_id="awtodo-event")
        mock_list.return_value = [
            self._slot("external"),
            self._slot("awtodo-event"),
            self._slot("instance-1", series="awtodo-event"),
        ]
        data = self._calendar(include_outlook=True)
        self.assertEqual(data["outlook"]["status"], "ok")
        self.assertEqual([i["id"] for i in data["outlook"]["items"]], ["external"])
        self.assertEqual(data["outlook"]["items"][0]["title"], "RDV")

    @patch("apps.planning.services.list_graph_busy_slots")
    def test_result_is_cached(self, mock_list):
        self._enable()
        mock_list.return_value = [self._slot("external")]
        self._calendar(include_outlook=True)
        self._calendar(include_outlook=True)
        self.assertEqual(mock_list.call_count, 1)

    @patch("apps.planning.services.list_graph_busy_slots")
    def test_graph_error_does_not_break_calendar(self, mock_list):
        self._enable()
        mock_list.side_effect = GraphSyncError("boom")
        data = self._calendar(include_outlook=True)
        self.assertEqual(data["outlook"], {"status": "error", "items": []})
        self.assertIn("events", data)

    def _make_event(self):
        from apps.planning.services import create_event

        with patch("apps.planning.tasks.create_graph_event", return_value=""):
            return create_event(
                actor=self.user,
                title="Point Awtodo",
                start="2026-11-03T09:00:00+01:00",
                end="2026-11-03T10:00:00+01:00",
            )


class OutlookBusyApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="busy-api", email="busy-api@reparstores.com")
        self.client.force_authenticate(self.user)

    def test_outlook_query_param_adds_layer(self):
        r = self.client.get("/api/v1/planning/calendar/", {"from": FROM, "to": TO, "outlook": "1"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["outlook"]["status"], "disabled")

    def test_layer_absent_by_default(self):
        r = self.client.get("/api/v1/planning/calendar/", {"from": FROM, "to": TO})
        self.assertNotIn("outlook", r.data)
