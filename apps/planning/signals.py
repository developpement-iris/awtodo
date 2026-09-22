import django.dispatch
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


@receiver([calendar_event_created, calendar_event_updated, calendar_event_cancelled])
def sync_event_to_outlook(sender, event, actor=None, **kwargs):
    """Point d'accroche de la synchronisation Outlook (création/modification/
    suppression) — même principe que
    `apps.communication.signals.notify_channels_on_incident_created`.

    ⚠️ Scaffolding — volontairement inerte dans cette passe. Au déploiement
    AWS (en même temps que le SSO / la connexion Graph), ce récepteur devra :
      1. vérifier `event.owner.outlook_calendar_sync_enabled` et la présence
         d'une `O365Connection` active pour l'organisation ;
      2. déclencher une tâche Celery asynchrone qui appelle Microsoft Graph
         avec la permission d'application `Calendars.ReadWrite` (même
         modèle que `Mail.Send` pour `O365Connection` — permission
         d'application, pas de consentement par utilisateur à mettre en
         place) :
         - création : `POST /users/{owner.email}/events`, stocke l'id
           retourné dans `event.outlook_event_id` ;
         - modification : `PATCH /users/{owner.email}/events/{outlook_event_id}` ;
         - annulation : `DELETE /users/{owner.email}/events/{outlook_event_id}`,
           puis vide `event.outlook_event_id`.
      3. Une série récurrente se synchronise comme un seul événement Graph
         (champ `recurrence`, traduit depuis `event.recurrence_rule`) — pas
         occurrence par occurrence, cohérent avec la règle déjà actée
         ("l'édition ne porte jamais sur une occurrence isolée").
    Rien de tout cela n'est fait ici pour l'instant.
    """
    return None
