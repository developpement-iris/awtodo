import logging

from celery import shared_task

from apps.accounts.models import User
from apps.communication.services import get_o365_connection

from .graph_client import (
    GraphSyncError,
    build_graph_recurrence,
    create_graph_block_event,
    create_graph_event,
    delete_graph_event,
    update_graph_block_event,
    update_graph_event,
)
from .models import BlockOutlookSync, CalendarEvent, CalendarShare, ScheduledBlock

logger = logging.getLogger(__name__)


@shared_task
def sync_calendar_event_to_outlook(event_id, action):
    """Reflète un `CalendarEvent` Awtodo côté Outlook (sens unique, jamais
    l'inverse — voir `apps.planning.signals`). Déclenchée après commit par
    les trois signaux `calendar_event_created/updated/cancelled`.

    N'échoue jamais bruyamment : toute erreur (config Office 365 absente,
    opt-out, appel Graph en échec) est journalisée puis avalée — un incident
    de synchro Outlook ne doit jamais remonter comme une erreur de l'action
    Awtodo qui l'a déclenché (d'autant plus vrai en mode
    `CELERY_TASK_ALWAYS_EAGER`, où la tâche s'exécute encore dans le même
    processus que la requête HTTP tant qu'aucun broker Redis n'est
    provisionné).

    Événements récurrents : synchronisés si `event.recurrence_rule` entre
    dans le sous-ensemble traduit vers le motif de récurrence Graph (voir
    `apps.planning.graph_client.build_graph_recurrence` — FREQ daily/weekly/
    monthly/yearly, INTERVAL, BYDAY sur weekly, fin par UNTIL ou COUNT :
    exactement ce que produit l'éditeur front). Une RRULE plus riche passée
    directement par l'API (le backend l'accepte, l'éditeur non) est ignorée
    et journalisée plutôt que d'envoyer un motif approximatif à Outlook —
    toute la série se synchronise comme un seul événement Graph, jamais
    occurrence par occurrence (cohérent avec "l'édition ne porte jamais sur
    une occurrence isolée").
    """
    try:
        event = CalendarEvent.all_objects.select_related("owner", "owner__organisation").get(id=event_id)
    except CalendarEvent.DoesNotExist:
        return

    owner = event.owner
    if not owner.outlook_calendar_sync_enabled:
        return
    if event.recurrence_rule and build_graph_recurrence(event) is None:
        logger.info(
            "Synchro Outlook ignorée pour l'événement récurrent %s : règle de récurrence hors du "
            "sous-ensemble traduit vers Graph.",
            event_id,
        )
        return

    connection = get_o365_connection(owner.organisation)
    if not (connection.is_enabled and connection.tenant_id and connection.client_id and connection.client_secret):
        return

    upn = owner.email
    if not upn:
        return

    try:
        if action == "cancelled":
            if event.outlook_event_id:
                delete_graph_event(connection, upn, event.outlook_event_id)
                CalendarEvent.all_objects.filter(id=event.id).update(outlook_event_id="")
        elif event.outlook_event_id:
            update_graph_event(connection, upn, event.outlook_event_id, event)
        else:
            outlook_id = create_graph_event(connection, upn, event)
            CalendarEvent.all_objects.filter(id=event.id).update(outlook_event_id=outlook_id)
    except GraphSyncError:
        logger.exception("Synchronisation Outlook échouée pour l'événement %s (action=%s).", event_id, action)


