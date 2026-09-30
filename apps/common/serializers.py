from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import AuditLogEntry


class AuditLogEntrySerializer(serializers.ModelSerializer):
    # `allow_null` : une entrée peut être journalisée sans acteur (action
    # système, ex. incident créé par le compte de service ticketing).
    actor = UserSerializer(read_only=True, allow_null=True)

    class Meta:
        model = AuditLogEntry
        fields = ["id", "actor", "verb", "field_name", "old_value", "new_value", "created_at"]


class ProjectHistoryEntrySerializer(AuditLogEntrySerializer):
    """Vue enrichie pour l'historique projet/global (session du 2026-09-29,
    voir docs/modeles-et-api.md > "Historique d'activité") — ajoute le type
    d'entité et le contexte projet/groupe, absents de la vue imbriquée dans
    une tâche/un incident (`AuditLogEntrySerializer` seule, déjà dans le
    contexte de cette entité-là)."""

    entity_type = serializers.CharField(source="content_type.model", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True, default=None)
    team_name = serializers.CharField(source="team.name", read_only=True, default=None)

    class Meta(AuditLogEntrySerializer.Meta):
        fields = AuditLogEntrySerializer.Meta.fields + ["entity_type", "project", "project_name", "team_name"]
