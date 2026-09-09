from django.conf import settings
from django.db import models

from apps.common.choices import PRIORITY_CHOICES
from apps.common.models import StatusLifecycleModel, TimeStampedModel, UUIDModel


class Task(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    TASK_TYPE_CHOICES = [
        ("correction", "Correction"),
        ("ajout", "Ajout"),
        ("evolution", "Évolution"),
    ]
    ORIGIN_CHOICES = [
        ("manuelle", "Manuelle"),
        ("api", "API"),
    ]
    STATUS_CHOICES = [
        ("en_attente_validation", "En attente de validation"),
        ("disponible", "Disponible"),
        ("assignee", "Assignée"),
        ("en_cours", "En cours"),
        ("rejetee", "Rejetée"),
        ("archivee", "Archivée"),
    ]
    ACTIVE_STATUSES = frozenset({"en_attente_validation", "disponible", "assignee", "en_cours"})

    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="tasks")
    version = models.ForeignKey("projects.ProjectVersion", on_delete=models.PROTECT, related_name="tasks")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    task_type = models.CharField(max_length=20, choices=TASK_TYPE_CHOICES)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="moyenne")
    deadline = models.DateField(null=True, blank=True)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tasks",
    )
    time_spent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    # Temps théorique/estimé, renseignable dès la création ou modifiable
    # ensuite par tout membre du projet (même garde que le titre/la
    # description, voir `_ensure_can_rename`) — distinct de `time_spent`
    # (temps réel, capturé uniquement à la clôture).
    estimated_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    origin = models.CharField(max_length=20, choices=ORIGIN_CHOICES, default="manuelle")
    external_reference_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="en_attente_validation")
    rejection_reason = models.TextField(null=True, blank=True)

    class Meta:
        # Explicite plutôt qu'hérité de StatusLifecycleModel.Meta : avec
        # plusieurs bases abstraites, Django n'hérite que du Meta de la
        # première base qui en déclare un (ici UUIDModel, qui n'a que
        # `abstract=True`) — le Meta des bases suivantes est ignoré.
        # `default_manager_name` : utilisé par les relations inverses
        # (`project.tasks.all()`) — sans ça, elles passent silencieusement par
        # `objects` (filtré) et masquent les tâches archivées/rejetées.
        # `base_manager_name` : utilisé par le collecteur de suppression en
        # cascade (ex. `on_delete=PROTECT`), pour voir aussi les lignes
        # historiques lors de l'évaluation des contraintes.
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"

    def __str__(self):
        return self.title


class TaskComment(UUIDModel, TimeStampedModel):
    """Pas d'édition ni de suppression en v1 — un commentaire posté est
    permanent, cohérent avec la règle transverse "aucune suppression
    physique". Pas de StatusLifecycleModel : sans update/delete possible,
    il n'y a jamais d'état "terminal" à distinguer d'un état "actif" — même
    raisonnement que `apps.incidents.models.IncidentComment`."""

    task = models.ForeignKey(Task, on_delete=models.PROTECT, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="task_comments")
    content = models.TextField()

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Commentaire de {self.author} sur {self.task}"
