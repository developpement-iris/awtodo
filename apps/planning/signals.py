import django.dispatch

# Émis par `apps.planning.services.add_participant` quand un utilisateur est
# invité à un événement. Consommé par `apps.notifications` (plus haut dans la
# hiérarchie de dépendances — l'inverse serait interdit).
# kwargs : event, participant, actor
event_participant_invited = django.dispatch.Signal()
