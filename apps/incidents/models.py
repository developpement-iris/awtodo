from django.conf import settings
from django.db import models

from apps.common.choices import PRIORITY_CHOICES
from apps.common.models import StatusLifecycleModel, TimeStampedModel, UUIDModel


class Incident(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    STATUS_CHOICES = [
        ("signale", "Signalé"),
        ("en_cours", "En cours"),
        ("resolu", "Résolu"),
        ("archive", "Archivé"),
    ]
    ACTIVE_STATUSES = frozenset({"signale", "en_cours", "resolu"})

    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.PROTECT, related_name="incidents"
    )
    team = models.ForeignKey(
        "accounts.Team", null=True, blank=True, on_delete=models.PROTECT, related_name="incidents"
    )
    # Contrairement aux tâches, l'incident n'a jamais eu d'assigné (voir
    # docs/modeles-et-api.md > "API — endpoints Incidents" > "Différence
    # volontaire avec les tâches") — ce champ ne restreint donc aucune des
    # transitions de statut existantes, seulement le changement de priorité
    # (session du 11/08/2026), qui a besoin d'un responsable identifiable.
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assigned_incidents",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="moyenne")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="signale")
    external_reference_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"

    def __str__(self):
        return self.title


class IncidentComment(UUIDModel, TimeStampedModel):
    """Pas d'édition ni de suppression en v1 (voir CLAUDE.md) — un commentaire
    posté est permanent, cohérent avec la règle transverse "aucune suppression
    physique". Pas de StatusLifecycleModel : sans update/delete possible, il
    n'y a jamais d'état "terminal" à distinguer d'un état "actif"."""

    incident = models.ForeignKey(Incident, on_delete=models.PROTECT, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="incident_comments")
    content = models.TextField()

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Commentaire de {self.author} sur {self.incident}"
