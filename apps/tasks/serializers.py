from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from apps.common.audit import get_audit_log
from apps.common.choices import PRIORITY_CHOICES
from apps.common.serializers import AuditLogEntrySerializer
from apps.projects.models import Project

from .models import Task, TaskComment
from .services import get_task_permissions


class TaskSerializer(serializers.ModelSerializer):
    task_type_display = serializers.CharField(source="get_task_type_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    assignee = UserSerializer(read_only=True)
    permissions = serializers.SerializerMethodField()
    version_label = serializers.CharField(source="version.label", read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "project",
            "version",
            "version_label",
            "title",
            "description",
            "task_type",
            "task_type_display",
            "priority",
            "priority_display",
            "deadline",
            "assignee",
            "time_spent",
            "estimated_hours",
            "origin",
            "external_reference_id",
            "status",
            "status_display",
            "rejection_reason",
            "created_at",
            "updated_at",
            "permissions",
        ]

    def get_permissions(self, obj):
        # Voir CLAUDE.md > "Permissions API — flags calculés" : une seule
        # source de vérité (apps.tasks.services), le frontend ne recalcule
        # jamais une règle de rôle/statut lui-même.
        request = self.context.get("request")
        return get_task_permissions(getattr(request, "user", None), obj)


class TaskCommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = TaskComment
        fields = ["id", "author", "content", "created_at"]


class TaskDetailSerializer(TaskSerializer):
    comments = TaskCommentSerializer(many=True, read_only=True)
    audit_log = serializers.SerializerMethodField()

    class Meta(TaskSerializer.Meta):
        fields = TaskSerializer.Meta.fields + ["comments", "audit_log"]

    def get_audit_log(self, obj):
        return AuditLogEntrySerializer(get_audit_log(obj), many=True).data


class TaskCommentCreateSerializer(serializers.Serializer):
    content = serializers.CharField()


class ProjectUserStatsSerializer(serializers.Serializer):
    """Une ligne du tableau "Statistiques" par utilisateur (voir
    docs/modeles-et-api.md) — objet simple en sortie de
    `apps.tasks.services.get_project_user_stats`, pas un `ModelSerializer`
    (les données sont un agrégat, pas une instance de modèle)."""

    user = UserSerializer(read_only=True)
    tasks_done = serializers.IntegerField(read_only=True)
    tasks_in_progress = serializers.IntegerField(read_only=True)
    hours_spent = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)


class CompletionTrendPointSerializer(serializers.Serializer):
    """Un point du graphique en barres "Tâches terminées par semaine" (voir
    docs/modeles-et-api.md > "Statistiques")."""

    week_start = serializers.DateField(read_only=True)
    count = serializers.IntegerField(read_only=True)


class TaskInsightsSerializer(serializers.Serializer):
    """Widgets étendus de l'écran Statistiques (délais, heures, respect des
    échéances, personnes sollicitées, tendance hebdomadaire — voir
    docs/modeles-et-api.md), sortie de `apps.tasks.services._task_insights`.
    Réutilisé à la fois en tant que tel (`project-insights`) et par mixin de
    champs dans `GlobalTaskStatsSerializer` (mêmes clés, portée différente)."""

    hours_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    estimated_hours_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    avg_lead_time_days = serializers.FloatField(read_only=True, allow_null=True)
    tasks_on_time = serializers.IntegerField(read_only=True)
    tasks_late = serializers.IntegerField(read_only=True)
    tasks_over_estimate = serializers.IntegerField(read_only=True)
    tasks_under_estimate = serializers.IntegerField(read_only=True)
    contributors_count = serializers.IntegerField(read_only=True)
    priority_breakdown = serializers.DictField(child=serializers.IntegerField(), read_only=True)
    completion_trend = CompletionTrendPointSerializer(many=True, read_only=True)


class GlobalTaskStatsSerializer(TaskInsightsSerializer):
    projects_total = serializers.IntegerField(read_only=True)
    projects_active = serializers.IntegerField(read_only=True)
    projects_closed = serializers.IntegerField(read_only=True)
    tasks_done = serializers.IntegerField(read_only=True)
    tasks_in_progress = serializers.IntegerField(read_only=True)


class TaskCreateSerializer(serializers.Serializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    task_type = serializers.ChoiceField(choices=Task.TASK_TYPE_CHOICES)
    priority = serializers.ChoiceField(choices=PRIORITY_CHOICES, required=False, default="moyenne")
    deadline = serializers.DateField(required=False, allow_null=True)
    external_reference_id = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=100
    )
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    estimated_hours = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False, allow_null=True, min_value=0
    )
