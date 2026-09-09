from rest_framework import serializers

from .models import ORGANISATION_ROLE_CHOICES, Invitation, Organisation, Team, TeamMembership, User
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
        ]

    def get_teams(self, obj):
        # `team_memberships` (reverse FK) n'est pas filtré par statut par
        # défaut — filtrage explicite ici, seules les TeamMembership actives
        # comptent comme appartenance réelle au groupe.
        return list(obj.team_memberships.filter(status="active").values_list("team_id", flat=True))


class OrganisationRoleUpdateSerializer(serializers.Serializer):
    organisation_role = serializers.ChoiceField(choices=ORGANISATION_ROLE_CHOICES)


class TeamSerializer(serializers.ModelSerializer):
    members = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ["id", "name", "description", "organisation", "created_by", "members", "can_manage"]

    def get_members(self, obj):
        member_ids = TeamMembership.objects.filter(team=obj).values_list("user_id", flat=True)
        return UserSerializer(User.objects.filter(id__in=member_ids), many=True).data

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