@shared_task
def sync_scheduled_block_to_outlook(block_id, action):
    """Reflète un `ScheduledBlock` (créneau posé sur une tâche ou un
    incident) côté Outlook — pour le propriétaire **et** chaque personne à
    qui il a partagé son calendrier (`CalendarShare`), à condition que cette
    personne ait elle-même activé son opt-in (le partage seul ne suffit pas
    à écrire dans l'Outlook de quelqu'un d'autre — tranché avec
    l'utilisateur). Un id Graph par (créneau, destinataire), stocké dans
    `BlockOutlookSync` — contrairement à `CalendarEvent` (un seul
    destinataire possible), un créneau peut en avoir plusieurs.

    Le titre Outlook reprend celui de la tâche ou de l'incident planifié.
    Même politique d'erreurs que `sync_calendar_event_to_outlook` : chaque
    destinataire est traité indépendamment, l'échec de l'un n'empêche pas
    les autres, rien ne remonte jamais comme une erreur de l'action Awtodo
    qui a déclenché la tâche.

    Limite assumée : la liste des destinataires est recalculée à chaque
    exécution à partir des partages *actuellement* actifs — un partage
    révoqué après coup ne supprime pas rétroactivement l'événement déjà créé
    sur l'Outlook de l'ex-destinataire."""
    try:
        block = ScheduledBlock.all_objects.select_related(
            "task", "incident", "owner", "owner__organisation"
        ).get(id=block_id)
    except ScheduledBlock.DoesNotExist:
        return

    recipient_ids = {block.owner_id, *CalendarShare.objects.filter(owner_id=block.owner_id).values_list(
        "grantee_id", flat=True
    )}
    recipients = User.objects.filter(id__in=recipient_ids).select_related("organisation")
    for recipient in recipients:
        _sync_block_for_recipient(block, recipient, action)


def _sync_block_for_recipient(block, recipient, action):
    if not recipient.outlook_calendar_sync_enabled:
        return
    connection = get_o365_connection(recipient.organisation)
    if not (connection.is_enabled and connection.tenant_id and connection.client_id and connection.client_secret):
        return
    upn = recipient.email
    if not upn:
        return

    sync_row, _ = BlockOutlookSync.objects.get_or_create(block=block, user=recipient)

    try:
        if action == "cancelled":
            if sync_row.outlook_event_id:
                delete_graph_event(connection, upn, sync_row.outlook_event_id)
                BlockOutlookSync.objects.filter(id=sync_row.id).update(outlook_event_id="")
        elif sync_row.outlook_event_id:
            update_graph_block_event(connection, upn, sync_row.outlook_event_id, block)
        else:
            outlook_id = create_graph_block_event(connection, upn, block)
            BlockOutlookSync.objects.filter(id=sync_row.id).update(outlook_event_id=outlook_id)
    except GraphSyncError:
        logger.exception(
            "Synchronisation Outlook échouée pour le créneau %s → destinataire %s (action=%s).",
            block.id,
            recipient.id,
            action,
        )


@shared_task
def backfill_user_outlook_sync(user_id):
    """Rattrape ce qui existait déjà **avant** l'activation de la synchro —
    les signaux ne se redéclenchent pas tout seuls pour l'historique.
    Déclenchée une seule fois, quand `outlook_calendar_sync_enabled` bascule
    de False à True (voir `apps.accounts.services.update_planning_preferences`
    et `apps.planning.signals`), jamais à chaque sauvegarde de préférence.

    Deux volets : (1) les événements personnels actifs de l'utilisateur pas
    déjà rattachés à un id Graph ; (2) les créneaux de tâche/incident
    concernés par cette activation — les siens, **et** ceux des personnes
    qui lui ont partagé leur calendrier (un partage déjà en place avant que
    ce destinataire n'active son propre opt-in doit aussi se rattraper).
    Chaque appel réutilise la tâche unitaire correspondante, mêmes
    garde-fous, mêmes erreurs avalées."""
    events = CalendarEvent.objects.filter(owner_id=user_id, outlook_event_id="").values_list("id", flat=True)
    for event_id in events:
        sync_calendar_event_to_outlook(str(event_id), "created")

    shared_owner_ids = CalendarShare.objects.filter(grantee_id=user_id).values_list("owner_id", flat=True)
    block_ids = ScheduledBlock.objects.filter(
        owner_id__in={user_id, *shared_owner_ids}
    ).values_list("id", flat=True)
    for block_id in block_ids:
        sync_scheduled_block_to_outlook(str(block_id), "created")
