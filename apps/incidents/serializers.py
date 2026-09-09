from rest_framework import serializers

from apps.accounts.models import Team
from apps.accounts.serializers import UserSerializer
from apps.common.audit import get_audit_log
from apps.common.choices import PRIORITY_CHOICES
from apps.common.serializers import AuditLogEntrySerializer
from apps.projects.models import Project

from .models import Incident, IncidentComment
from .services import get_incident_permissions


class IncidentSerializer(serializers.ModelSerializer):
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    team_name = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = [
            "id",
            "project",
            "team",
            "team_name",
            "title",
            "description",
            "priority",
            "priority_display",
            "status",
            "status_display",
            "external_reference_id",
            "assigned_to",
            "assigned_to_name",
            "created_at",
            "permissions",
        ]

    def get_team_name(self, obj):
        return obj.team.name if obj.team_id else None

    def get_assigned_to_name(self, obj):
        return obj.assigned_to.get_full_name() or obj.assigned_to.username if obj.assigned_to_id else None

    def get_permissions(self, obj):
        request = self.context.get("request")
        return get_incident_permissions(getattr(request, "user", None), obj)


class IncidentCommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = IncidentComment
        fields = ["id", "author", "content", "created_at"]


class IncidentDetailSerializer(IncidentSerializer):
    comments = IncidentCommentSerializer(many=True, read_only=True)
    audit_log = serializers.SerializerMethodField()

    class Meta(IncidentSerializer.Meta):
        fields = IncidentSerializer.Meta.fields + ["comments", "audit_log"]

    def get_audit_log(self, obj):
        return AuditLogEntrySerializer(get_audit_log(obj), many=True).data


class IncidentCreateSerializer(serializers.Serializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=False, allow_null=True)
    team = serializers.PrimaryKeyRelatedField(queryset=Team.objects.all(), required=False, allow_null=True)
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    priority = serializers.ChoiceField(choices=PRIORITY_CHOICES, required=False, default="moyenne")
    external_reference_id = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=100
    )


class IncidentAssignProjectSerializer(serializers.Serializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())


class IncidentPriorityUpdateSerializer(serializers.Serializer):
    priority = serializers.ChoiceField(choices=PRIORITY_CHOICES)


class IncidentCommentCreateSerializer(serializers.Serializer):
    content = serializers.CharField()
