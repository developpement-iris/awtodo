from django.dispatch import receiver

from apps.incidents.signals import incident_created


@receiver(incident_created)
def notify_channels_on_incident_created(sender, incident, actor=None, **kwargs):
    """Point d'accroche de la notification automatique « création d'incident ».

    ⚠️ Scaffolding — volontairement inerte dans cette passe (session du
    2026-09-28 : câblage réel limité à l'envoi manuel, voir
    `apps.communication.services.compose_message`). Une prochaine passe
    devra :
      1. si `incident.project_id` : lister les `CommunicationChannel` actifs
         du projet avec `notify_incident_created=True` ;
      2. créer un `CommunicationMessage(trigger="incident_cree", incident=…)`
         + une `CommunicationDelivery` par canal ;
      3. déclencher `apps.communication.tasks.send_communication_message`
         après commit, exactement comme l'envoi manuel.
    Rien de tout cela n'est fait ici pour l'instant.
    """
    return None
