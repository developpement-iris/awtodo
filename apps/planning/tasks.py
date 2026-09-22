import logging

from celery import shared_task

from apps.communication.services import get_o365_connection

from .graph_client import GraphSyncError, build_graph_recurrence, create_graph_event, delete_graph_event, update_graph_event
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
def backfill_user_outlook_sync(user_id):
    """Rattrape les événements créés **avant** l'activation de la synchro —
    les signaux `calendar_event_*` ne se redéclenchent pas tout seuls pour
    l'historique. Déclenchée une seule fois, quand `outlook_calendar_sync_enabled`
    bascule de False à True (voir `apps.accounts.services.update_planning_preferences`
    et `apps.planning.signals`), jamais à chaque sauvegarde de préférence.

    Ne synchronise que les événements actifs (`status="confirme"`) pas déjà
    rattachés à un id Graph — appelle simplement la tâche de synchro unitaire
    pour chacun, en `created` (mêmes garde-fous, mêmes erreurs avalées, y
    compris le tri récurrence traduisible/non traduisible)."""
    events = CalendarEvent.objects.filter(owner_id=user_id, outlook_event_id="").values_list("id", flat=True)
    for event_id in events:
        sync_calendar_event_to_outlook(str(event_id), "created")
