from rest_framework import serializers

from .models import ORGANISATION_ROLE_CHOICES, Invitation, Organisation, PasswordResetRequest, Team, TeamMembership, User
from .services import can_manage_team


class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = ["id", "name", "created_at"]


class OrganisationCreateSerializer(serializers.Serializer):
    organisation_name = serializers.CharField(max_length=200)
    admin_name = serializers.CharField(max_length=200)
    admin_email = serializers.EmailField()


class UserSerializer(serializers.ModelSerializer):
    teams = serializers.SerializerMethodField()
    organisation_role_display = serializers.CharField(source="get_organisation_role_display", read_only=True)
    account_type_display = serializers.CharField(source="get_account_type_display", read_only=True)
    account_status_display = serializers.CharField(source="get_account_status_display", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "teams",
            "organisation",
            "organisation_role",
            "organisation_role_display",
            "is_platform_admin",
            "account_type",
            "account_type_display",
            "account_status",
            "account_status_display",
            "planning_color",
        ]

    def get_teams(self, obj):
        # `team_memberships` (reverse FK) n'est pas filtré par statut par
        # défaut — seules les TeamMembership actives comptent. `_active_memberships`
        # (préchargé par les viewsets qui sérialisent `UserSerializer` en
        # masse — voir `Prefetch(... "_active_memberships")`) évite un
        # `SELECT` par utilisateur dans les listes ; requête ponctuelle sinon.
        if hasattr(obj, "_active_memberships"):
            return [m.team_id for m in obj._active_memberships]
        return list(obj.team_memberships.filter(status="active").values_list("team_id", flat=True))


class OrganisationRoleUpdateSerializer(serializers.Serializer):
    organisation_role = serializers.ChoiceField(choices=ORGANISATION_ROLE_CHOICES)


class MeSerializer(UserSerializer):
    """`UserSerializer` + préférences strictement personnelles (session du
    2026-09-16) — volontairement PAS sur `UserSerializer` de base : ce
    dernier est nested un peu partout (membres de projet/groupe, auteur d'un
    commentaire...), `email_notifications_enabled` n'a de sens que pour
    l'intéressé lui-même. Utilisé par `MeView` et les deux endpoints de
    l'écran Paramètres (mot de passe, préférences)."""

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + [
            "email_notifications_enabled",
            "outlook_calendar_sync_enabled",
            "accent_color",
        ]


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)


class NotificationPreferencesSerializer(serializers.Serializer):
    email_notifications_enabled = serializers.BooleanField()


class AppearancePreferencesSerializer(serializers.Serializer):
    # `allow_blank=True` : chaîne vide = réinitialisation à l'habillage
    # Awtodo par défaut, valeur valide (bouton "Par défaut" de l'écran
    # Réglages), pas une absence de champ.
    accent_color = serializers.CharField(max_length=7, allow_blank=True)


class PlanningPreferencesSerializer(serializers.Serializer):
    """`planning_color` accepte une chaîne vide : c'est la façon de revenir à
    "pas de couleur choisie" (repli sur l'accent thémé). Les horaires de
    travail sont gérés séparément, voir `apps.planning.views.WorkingHoursView`
    (modèle hebdomadaire + exceptions, pas juste deux champs scalaires).
    `outlook_calendar_sync_enabled` (session du 2026-09-22) : scaffolding,
    n'a encore aucun effet réel — voir `apps.planning.signals`."""

    planning_color = serializers.RegexField(
        r"^(#[0-9A-Fa-f]{6})?$", required=False, allow_blank=True
    )
    outlook_calendar_sync_enabled = serializers.BooleanField(required=False)


class TeamMembershipSerializer(serializers.ModelSerializer):
    """Vue « adhésion » d'un membre de groupe (utilisateur + rôle) — voir
    `TeamSerializer.memberships`, distinct de `TeamSerializer.members`
    (liste d'utilisateurs bruts, déjà consommée ailleurs pour peupler des
    sélecteurs — pas touchée pour ne rien casser)."""

    user = UserSerializer(read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = TeamMembership
        fields = ["id", "user", "role", "role_display"]


class TeamSerializer(serializers.ModelSerializer):
    members = serializers.SerializerMethodField()
    memberships = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ["id", "name", "description", "organisation", "created_by", "members", "memberships", "can_manage"]

    def get_members(self, obj):
        member_ids = TeamMembership.objects.filter(team=obj).values_list("user_id", flat=True)
        return UserSerializer(User.objects.filter(id__in=member_ids), many=True).data

    def get_memberships(self, obj):
        memberships = TeamMembership.objects.filter(team=obj).select_related("user")
        return TeamMembershipSerializer(memberships, many=True).data

    def get_can_manage(self, obj):
        # Voir CLAUDE.md > "Permissions API — flags calculés" : une seule
        # source de vérité (apps.accounts.services), le frontend ne
        # recalcule jamais une règle de rôle lui-même.
        request = self.context.get("request")
        return can_manage_team(getattr(request, "user", None), obj)


class TeamCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True, default="")


class TeamMemberSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())


class TeamMemberRoleSerializer(serializers.Serializer):
    membership = serializers.PrimaryKeyRelatedField(queryset=TeamMembership.objects.all())
    role = serializers.ChoiceField(choices=TeamMembership.ROLE_CHOICES)


class TeamRenameSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)


class InvitationSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    organisation_name = serializers.CharField(source="organisation.name", read_only=True)
    user = UserSerializer(read_only=True)
    invited_by = UserSerializer(read_only=True)

    class Meta:
        model = Invitation
        fields = [
            "id",
            "email",
            "user",
            "organisation",
            "organisation_name",
            "team",
            "project",
            "invited_by",
            "token",
            "status",
            "status_display",
            "created_at",
            "accepted_at",
        ]


class InvitationCreateSerializer(serializers.Serializer):
    """Réservée aux invitations de comptes internes (`POST /api/v1/invitations/`,
    voir CLAUDE.md > "Comptes et invitations"). Volontairement sans champ
    `project` : les invitations de comptes externes scopés à un projet
    passent par `POST /api/v1/projects/{id}/members/invite/`
    (`apps.projects.views`), qui a déjà l'instance `Project` résolue —
    `apps.accounts` ne doit jamais importer `apps.projects` (voir la note sur
    `Invitation.project` dans models.py), donc ce serializer ne peut pas
    accepter un `project` en entrée sans violer cette règle."""

    email = serializers.EmailField()
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    team = serializers.PrimaryKeyRelatedField(queryset=Team.objects.all(), required=False, allow_null=True)


class InvitationAcceptSerializer(serializers.Serializer):
    """Mot de passe choisi par l'invité pour activer son compte (voir
    `apps.accounts.services.accept_invitation`, session du 2026-08-06)."""

    password = serializers.CharField(write_only=True)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class PasswordResetRequestSerializer(serializers.Serializer):
    """Identifiant OU email — voir `services.request_password_reset`."""

    identifier = serializers.CharField()


class PasswordResetTokenSerializer(serializers.ModelSerializer):
    """Volontairement minimal : n'expose ni `user` ni aucune donnée
    personnelle — le lien est public le temps que la personne choisisse son
    nouveau mot de passe, juste assez pour que la page affiche "lien valide"
    ou "lien expiré/déjà utilisé" avant soumission."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = PasswordResetRequest
        fields = ["id", "status", "status_display", "is_expired"]


class PasswordResetConfirmSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)
