from django.conf import settings
from django.db import models

from apps.common.choices import PRIORITY_CHOICES
from apps.common.models import StatusLifecycleModel, TimeStampedModel, UUIDModel


# Types créés d'office pour tout nouveau groupe / projet sans groupe (et par
# la migration de données 0010 pour l'existant) — ce sont les 4 valeurs
# figées avant la personnalisation (session du 2026-10-09), mêmes clés pour
# rester compatibles avec les appelants API externes (QWEASE, Power Automate).
DEFAULT_TASK_TYPES = [
    ("correction", "Correction", "wrench"),
    ("ajout", "Ajout", "circle_plus"),
    ("evolution", "Évolution", "trending_up"),
    ("test", "Test", "flask"),
]


class TaskType(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    """Type de tâche personnalisable (session du 2026-10-09). Portée : un
    groupe (`team`, partagé par tous ses projets collaboratifs) **ou** un
    projet sans groupe (`project`, projet individuel) — exactement l'un des
    deux, garanti par le service (même doctrine que `Incident.project`/
    `.team`), pas par une contrainte DB.

    `Task.task_type` stocke la `key` (texte), pas une FK : l'API reste
    rétrocompatible pour les intégrations qui envoient déjà `"correction"`.
    `key` est figée à la création ; seul `label`/`icon` se renomment."""

    STATUS_CHOICES = [("active", "Actif"), ("archived", "Archivé")]
    ACTIVE_STATUSES = frozenset({"active"})
    # Liste courte, sans couleur (une couleur = un axe, voir
    # docs/charte-graphique.md) — miroir de `TASK_TYPE_ICONS` côté frontend.
    ICON_CHOICES = [
        ("wrench", "Clé"),
        ("circle_plus", "Plus"),
        ("trending_up", "Flèche montante"),
        ("flask", "Fiole"),
        ("rocket", "Fusée"),
        ("code", "Code"),
        ("lightbulb", "Ampoule"),
        ("book", "Livre"),
        ("search", "Loupe"),
        ("bug", "Bug"),
        ("file", "Document"),
        ("users", "Personnes"),
        ("shield", "Bouclier"),
        ("tag", "Étiquette"),
    ]

    team = models.ForeignKey(
        "accounts.Team", null=True, blank=True, on_delete=models.PROTECT, related_name="task_types"
    )
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.PROTECT, related_name="task_types"
    )
    key = models.CharField(max_length=50)
    label = models.CharField(max_length=50)
    icon = models.CharField(max_length=30, choices=ICON_CHOICES, default="tag")
    position = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["position", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "key"], condition=models.Q(team__isnull=False), name="unique_task_type_key_per_team"
            ),
            models.UniqueConstraint(
                fields=["project", "key"],
                condition=models.Q(project__isnull=False),
                name="unique_task_type_key_per_project",
            ),
        ]

    def __str__(self):
        return self.label


class Task(UUIDModel, TimeStampedModel, StatusLifecycleModel):
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
        ("annulee", "Annulée"),
    ]
    ACTIVE_STATUSES = frozenset({"en_attente_validation", "disponible", "assignee", "en_cours"})

    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="tasks")
    version = models.ForeignKey("projects.ProjectVersion", on_delete=models.PROTECT, related_name="tasks")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    # Clé d'un `TaskType` de la portée du projet (groupe, sinon projet) —
    # validée par le service, plus de `choices` figées (session du 2026-10-09).
    task_type = models.CharField(max_length=50)
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
    # Distinct de `rejection_reason` (refus avant même de démarrer, réservé à
    # `en_attente_validation`) : une annulation abandonne une tâche déjà
    # validée (disponible/assignée/en cours), jamais confondue avec une
    # clôture réussie (`archivee`, voir `complete_task`).
    cancellation_reason = models.TextField(null=True, blank=True)

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
