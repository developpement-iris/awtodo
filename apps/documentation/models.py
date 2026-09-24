from django.db import models

from apps.common.models import StatusLifecycleModel, TimeStampedModel, UUIDModel


class DocSpace(UUIDModel, TimeStampedModel):
    """Un espace de documentation par projet. Pas de StatusLifecycleModel :
    l'espace n'est jamais 'terminé', il suit le projet. Créé à la demande
    (get_or_create) au premier accès à l'onglet Documentation."""

    project = models.OneToOneField(
        "projects.Project", on_delete=models.PROTECT, related_name="doc_space"
    )
    is_public = models.BooleanField(default=False)
    # Token non devinable ; None tant que le lien public n'a jamais été activé.
    # Révoquer = None + is_public=False. Régénérer = nouveau token.
    public_token = models.CharField(max_length=64, null=True, blank=True, unique=True)
    # Segment lisible choisi par le chef de projet (session du 2026-09-23) —
    # purement cosmétique, mémorisé pour être réaffiché/modifié dans l'écran
    # de config. Le caractère non-devinable du lien tient tout entier au
    # suffixe aléatoire que `services._generate_token` embarque dans
    # `public_token` ; changer `custom_slug` régénère donc `public_token`
    # (même principe qu'une rotation) — voir `services.set_public_slug`.
    custom_slug = models.CharField(max_length=80, blank=True, default="")
    # Personnalisation de la page publique (session du 2026-09-23) —
    # vide = habillage Awtodo par défaut. `accent_color` : hex ou vide.
    accent_color = models.CharField(max_length=7, blank=True, default="")
    header_content = models.TextField(blank=True, default="")
    footer_content = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Documentation — {self.project.name}"


class DocPage(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    STATUS_CHOICES = [
        ("brouillon", "Brouillon"),
        ("publie", "Publié"),
        ("archive", "Archivé"),
    ]
    ACTIVE_STATUSES = frozenset({"brouillon", "publie"})

    space = models.ForeignKey(DocSpace, on_delete=models.PROTECT, related_name="pages")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)  # unique par espace (hors archivées)
    content = models.TextField(blank=True, default="")  # Markdown
    order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="brouillon")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["space", "slug"],
                condition=~models.Q(status="archive"),
                name="uniq_active_docpage_slug_per_space",
            )
        ]

    def __str__(self):
        return f"{self.space.project.name} — {self.title}"


class DocEntry(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    """Fiche structurée d'un onglet : 'fonctionnalite' (onglet Fonctionnalités)
    ou 'resolution' (onglet Résolution d'incidents). Même forme, même cycle de
    vie, un seul modèle avec un champ `kind` — pas deux modèles jumeaux."""

    STATUS_CHOICES = [
        ("brouillon", "Brouillon"),
        ("publie", "Publié"),
        ("archive", "Archivé"),
    ]
    ACTIVE_STATUSES = frozenset({"brouillon", "publie"})
    KIND_CHOICES = [
        ("fonctionnalite", "Fonctionnalité"),
        ("resolution", "Résolution d'incident"),
        # Fiche unique auto-générée (session du 2026-09-23), voir
        # `services.generate_contributors_entry` — pas de file "à documenter"
        # ni de source tâche/incident pour ce kind, régénérée à la demande.
        ("contributeurs", "Contributeurs au projet"),
    ]
    SOURCE_CHOICES = [
        ("manuelle", "Manuelle"),
        ("tache", "Tâche"),
        ("incident", "Incident"),
        ("cahier_des_charges", "Cahier des charges"),
    ]

    space = models.ForeignKey(DocSpace, on_delete=models.PROTECT, related_name="entries")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")  # Markdown
    order = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default="manuelle")
    source_task = models.ForeignKey(
        "tasks.Task", null=True, blank=True, on_delete=models.SET_NULL, related_name="doc_entries"
    )
    source_incident = models.ForeignKey(
        "incidents.Incident", null=True, blank=True, on_delete=models.SET_NULL, related_name="doc_entries"
    )
    # Rattachement à une version du projet (session du 2026-09-23, retour
    # direct : "la possibilité de faire remonter des fiches pour le
    # versionning : ajout de la V1, ajout de la V2"). Optionnel — une fiche
    # créée manuellement ou avant l'existence de versions n'en a pas.
    # Renseigné automatiquement à la version de la tâche source quand la
    # fiche vient de `create_entry_from_pending` (`task.version`).
    version = models.ForeignKey(
        "projects.ProjectVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="doc_entries"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="brouillon")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"{self.space.project.name} — [{self.kind}] {self.title}"


class PendingDocEntry(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    """File 'À documenter'. Une tâche ajout/évolution livrée -> kind=fonctionnalite ;
    un incident résolu -> kind=resolution. Statut terminal = 'traitee' ou 'ignoree'."""

    STATUS_CHOICES = [
        ("en_attente", "En attente"),
        ("traitee", "Traitée"),
        ("ignoree", "Ignorée"),
    ]
    ACTIVE_STATUSES = frozenset({"en_attente"})
    KIND_CHOICES = DocEntry.KIND_CHOICES

    space = models.ForeignKey(DocSpace, on_delete=models.PROTECT, related_name="pending_entries")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    task = models.OneToOneField(
        "tasks.Task", null=True, blank=True, on_delete=models.PROTECT, related_name="doc_pending_entry"
    )
    incident = models.OneToOneField(
        "incidents.Incident", null=True, blank=True, on_delete=models.PROTECT, related_name="doc_pending_entry"
    )
    entry = models.ForeignKey(
        DocEntry, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="en_attente")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(task__isnull=False, incident__isnull=True)
                    | models.Q(task__isnull=True, incident__isnull=False)
                ),
                name="pendingdocentry_exactly_one_source",
            )
        ]

    def __str__(self):
        src = self.task or self.incident
        return f"À documenter — {src}"
