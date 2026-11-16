"""Fiches d'évaluation de projet (session du 2026-11-13) — voir
docs/modeles-et-api.md > "Fiches d'évaluation de projet".

Une fiche a deux parties : la satisfaction client (lien public) et
l'évaluation chef de projet (remplie dans Awtodo). Ses questions sont une
copie figée du catalogue du groupe (ou du projet sans groupe) au moment de sa
création, plus d'éventuelles questions propres à la fiche."""

from django.conf import settings
from django.db import models

from apps.common.models import StatusLifecycleModel, TimeStampedModel, UUIDModel

SECTION_CHOICES = [("client", "Satisfaction client"), ("interne", "Évaluation chef de projet")]
SECTIONS = tuple(key for key, _ in SECTION_CHOICES)

ANSWER_TYPE_CHOICES = [
    ("note_5", "Note de 1 à 5"),
    ("nps_10", "Recommandation de 0 à 10"),
    ("oui_non", "Oui / Non"),
    ("choix_unique", "Choix unique"),
    ("choix_multiple", "Choix multiple"),
    ("texte_court", "Texte court"),
    ("texte_long", "Texte long"),
]
ANSWER_TYPES = tuple(key for key, _ in ANSWER_TYPE_CHOICES)
CONDITIONABLE_TYPES = frozenset({"oui_non", "choix_unique"})
CHOICE_TYPES = frozenset({"choix_unique", "choix_multiple"})
NUMERIC_TYPES = frozenset({"note_5", "nps_10", "oui_non"})


class QuestionDefinition(models.Model):
    """Champs communs à une question du catalogue et à sa copie dans une fiche.
    `condition_on` est déclaré dans chaque sous-classe (FK vers son propre modèle)."""

    section = models.CharField(max_length=10, choices=SECTION_CHOICES)
    label = models.CharField(max_length=300)
    help_text = models.CharField(max_length=500, blank=True, default="")
    answer_type = models.CharField(max_length=20, choices=ANSWER_TYPE_CHOICES)
    # Options d'un choix unique/multiple : liste de chaînes, vide sinon.
    options = models.JSONField(default=list, blank=True)
    required = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    # Réponses de la question `condition_on` qui affichent celle-ci ("oui"/
    # "non" ou options d'un choix unique). Vide si pas de condition.
    condition_values = models.JSONField(default=list, blank=True)

    class Meta:
        abstract = True


class CatalogQuestion(UUIDModel, TimeStampedModel, StatusLifecycleModel, QuestionDefinition):
    """Question générique d'un groupe (`team`) ou d'un projet sans groupe
    (`project`) — exactement l'un des deux, garanti par le service (même
    doctrine que `TaskType`). Copiée dans chaque nouvelle fiche."""

    STATUS_CHOICES = [("active", "Active"), ("archived", "Archivée")]
    ACTIVE_STATUSES = frozenset({"active"})

    team = models.ForeignKey(
        "accounts.Team", null=True, blank=True, on_delete=models.PROTECT, related_name="evaluation_questions"
    )
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.PROTECT, related_name="evaluation_questions"
    )
    condition_on = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="dependents"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["section", "position", "created_at"]

    def __str__(self):
        return self.label


class EvaluationSheet(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    """Fiche d'évaluation d'un projet. Cycle de vie :
    brouillon -> ouverte <-> close -> archivee (un brouillon s'archive aussi)."""

    STATUS_CHOICES = [
        ("brouillon", "Brouillon"),
        ("ouverte", "Ouverte"),
        ("close", "Close"),
        ("archivee", "Archivée"),
    ]
    ACTIVE_STATUSES = frozenset({"brouillon", "ouverte", "close"})

    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="evaluation_sheets")
    title = models.CharField(max_length=200)
    client_intro = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="brouillon")
    public_token = models.CharField(max_length=64, null=True, blank=True, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class SheetQuestion(UUIDModel, TimeStampedModel, StatusLifecycleModel, QuestionDefinition):
    """Copie figée d'une question dans une fiche. `catalog_question` renseigné
    = question générique (non modifiable, sert à agréger les stats) ; vide =
    question propre à la fiche."""

    STATUS_CHOICES = [("active", "Active"), ("archived", "Archivée")]
    ACTIVE_STATUSES = frozenset({"active"})

    sheet = models.ForeignKey(EvaluationSheet, on_delete=models.PROTECT, related_name="questions")
    catalog_question = models.ForeignKey(
        CatalogQuestion, null=True, blank=True, on_delete=models.PROTECT, related_name="sheet_copies"
    )
    condition_on = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="dependents"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["section", "position", "created_at"]

    def __str__(self):
        return self.label


class ClientResponse(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    """Une réponse reçue via le lien public. `ecartee` = retirée des
    résultats (spam, test), jamais supprimée."""

    STATUS_CHOICES = [("retenue", "Retenue"), ("ecartee", "Écartée")]
    ACTIVE_STATUSES = frozenset({"retenue"})

    sheet = models.ForeignKey(EvaluationSheet, on_delete=models.PROTECT, related_name="client_responses")
    respondent_name = models.CharField(max_length=150)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="retenue")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["-created_at"]


class InternalEvaluation(UUIDModel, TimeStampedModel):
    """Partie chef de projet : une seule par fiche, partagée par les chefs de projet."""

    sheet = models.OneToOneField(EvaluationSheet, on_delete=models.PROTECT, related_name="internal_evaluation")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")


class Answer(UUIDModel, TimeStampedModel):
    """Réponse à une question : rattachée à une réponse client **ou** à la
    partie interne. Jamais supprimée ; une réponse effacée garde `value=None`."""

    question = models.ForeignKey(SheetQuestion, on_delete=models.PROTECT, related_name="answers")
    client_response = models.ForeignKey(
        ClientResponse, null=True, blank=True, on_delete=models.PROTECT, related_name="answers"
    )
    internal_evaluation = models.ForeignKey(
        InternalEvaluation, null=True, blank=True, on_delete=models.PROTECT, related_name="answers"
    )
    value = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["client_response", "question"],
                condition=models.Q(client_response__isnull=False),
                name="unique_answer_per_client_response",
            ),
            models.UniqueConstraint(
                fields=["internal_evaluation", "question"],
                condition=models.Q(internal_evaluation__isnull=False),
                name="unique_answer_per_internal_evaluation",
            ),
        ]
