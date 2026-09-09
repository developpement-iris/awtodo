from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel, UUIDModel
from apps.incidents.models import Incident
from apps.tasks.models import Task


class Notification(UUIDModel, TimeStampedModel):
    """`apps.notifications` est en tête de la hiérarchie de dépendances du
    projet (voir CLAUDE.md > "Structure du projet") — importer `Task`/
    `Incident` ici est autorisé dans ce sens précis, jamais l'inverse. FK
    directes plutôt qu'une relation générique (contrairement à
    `apps.common.models.AuditLogEntry`) : il n'existe que deux cibles
    possibles pour une notification, une relation générique n'apporterait
    rien ici."""

    VERB_CHOICES = [
        ("task_assigned", "Tâche assignée"),
        ("task_commented", "Commentaire sur une tâche"),
        ("incident_commented", "Commentaire sur un incident"),
        ("event_invited", "Invitation à un événement"),
    ]

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    verb = models.CharField(max_length=30, choices=VERB_CHOICES)
    message = models.CharField(max_length=255)
    task = models.ForeignKey(Task, null=True, blank=True, on_delete=models.PROTECT, related_name="notifications")
    incident = models.ForeignKey(
        Incident, null=True, blank=True, on_delete=models.PROTECT, related_name="notifications"
    )
    event = models.ForeignKey(
        "planning.CalendarEvent", null=True, blank=True, on_delete=models.PROTECT, related_name="notifications"
    )
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.verb} → {self.recipient}"
