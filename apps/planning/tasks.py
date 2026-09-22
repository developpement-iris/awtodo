import logging

from celery import shared_task

from apps.communication.services import get_o365_connection

from .graph_client import GraphSyncError, create_graph_event, delete_graph_event, update_graph_event
from .models import CalendarEvent

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

    Limite v1 assumée : les événements récurrents ne sont pas synchronisés
    (traduire une RRULE iCal en motif de récurrence Graph n'a pas pu être
    vérifié faute d'accès à une vraie boîte Outlook — plutôt que risquer une
    série mal traduite côté Outlook, la synchro est ignorée et journalisée).
    """
    try:
        event = CalendarEvent.all_objects.select_related("owner", "owner__organisation").get(id=event_id)
    except CalendarEvent.DoesNotExist:
        return

    owner = event.owner
    if not owner.outlook_calendar_sync_enabled:
        return
    if event.recurrence_rule:
        logger.info(
            "Synchro Outlook ignorée pour l'événement récurrent %s (v1 : événements ponctuels uniquement).",
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
