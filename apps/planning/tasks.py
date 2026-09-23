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
from .models import CalendarEvent, EventParticipant, EventParticipantOutlookSync, ScheduledBlock

logger = logging.getLogger(__name__)


def _get_ready_connection(organisation):
    """`O365Connection` utilisable (activée, identifiants renseignés), ou
    `None` — factorise la même vérification répétée par chaque tâche."""
    connection = get_o365_connection(organisation)
    if connection.is_enabled and connection.tenant_id and connection.client_id and connection.client_secret:
        return connection
    return None


@shared_task
def sync_calendar_event_to_outlook(event_id, action):
    """Reflète la copie **de l'organisateur** d'un `CalendarEvent` Awtodo
    côté Outlook (sens unique, jamais l'inverse — voir
    `apps.planning.signals`). Déclenchée après commit par les trois signaux
    `calendar_event_created/updated/cancelled`. Les copies des participants
    invités sont gérées séparément, voir `sync_event_participant_to_outlook`
    / `sync_event_to_all_participants_outlook`.

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

    connection = _get_ready_connection(owner.organisation)
    if connection is None:
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
def sync_event_participant_to_outlook(event_id, user_id, action):
    """Reflète la copie **d'un participant invité** à un `CalendarEvent`
    (session du 2026-09-23 — partager un événement précis synchronise ce
    seul événement sur l'Outlook du destinataire, à distinguer du partage
    de calendrier `CalendarShare`, qui ne synchronise jamais rien). Un id
    Graph par (événement, participant), stocké dans
    `EventParticipantOutlookSync` — distinct de `CalendarEvent.outlook_event_id`
    (qui ne couvre que l'organisateur).

    Soumise au même opt-in individuel que toute autre synchro : être invité
    à un événement ne contourne pas le contrôle personnel de chacun sur ce
    qui atterrit dans son propre Outlook. N'échoue jamais bruyamment (voir
    `sync_calendar_event_to_outlook`)."""
    try:
        event = CalendarEvent.all_objects.select_related("owner").get(id=event_id)
    except CalendarEvent.DoesNotExist:
        return
    try:
        recipient = User.objects.select_related("organisation").get(id=user_id)
    except User.DoesNotExist:
        return

    if not recipient.outlook_calendar_sync_enabled:
        return
    if event.recurrence_rule and build_graph_recurrence(event) is None:
        return

    connection = _get_ready_connection(recipient.organisation)
    if connection is None:
        return

    upn = recipient.email
    if not upn:
        return

    sync_row, _ = EventParticipantOutlookSync.objects.get_or_create(event=event, user=recipient)

    try:
        if action == "cancelled":
            if sync_row.outlook_event_id:
                delete_graph_event(connection, upn, sync_row.outlook_event_id)
                EventParticipantOutlookSync.objects.filter(id=sync_row.id).update(outlook_event_id="")
        elif sync_row.outlook_event_id:
            update_graph_event(connection, upn, sync_row.outlook_event_id, event)
        else:
            outlook_id = create_graph_event(connection, upn, event)
            EventParticipantOutlookSync.objects.filter(id=sync_row.id).update(outlook_event_id=outlook_id)
    except GraphSyncError:
        logger.exception(
            "Synchronisation Outlook échouée pour l'événement %s → participant %s (action=%s).",
            event_id,
            user_id,
            action,
        )


@shared_task
def sync_event_to_all_participants_outlook(event_id, action):
    """Fait suivre un changement de contenu (renommage, déplacement,
    annulation) de l'organisateur vers la copie Outlook de chaque
    participant **actif** — le jeu de participants ne change pas ici (voir
    `sync_event_participant_to_outlook` pour l'ajout/retrait d'une personne
    précise). Chaque participant est traité indépendamment : l'échec de
    l'un n'empêche pas la synchro des autres."""
    participant_ids = EventParticipant.objects.filter(event_id=event_id).values_list("user_id", flat=True)
    for user_id in participant_ids:
        sync_event_participant_to_outlook(event_id, str(user_id), action)


@shared_task
def sync_scheduled_block_to_outlook(block_id, action):
    """Reflète un `ScheduledBlock` (créneau posé sur une tâche ou un
    incident assigné) côté Outlook. Un seul destinataire possible : son
    `owner` — une tâche/un incident n'a qu'un assigné, pas de mécanisme de
    partage comme pour les événements libres (tranché explicitement avec
    l'utilisateur : "pas de partage pour les tâches planifiées comme pour
    les évènements"). Même structure que `sync_calendar_event_to_outlook`.

    Le titre Outlook reprend celui de la tâche ou de l'incident planifié.
    N'échoue jamais bruyamment (voir `sync_calendar_event_to_outlook`)."""
    try:
        block = ScheduledBlock.all_objects.select_related("task", "incident", "owner", "owner__organisation").get(
            id=block_id
        )
    except ScheduledBlock.DoesNotExist:
        return

    owner = block.owner
    if not owner.outlook_calendar_sync_enabled:
        return

    connection = _get_ready_connection(owner.organisation)
    if connection is None:
        return

    upn = owner.email
    if not upn:
        return

    try:
        if action == "cancelled":
            if block.outlook_event_id:
                delete_graph_event(connection, upn, block.outlook_event_id)
                ScheduledBlock.all_objects.filter(id=block.id).update(outlook_event_id="")
        elif block.outlook_event_id:
            update_graph_block_event(connection, upn, block.outlook_event_id, block)
        else:
            outlook_id = create_graph_block_event(connection, upn, block)
            ScheduledBlock.all_objects.filter(id=block.id).update(outlook_event_id=outlook_id)
    except GraphSyncError:
        logger.exception("Synchronisation Outlook échouée pour le créneau %s (action=%s).", block_id, action)


@shared_task
def backfill_user_outlook_sync(user_id):
    """Rattrape ce qui existait déjà **avant** l'activation de la synchro —
    les signaux ne se redéclenchent pas tout seuls pour l'historique.
    Déclenchée une seule fois, quand `outlook_calendar_sync_enabled` bascule
    de False à True (voir `apps.accounts.services.update_planning_preferences`
    et `apps.planning.signals`), jamais à chaque sauvegarde de préférence.

    Trois volets : (1) les événements personnels de l'utilisateur (sa
    propre copie, + fan-out vers les participants déjà invités le cas
    échéant) ; (2) les événements auxquels il est déjà invité en tant que
    participant (sa propre copie côté participant) ; (3) ses créneaux de
    tâche/incident. Chaque appel réutilise la tâche unitaire correspondante,
    mêmes garde-fous, mêmes erreurs avalées."""
    own_event_ids = CalendarEvent.objects.filter(owner_id=user_id, outlook_event_id="").values_list(
        "id", flat=True
    )
    for event_id in own_event_ids:
        sync_calendar_event_to_outlook(str(event_id), "created")
        sync_event_to_all_participants_outlook(str(event_id), "created")

    invited_event_ids = EventParticipant.objects.filter(user_id=user_id).values_list("event_id", flat=True)
    for event_id in invited_event_ids:
        sync_event_participant_to_outlook(str(event_id), str(user_id), "created")

    block_ids = ScheduledBlock.objects.filter(owner_id=user_id, outlook_event_id="").values_list("id", flat=True)
    for block_id in block_ids:
        sync_scheduled_block_to_outlook(str(block_id), "created")
