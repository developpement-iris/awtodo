import django.dispatch
from django.db import transaction
from django.dispatch import receiver

from apps.accounts.signals import outlook_calendar_sync_enabled_activated

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

# Synchronisation Outlook des créneaux de tâche/incident (session du
# 2026-09-23) — même principe, mais un créneau se synchronise sur PLUSIEURS
# calendriers Outlook (le propriétaire + chaque personne à qui il a partagé
# son calendrier et qui a elle-même activé son opt-in), voir
# `BlockOutlookSync`. Émis par `create_block`/`update_block`/`cancel_block`.
# kwargs : block, actor
scheduled_block_created = django.dispatch.Signal()
scheduled_block_updated = django.dispatch.Signal()
scheduled_block_cancelled = django.dispatch.Signal()


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


def _enqueue_block_outlook_sync(block, action):
    def _dispatch():
        from .tasks import sync_scheduled_block_to_outlook

        sync_scheduled_block_to_outlook.delay(str(block.id), action)

    transaction.on_commit(_dispatch)


@receiver(scheduled_block_created)
def sync_block_created_to_outlook(sender, block, actor=None, **kwargs):
    _enqueue_block_outlook_sync(block, "created")


@receiver(scheduled_block_updated)
def sync_block_updated_to_outlook(sender, block, actor=None, **kwargs):
    _enqueue_block_outlook_sync(block, "updated")


@receiver(scheduled_block_cancelled)
def sync_block_cancelled_to_outlook(sender, block, actor=None, **kwargs):
    _enqueue_block_outlook_sync(block, "cancelled")


@receiver(outlook_calendar_sync_enabled_activated)
def backfill_outlook_sync_on_activation(sender, user, **kwargs):
    """Rattrape les événements déjà existants la première fois qu'un
    utilisateur active la synchro — sans ça, seuls les événements créés
    *après* l'activation apparaîtraient côté Outlook (remonté directement :
    "ça synchronise pas mes événements déjà existants ?")."""

    def _dispatch():
        from .tasks import backfill_user_outlook_sync

        backfill_user_outlook_sync.delay(str(user.id))

    transaction.on_commit(_dispatch)
