from django.contrib import admin

from .models import BlockOutlookSync, CalendarEvent


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    # Vue de dépannage pour la synchro Outlook (session du 2026-09-22) :
    # `outlook_event_id` renseigné = la tâche Celery a bien créé l'événement
    # côté Graph ; vide + owner opt-in = soit pas encore passé (peu probable
    # en mode CELERY_TASK_ALWAYS_EAGER), soit échoué (voir logs serveur,
    # `apps.planning.tasks` journalise toute `GraphSyncError`).
    list_display = ("title", "owner", "start", "status", "outlook_event_id")
    list_filter = ("status",)
    search_fields = ("title", "owner__username", "owner__email")


@admin.register(BlockOutlookSync)
class BlockOutlookSyncAdmin(admin.ModelAdmin):
    # Même vue de dépannage, mais par (créneau, destinataire) — session du
    # 2026-09-23 : un créneau partagé a une ligne par personne qui doit le
    # recevoir sur son Outlook.
    list_display = ("block", "user", "outlook_event_id", "updated_at")
    search_fields = ("user__username", "user__email")
