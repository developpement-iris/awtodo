import django.dispatch

# kwargs: incident (Incident), actor (User | None) — émis en fin de
# create_incident. Point d'accroche de la notification automatique
# "communication" (apps.communication) : l'envoi réel vers les canaux
# `notify_incident_created` est câblé au déploiement AWS. apps.incidents
# n'importe jamais apps.communication — lien par signal.
incident_created = django.dispatch.Signal()

# kwargs: incident (Incident), comment (IncidentComment), actor (User)
incident_commented = django.dispatch.Signal()

# kwargs: incident (Incident), actor (User) — émis quand un incident passe en
# statut "resolu" via resolve_incident. Consommé par apps.documentation
# (onglet Résolution d'incidents). apps.incidents n'importe jamais
# apps.documentation — lien par signal.
incident_resolved = django.dispatch.Signal()
