from django.conf import settings
from django.db import models

from apps.common.models import StatusLifecycleModel, TimeStampedModel, UUIDModel

# Écran Statistiques/Dashboard personnalisable (session du 2026-10-01) — les
# deux écrans "Statistiques" (par projet et global) deviennent des canevas
# vierges où chaque utilisateur compose son propre tableau de bord. Voir
# docs/modeles-et-api.md > "Statistiques/Dashboard personnalisable".


class DashboardWidget(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    """Un widget posé sur le dashboard d'un utilisateur. Toujours **propre à
    son `owner`** — jamais partagé entre plusieurs utilisateurs, contrairement
    au planning de projet/au budget (décision actée explicitement : le
    dashboard doit suivre la personne, pas le projet).

    Un seul modèle pour les deux types de widget (`widget_type`) plutôt que
    deux modèles jumeaux : la position de grille, la portée et la visibilité
    sont des attributs du widget indépendamment de son type, et deux modèles
    obligeraient une requête UNION (ou deux requêtes + tri applicatif) pour
    charger "tous les widgets d'un dashboard" en un seul appel — voir
    `apps.dashboards.services.get_dashboard`."""

    SCOPE_CHOICES = [
        ("projet", "Projet"),
        ("global", "Global"),
    ]
    WIDGET_TYPE_CHOICES = [
        ("defaut", "Par défaut"),
        ("personnalise", "Personnalisé"),
    ]
    VISIBILITY_CHOICES = [
        ("individuel", "Individuel"),
        ("groupe", "Groupe"),
    ]
    STATUS_CHOICES = [
        ("active", "Actif"),
        ("removed", "Retiré"),
    ]
    ACTIVE_STATUSES = frozenset({"active"})

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dashboard_widgets"
    )
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES)
    # Nullable seulement si scope="global" — contrainte applicative (pas de
    # contrainte DB, même doctrine que CommunicationChannel.payload_template),
    # vérifiée dans apps.dashboards.services.create_widget.
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.PROTECT, related_name="dashboard_widgets"
    )
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPE_CHOICES)
    # Rempli uniquement si widget_type="defaut" — clé du catalogue
    # apps.dashboards.catalog.DEFAULT_METRICS.
    metric_key = models.CharField(max_length=60, blank=True, default="")
    # Rempli uniquement si widget_type="personnalise" — forme validée par
    # apps.dashboards.services.validate_custom_config :
    # {"source": "tasks", "aggregation": "avg", "field": "time_spent",
    #  "group_by": "assignee"}
    config = models.JSONField(blank=True, default=dict)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default="individuel")
    # Libellé affiché — vide = le frontend retombe sur le libellé du
    # catalogue (metric_key) ou un libellé généré depuis `config`.
    title = models.CharField(max_length=150, blank=True, default="")
    # Grille libre (react-grid-layout) — unités de colonnes/lignes, pas des
    # pixels.
    x = models.PositiveIntegerField(default=0)
    y = models.PositiveIntegerField(default=0)
    w = models.PositiveIntegerField(default=4)
    h = models.PositiveIntegerField(default=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        # Gotcha StatusLifecycleModel à reproduire explicitement sur chaque
        # modèle concret (voir apps.common.models.StatusLifecycleModel) — ne
        # s'hérite pas avec plusieurs bases abstraites.
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["y", "x"]
        indexes = [models.Index(fields=["owner", "scope", "project"])]

    def __str__(self):
        return f"{self.owner} — {self.title or self.metric_key or 'widget personnalisé'}"
