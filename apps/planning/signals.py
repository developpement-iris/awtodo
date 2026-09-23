import django.dispatch
from django.db import transaction
from django.dispatch import receiver

from apps.accounts.signals import outlook_calendar_sync_enabled_activated

# Émis par `apps.planning.services.add_participant`/`remove_participant`
# quand un utilisateur est invité/retiré d'un événement. Consommés par
# `apps.notifications` (plus haut dans la hiérarchie de dépendances —
# l'inverse serait interdit) et, pour l'invitation, par la synchro Outlook
# ci-dessous. kwargs : event, participant, actor
event_participant_invited = django.dispatch.Signal()
event_participant_removed = django.dispatch.Signal()

# Synchronisation Outlook (session du 2026-09-22, sens unique Awtodo →
# Outlook uniquement — jamais l'inverse, tranché avec l'utilisateur). Émis
# par `create_event`/`update_event`/`cancel_event`. kwargs : event, actor
calendar_event_created = django.dispatch.Signal()
calendar_event_updated = django.dispatch.Signal()
calendar_event_cancelled = django.dispatch.Signal()

# Occurrence unique d'une série modifiée/annulée (session du 2026-09-23,
# RECURRENCE-ID — voir `CalendarEventOccurrenceOverride`). Émis par
# `update_event_occurrence`/`cancel_event_occurrence`.
# kwargs : event, override, actor
calendar_event_occurrence_updated = django.dispatch.Signal()
calendar_event_occurrence_cancelled = django.dispatch.Signal()

# Synchronisation Outlook des créneaux de tâche/incident (session du
# 2026-09-23). Un créneau n'a jamais qu'un seul destinataire (son
# propriétaire) — pas de partage possible pour une tâche/un incident,
# contrairement à un événement libre (tranché explicitement avec
# l'utilisateur : "pas de partage pour les tâches planifiées comme pour les
# évènements"). Émis par `create_block`/`update_block`/`cancel_block`.
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


def _enqueue_participants_outlook_sync(event, action):
    """Fait suivre le contenu (renommage, déplacement, annulation) de
    l'événement vers la copie Outlook de **chaque participant actif déjà
    invité** — le jeu de destinataires ne change pas ici, seulement le
    contenu. Voir `_enqueue_participant_outlook_sync` pour l'ajout/retrait
    d'un participant précis."""

    def _dispatch():
        from .tasks import sync_event_to_all_participants_outlook

        sync_event_to_all_participants_outlook.delay(str(event.id), action)

    transaction.on_commit(_dispatch)


def _enqueue_participant_outlook_sync(event, participant, action):
    def _dispatch():
        from .tasks import sync_event_participant_to_outlook

        sync_event_participant_to_outlook.delay(str(event.id), str(participant.user_id), action)

    transaction.on_commit(_dispatch)


# Un récepteur par signal plutôt qu'un seul partagé (comme avant le câblage
# réel) : chaque signal correspond à une action Graph différente
# (POST/PATCH/DELETE), il faut la connaître pour construire la tâche.
# Chaque signal déclenche à la fois la synchro de la copie de l'organisateur
# et celle des copies déjà distribuées aux participants actifs.
@receiver(calendar_event_created)
def sync_event_created_to_outlook(sender, event, actor=None, **kwargs):
    _enqueue_outlook_sync(event, "created")
    _enqueue_participants_outlook_sync(event, "created")


@receiver(calendar_event_updated)
def sync_event_updated_to_outlook(sender, event, actor=None, **kwargs):
    _enqueue_outlook_sync(event, "updated")
    _enqueue_participants_outlook_sync(event, "updated")


@receiver(calendar_event_cancelled)
def sync_event_cancelled_to_outlook(sender, event, actor=None, **kwargs):
    _enqueue_outlook_sync(event, "cancelled")
    _enqueue_participants_outlook_sync(event, "cancelled")


@receiver(event_participant_invited)
def sync_new_participant_to_outlook(sender, event, participant, actor=None, **kwargs):
    _enqueue_participant_outlook_sync(event, participant, "created")


@receiver(event_participant_removed)
def sync_removed_participant_to_outlook(sender, event, participant, actor=None, **kwargs):
    # Retiré de l'événement Awtodo → sa copie Outlook personnelle est
    # supprimée (pas l'événement des autres participants/de l'organisateur).
    _enqueue_participant_outlook_sync(event, participant, "cancelled")


def _enqueue_occurrence_outlook_sync(override, action):
    def _dispatch():
        from .tasks import sync_event_occurrence_to_all_participants_outlook, sync_event_occurrence_to_outlook

        sync_event_occurrence_to_outlook.delay(str(override.id), action)
        sync_event_occurrence_to_all_participants_outlook.delay(str(override.id), action)

    transaction.on_commit(_dispatch)


@receiver(calendar_event_occurrence_updated)
def sync_occurrence_updated_to_outlook(sender, event, override, actor=None, **kwargs):
    _enqueue_occurrence_outlook_sync(override, "updated")


@receiver(calendar_event_occurrence_cancelled)
def sync_occurrence_cancelled_to_outlook(sender, event, override, actor=None, **kwargs):
    _enqueue_occurrence_outlook_sync(override, "cancelled")


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
    """Rattrape ce qui existait déjà la première fois qu'un utilisateur
    active la synchro — sans ça, seuls les événements/créneaux créés
    *après* l'activation apparaîtraient côté Outlook (remonté directement :
    "ça synchronise pas mes événements déjà existants ?")."""

    def _dispatch():
        from .tasks import backfill_user_outlook_sync

        backfill_user_outlook_sync.delay(str(user.id))

    transaction.on_commit(_dispatch)
