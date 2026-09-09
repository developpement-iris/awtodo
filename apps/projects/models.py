from django.conf import settings
from django.db import models

from apps.accounts.models import default_organisation_id
from apps.common.choices import PRIORITY_CHOICES
from apps.common.models import StatusLifecycleModel, TimeStampedModel, UUIDModel


class Project(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    TYPE_CHOICES = [
        ("individuel", "Individuel"),
        ("collaboratif", "Collaboratif"),
    ]
    STATUS_CHOICES = [
        ("actif", "Actif"),
        ("cloture", "Clôturé"),
    ]
    ACTIVE_STATUSES = frozenset({"actif"})

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    project_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="collaboratif")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="actif")
    deadline = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, null=True, blank=True)
    team = models.ForeignKey(
        "accounts.Team", null=True, blank=True, on_delete=models.PROTECT, related_name="projects"
    )
    organisation = models.ForeignKey(
        "accounts.Organisation", on_delete=models.PROTECT, related_name="projects", default=default_organisation_id
    )

    # Bloc-notes : markdown, texte entièrement libre, aucune structure
    # imposée (voir CLAUDE.md > "Projets — Hub complet"). Pas d'historique de
    # versions — le contenu s'écrase à l'édition. Le cahier des charges, lui,
    # est structuré en sous-sections — voir `SpecSection` ci-dessous.
    notepad_content = models.TextField(blank=True, default="")
    notepad_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"

    def __str__(self):
        return self.name


class SpecSection(UUIDModel, TimeStampedModel):
    """Sous-section du "cahier des charges" d'un projet (voir CLAUDE.md >
    "Projets — Hub complet"). Liste fixe de 12 clés (choices Django, pas de
    taxonomie personnalisable par projet — cohérent avec la philosophie v1
    "choices figées plutôt que sur-ingénierie"). `is_active` = cochée dans le
    "sommaire" affiché à gauche de l'onglet ; décocher une section ne vide
    pas son `content` (l'utilisateur peut la re-cocher plus tard sans perdre
    ce qu'il avait écrit).

    Pas de `StatusLifecycleModel` ici : ce n'est pas une entité métier avec
    un cycle de vie propre (comme une tâche ou un incident), juste une
    subdivision structurelle de `Project` — une ligne par
    (project, section_key), créée à la demande (`get_or_create`) et jamais
    supprimée en pratique, cohérent avec la règle transverse "aucune
    suppression physique" sans le formalisme complet du soft-delete."""

    SECTION_CHOICES = [
        ("contexte", "Contexte"),
        ("objectifs", "Objectifs"),
        ("besoin", "Besoin"),
        ("perimetre", "Périmètre"),
        ("exigences_fonctionnelles", "Exigences fonctionnelles"),
        ("exigences_techniques", "Exigences techniques"),
        ("contraintes", "Contraintes"),
        ("livrables", "Livrables"),
        ("planning", "Planning"),
        ("budget", "Budget"),
        ("organisation", "Organisation"),
        ("annexes", "Annexes"),
    ]

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="spec_sections")
    section_key = models.CharField(max_length=40, choices=SECTION_CHOICES)
    is_active = models.BooleanField(default=False)
    content = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "section_key"], name="uniq_project_spec_section"),
        ]

    def __str__(self):
        return f"{self.project} — {self.get_section_key_display()}"


class ProjectVersion(UUIDModel, TimeStampedModel):
    """Voir docs/modeles-et-api.md > "ProjectVersion". Une seule version
    courante à la fois par projet (`is_current`) — pas de statut actif/terminal
    à gérer ici, une version n'est jamais "terminée", juste remplacée comme
    courante par la suivante. Pas de `StatusLifecycleModel` : aucune version
    n'est jamais supprimée ni archivée, cohérent avec la règle transverse."""

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="versions")
    label = models.CharField(max_length=100)
    is_current = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_project_versions",
    )

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project"],
                condition=models.Q(is_current=True),
                name="uniq_current_version_per_project",
            ),
        ]

    def __str__(self):
        return f"{self.project} — {self.label}"


class ProjectMembership(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    ROLE_CHOICES = [
        ("chef_de_projet", "Chef de projet"),
        ("membre", "Membre"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("removed", "Retirée"),
    ]
    ACTIVE_STATUSES = frozenset({"active"})

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_memberships"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "user", "role"],
                condition=models.Q(status="active"),
                name="uniq_active_project_user_role",
            ),
        ]

    def __str__(self):
        return f"{self.user} — {self.project} ({self.role})"
