"""Scaffolding de la synchronisation Outlook (session du 2026-09-22, sens
unique Awtodo → Outlook). Vérifie seulement que les signaux sont bien émis
aux bons moments — le récepteur reste volontairement inerte tant que Graph
n'est pas câblé (voir `apps.planning.signals`), rien à tester côté effet."""

from django.dispatch import Signal
from django.test import TestCase

from apps.accounts.models import User
from apps.planning.services import cancel_event, create_event, update_event
from apps.planning.signals import calendar_event_cancelled, calendar_event_created, calendar_event_updated


class _SignalCatcher:
    def __init__(self, signal: Signal):
        self.signal = signal
        self.received = []
        signal.connect(self._handler, weak=False)

    def _handler(self, sender, **kwargs):
        self.received.append(kwargs)

    def disconnect(self):
        self.signal.disconnect(self._handler)


class OutlookSyncSignalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="outlook-sync-user")

    def test_create_event_emits_calendar_event_created(self):
        catcher = _SignalCatcher(calendar_event_created)
        try:
            event = create_event(
                actor=self.user,
                title="Point équipe",
                start="2026-10-01T09:00:00+02:00",
                end="2026-10-01T10:00:00+02:00",
            )
            self.assertEqual(len(catcher.received), 1)
            self.assertEqual(catcher.received[0]["event"].id, event.id)
            self.assertEqual(catcher.received[0]["actor"], self.user)
        finally:
            catcher.disconnect()

    def test_update_event_emits_calendar_event_updated(self):
        event = create_event(
            actor=self.user,
            title="Point équipe",
            start="2026-10-01T09:00:00+02:00",
            end="2026-10-01T10:00:00+02:00",
        )
        catcher = _SignalCatcher(calendar_event_updated)
        try:
            update_event(actor=self.user, event=event, title="Point équipe (déplacé)")
            self.assertEqual(len(catcher.received), 1)
            self.assertEqual(catcher.received[0]["event"].id, event.id)
        finally:
            catcher.disconnect()

    def test_cancel_event_emits_calendar_event_cancelled(self):
        event = create_event(
            actor=self.user,
            title="Point équipe",
            start="2026-10-01T09:00:00+02:00",
            end="2026-10-01T10:00:00+02:00",
        )
        catcher = _SignalCatcher(calendar_event_cancelled)
        try:
            cancel_event(actor=self.user, event=event)
            self.assertEqual(len(catcher.received), 1)
            self.assertEqual(catcher.received[0]["event"].id, event.id)
        finally:
            catcher.disconnect()

    def test_inert_receiver_does_not_raise(self):
        # Le récepteur connecté par défaut (`sync_event_to_outlook`) ne doit
        # rien casser tant qu'il est inerte — pas de credentials, pas
        # d'appel réseau.
        event = create_event(
            actor=self.user,
            title="Point équipe",
            start="2026-10-01T09:00:00+02:00",
            end="2026-10-01T10:00:00+02:00",
        )
        update_event(actor=self.user, event=event, title="Renommé")
        cancel_event(actor=self.user, event=event)
        self.assertEqual(event.outlook_event_id, "")
