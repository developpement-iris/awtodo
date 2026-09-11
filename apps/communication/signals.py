from django.dispatch import receiver

from apps.incidents.signals import incident_created


@receiver(incident_created)
def notify_channels_on_incident_created(sender, incident, actor=None, **kwargs):
    """Point d'accroche de la notification automatique « création d'incident ».

    ⚠️ Scaffolding — volontairement inerte dans cette passe. Au déploiement
    AWS (en même temps que le SSO / la connexion Graph), ce récepteur devra :
      1. si `incident.project_id` : lister les `CommunicationChannel` actifs
         du projet avec `notify_incident_created=True` ;
      2. créer un `CommunicationMessage(trigger="incident_cree", incident=…)` ;
      3. déclencher l'envoi asynchrone (tâche Celery) vers ces canaux, plus
         un mail à `incident.author_email` s'il est renseigné.
    Rien de tout cela n'est fait ici pour l'instant.
    """
    return None
