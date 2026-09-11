from rest_framework import serializers

from apps.accounts.models import Team, User
from apps.accounts.serializers import UserSerializer
from apps.common.choices import PRIORITY_CHOICES

from .models import Project, ProjectMembership, ProjectVersion
from .services import get_project_permissions

# Statuts de tâche comptant comme "travail réel" pour l'indicateur de
# progression (X/Y tâches terminées) — tout sauf `rejetee`, qui n'a jamais
# été acceptée comme travail à faire. Dupliqué en littéral plutôt qu'importé
# de `apps.tasks` : `projects` est en dessous de `tasks` dans la hiérarchie
# de dépendances du projet (voir CLAUDE.md), l'import serait interdit.
NON_REJECTED_TASK_STATUSES = [
    "en_attente_validation",
    "disponible",
    "assignee",
    "en_cours",
    "archivee",
]


class ProjectMembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = ProjectMembership
        fields = ["id", "user", "role", "role_display"]


class ProjectSerializer(serializers.ModelSerializer):
    project_type_display = serializers.CharField(source="get_project_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    team = serializers.PrimaryKeyRelatedField(read_only=True)
    team_name = serializers.SerializerMethodField()
    tasks_total = serializers.SerializerMethodField()
    tasks_done = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    current_version_id = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "project_type",
            "project_type_display",
            "status",
            "status_display",
            "deadline",
            "already_in_production",
            "priority",
            "priority_display",
            "team",
            "team_name",
            "tasks_total",
            "tasks_done",
            "notepad_content",
            "notepad_updated_at",
            "members",
            "permissions",
            "current_version_id",
        ]

    def get_permissions(self, obj):
        request = self.context.get("request")
        return get_project_permissions(getattr(request, "user", None), obj)

    def get_current_version_id(self, obj):
        # Évite un aller-retour séparé pour connaître la version par défaut à
        # afficher (sélecteur de version, voir docs/modeles-et-api.md).
        # `_current_versions` préchargé par `ProjectViewSet.get_queryset()`
        # dans la liste ; requête ponctuelle sinon (détail, après création).
        if hasattr(obj, "_current_versions"):
            current = obj._current_versions[0] if obj._current_versions else None
        else:
            current = obj.versions.filter(is_current=True).first()
        return str(current.id) if current else None

    def get_team_name(self, obj):
        return obj.team.name if obj.team else None

    def get_tasks_total(self, obj):
        # Annoté par ProjectViewSet.queryset quand disponible (évite une requête
        # par projet dans la liste) ; recalculé au besoin (ex. juste après la
        # création, où l'instance ne vient pas du queryset annoté).
        if hasattr(obj, "tasks_total"):
            return obj.tasks_total
        return obj.tasks.filter(status__in=NON_REJECTED_TASK_STATUSES).count()

    def get_tasks_done(self, obj):
        if hasattr(obj, "tasks_done"):
            return obj.tasks_done
        return obj.tasks.filter(status="archivee").count()

    def get_members(self, obj):
        # `_prefetched_members` posé par `ProjectViewSet.get_queryset()` dans
        # la liste ; requête ponctuelle sinon. Même portée qu'avant (manager
        # `all_objects` — inchangé, y compris les adhésions `removed`).
        if hasattr(obj, "_prefetched_members"):
            memberships = obj._prefetched_members
        else:
            memberships = ProjectMembership.objects.filter(project=obj).select_related("user")
        return ProjectMembershipSerializer(memberships, many=True).data


class ProjectCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    project_type = serializers.ChoiceField(choices=Project.TYPE_CHOICES)
    deadline = serializers.DateField(required=False, allow_null=True)
    already_in_production = serializers.BooleanField(required=False, default=False)
    priority = serializers.ChoiceField(choices=PRIORITY_CHOICES, required=False, allow_null=True)
    team = serializers.PrimaryKeyRelatedField(queryset=Team.objects.all(), required=False, allow_null=True)
    member_ids = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), many=True, required=False)


class ProjectNotepadUpdateSerializer(serializers.Serializer):
    notepad_content = serializers.CharField(allow_blank=True)


class SpecSectionSerializer(serializers.Serializer):
    """Une sous-section du cahier des charges — objet simple (pas un
    `ModelSerializer`) : `get_spec_sections`/`update_spec_section` renvoient
    un dict synthétisé, pas forcément une instance `SpecSection` (voir
    apps/projects/services.py)."""

    section_key = serializers.CharField(read_only=True)
    label = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    content = serializers.CharField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True, allow_null=True)


class SpecSectionUpdateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=False)
    content = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if "is_active" not in attrs and "content" not in attrs:
            raise serializers.ValidationError("Fournir `is_active` et/ou `content`.")
        return attrs


class ProjectMemberAddSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    email = serializers.EmailField(required=False)
    role = serializers.ChoiceField(choices=ProjectMembership.ROLE_CHOICES, required=False, default="membre")

    def validate(self, attrs):
        if not attrs.get("user") and not attrs.get("email"):
            raise serializers.ValidationError("Fournir soit `user`, soit `email`.")
        return attrs


class ProjectMemberRoleSerializer(serializers.Serializer):
    membership = serializers.PrimaryKeyRelatedField(queryset=ProjectMembership.objects.all())
    role = serializers.ChoiceField(choices=ProjectMembership.ROLE_CHOICES)


class ProjectMemberRemoveSerializer(serializers.Serializer):
    membership = serializers.PrimaryKeyRelatedField(queryset=ProjectMembership.objects.all())


class ProjectConvertToCollaborativeSerializer(serializers.Serializer):
    team = serializers.PrimaryKeyRelatedField(queryset=Team.objects.all())


class ProjectVersionSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = ProjectVersion
        fields = ["id", "project", "label", "is_current", "created_at", "created_by"]


class ProjectVersionCreateSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=100)


class ProjectInviteExternalSerializer(serializers.Serializer):
    """3ᵉ cas de `POST /api/v1/projects/{id}/members/` — voir CLAUDE.md >
    "Onglet Administration sur le hub projet". Distinct de
    `ProjectMemberAddSerializer` : ici la personne n'a aucun compte, on ne
    fournit donc jamais `user`."""

    email = serializers.EmailField()
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
