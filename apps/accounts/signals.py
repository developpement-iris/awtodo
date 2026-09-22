import django.dispatch

# Émis par `update_planning_preferences` quand `outlook_calendar_sync_enabled`
# bascule de False à True (session du 2026-09-22, suite Outlook — backfill
# des événements déjà existants). Consommé par `apps.planning.signals` (plus
# haut dans la hiérarchie de dépendances — l'inverse serait interdit).
# kwargs : user
outlook_calendar_sync_enabled_activated = django.dispatch.Signal()
