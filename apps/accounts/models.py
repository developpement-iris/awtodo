import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.utils import OperationalError, ProgrammingError

from apps.common.models import StatusLifecycleModel, TimeStampedModel, UUIDModel


class Organisation(UUIDModel, TimeStampedModel):
    """Racine de la hiérarchie à 4 niveaux (voir CLAUDE.md > "Organisation") :
    plateforme (User.is_platform_admin) > organisation (User.organisation_role)
    > projet (ProjectMembership.role) > groupe (Team.created_by). Pas de
    StatusLifecycleModel ici : aucun flux d'archivage/suppression d'organisation
    n'est exposé dans cette passe — à ajouter si ce besoin apparaît."""

    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


def default_organisation_id():
    """Awtodo reste, en usage réel, un outil à une seule organisation (voir
    CLAUDE.md > "Organisation") — il n'en existe donc concrètement qu'une
    seule à tout instant tant que le chantier multi-organisations n'est pas
    allé plus loin. Sert de valeur par défaut pratique à `organisation` sur
    `User`/`Team`/`Project` (évite d'imposer ce kwarg à chaque appel/test
    existant) sans affaiblir la contrainte NOT NULL en base — un appelant qui
    veut une organisation précise (ex. création d'une nouvelle organisation,
    chantier 3.4) la passe explicitement et prime sur ce défaut.

    Le try/except couvre le cas où ce défaut est évalué alors que la table
    n'existe pas encore : `manage.py migrate`/`collectstatic` lancent les
    system checks Django (`check_user_model` instancie `User()`, ce qui
    évalue ce défaut) *avant* que les migrations n'aient créé la table — ce
    qui arrive sur une base neuve au premier déploiement."""
    try:
        return Organisation.objects.order_by("created_at").values_list("id", flat=True).first()
    except (OperationalError, ProgrammingError):
        return None


ORGANISATION_ROLE_CHOICES = [
    ("admin", "Administrateur"),
    ("chef_de_projet", "Chef de projet"),
    ("membre", "Membre"),
]


class Team(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    STATUS_CHOICES = [
        ("actif", "Actif"),
        ("archive", "Archivé"),
    ]
    ACTIVE_STATUSES = frozenset({"actif"})

    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="actif")
    organisation = models.ForeignKey(
        Organisation, on_delete=models.PROTECT, related_name="teams", default=default_organisation_id
    )
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="created_teams", null=True, blank=True
    )
    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"

    def __str__(self):
        return self.name


class TeamMembership(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    """Remplace `Team.members` (many-to-many brut) — cohérent avec la règle
    transverse "aucune suppression physique" (voir CLAUDE.md) : retirer un
    membre passe `status` à `removed`, jamais un DELETE. Même pattern que
    `apps.projects.models.ProjectMembership`."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("removed", "Retirée"),
    ]
    ACTIVE_STATUSES = frozenset({"active"})

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="team_memberships")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        constraints = [
            models.UniqueConstraint(
                fields=["team", "user"],
                condition=models.Q(status="active"),
                name="uniq_active_team_user",
            ),
        ]

    def __str__(self):
        return f"{self.user} — {self.team}"


ACCOUNT_TYPE_CHOICES = [
    ("interne", "Interne"),
    ("externe", "Externe"),
]

ACCOUNT_STATUS_CHOICES = [
    ("pending", "En attente"),
    ("active", "Actif"),
]


class User(UUIDModel, AbstractUser):
    azure_oid = models.CharField(max_length=64, unique=True, null=True, blank=True)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.PROTECT, related_name="users", default=default_organisation_id
    )
    organisation_role = models.CharField(max_length=20, choices=ORGANISATION_ROLE_CHOICES, default="membre")
    is_platform_admin = models.BooleanField(default=False)
    # Compte technique (préfigure le futur compte de service ticketing, voir
    # CLAUDE.md > "Stack technique" > Auth — pas encore de clé API dédiée).
    # `apps.incidents.views.IncidentViewSet.create` traite un tel utilisateur
    # comme `actor=None` (appel système), qui contourne la contrainte de
    # groupe/projet dans `create_incident` — jamais utilisé pour autre chose.
    is_service_account = models.BooleanField(default=False)
    # `interne`/`active` par défaut : couvre tous les chemins de création
    # existants (seed, tests, admin de nouvelle organisation — chantier
    # 3.4 — qui n'a jamais de flux d'invitation). Seul le flux d'invitation
    # (voir `create_invitation` ci-dessous) crée explicitement un compte
    # `pending`, et éventuellement `externe`.
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, default="interne")
    account_status = models.CharField(max_length=20, choices=ACCOUNT_STATUS_CHOICES, default="active")

    def __str__(self):
        return self.get_username()


class Invitation(UUIDModel, TimeStampedModel):
    """Voir CLAUDE.md > "Comptes et invitations". `project` référence
    `apps.projects.Project` via une chaîne ("projects.Project") plutôt qu'un
    import direct : `apps.accounts` ne doit jamais importer `apps.projects`
    (accounts est plus bas dans la hiérarchie de dépendances, voir CLAUDE.md
    > "Structure du projet"). Une FK par chaîne est une référence de schéma
    résolue paresseusement par Django, pas un import Python — elle ne viole
    donc pas la règle, qui porte sur le couplage de code (services/logique
    métier), pas sur le schéma de données. Pas de StatusLifecycleModel : le
    cycle `pending → accepted/revoked/expired` est un vrai cycle de vie
    métier avec ses propres règles de transition (voir services.py), pas un
    simple actif/archivé — un statut CharField suffit, pas besoin du pattern
    manager actif/historique pour un objet qui n'est jamais listé "par défaut
    sans les terminaux" nulle part dans l'UI actuelle."""

    STATUS_CHOICES = [
        ("pending", "En attente"),
        ("accepted", "Acceptée"),
        ("revoked", "Révoquée"),
        ("expired", "Expirée"),
    ]

    email = models.EmailField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="invitations")
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="invitations")
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL, related_name="invitations")
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="invitations"
    )
    invited_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="sent_invitations")
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    accepted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Invitation {self.email} ({self.status})"
