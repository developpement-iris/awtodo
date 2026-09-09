import django.dispatch

# kwargs: incident (Incident), comment (IncidentComment), actor (User)
incident_commented = django.dispatch.Signal()

# kwargs: incident (Incident), actor (User) — émis quand un incident passe en
# statut "resolu" via resolve_incident. Consommé par apps.documentation
# (onglet Résolution d'incidents). apps.incidents n'importe jamais
# apps.documentation — lien par signal.
incident_resolved = django.dispatch.Signal()
