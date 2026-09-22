import django.dispatch
from django.db import transaction
from django.dispatch import receiver

# Émis par `apps.planning.services.add_participant` quand un utilisateur est
# invité à un événement. Consommé par `apps.notifications` (plus haut dans la
# hiérarchie de dépendances — l'inverse serait interdit).
# kwargs : event, participant, actor
event_participant_invited = django.dispatch.Signal()

# Synchronisation Outlook (session du 2026-09-22, sens unique Awtodo →
# Outlook uniquement — jamais l'inverse, tranché avec l'utilisateur). Émis
# par `create_event`/`update_event`/`cancel_event`. kwargs : event, actor
calendar_event_created = django.dispatch.Signal()
calendar_event_updated = django.dispatch.Signal()
calendar_event_cancelled = django.dispatch.Signal()


def _enqueue_outlook_sync(event, action):
    """Planifie la tâche Celery après le commit de la transaction en cours —
    évite de lire l'événement avant qu'il soit réellement visible en base
    (important dès qu'un vrai worker/broker sera en jeu ; sans effet en mode
    `CELERY_TASK_ALWAYS_EAGER` puisqu'on est déjà dans la même transaction,
    mais garde le code correct pour la bascule future)."""

    def _dispatch():
        from .tasks import sync_calendar_event_to_outlook

        sync_calendar_event_to_outlook.delay(str(event.id), action)

    transaction.on_commit(_dispatch)


# Un récepteur par signal plutôt qu'un seul partagé (comme avant le câblage
# réel) : chaque signal correspond à une action Graph différente
# (POST/PATCH/DELETE), il faut la connaître pour construire la tâche.
@receiver(calendar_event_created)
def sync_event_created_to_outlook(sender, event, actor=None, **kwargs):
    _enqueue_outlook_sync(event, "created")


@receiver(calendar_event_updated)
def sync_event_updated_to_outlook(sender, event, actor=None, **kwargs):
    _enqueue_outlook_sync(event, "updated")


@receiver(calendar_event_cancelled)
def sync_event_cancelled_to_outlook(sender, event, actor=None, **kwargs):
    _enqueue_outlook_sync(event, "cancelled")
