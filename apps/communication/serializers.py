from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import CommunicationChannel, CommunicationDelivery, CommunicationMessage, O365Connection


class O365ConnectionSerializer(serializers.ModelSerializer):
    is_configured = serializers.BooleanField(read_only=True)
    # Jamais renvoyé en clair — le champ n'apparaît qu'en écriture. Un booléen
    # dérivé indique juste s'il est renseigné.
    client_secret = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_client_secret = serializers.SerializerMethodField()

    class Meta:
        model = O365Connection
        fields = [
            "tenant_id",
            "client_id",
            "client_secret",
            "has_client_secret",
            "is_enabled",
            "is_configured",
        ]

    def get_has_client_secret(self, obj):
        return bool(obj.client_secret)


class CommunicationChannelSerializer(serializers.ModelSerializer):
    # "team" si rattaché à un groupe (hérité par tous ses projets), "project"
    # sinon — le frontend s'en sert pour regrouper l'affichage sous deux
    # sections distinctes (session du 2026-10-07).
    scope = serializers.SerializerMethodField()

    class Meta:
        model = CommunicationChannel
        fields = [
            "id",
            "scope",
            "label",
            "teams_channel_id",
            "teams_channel_name",
            "teams_webhook_url",
            "payload_template",
            "notify_incident_created",
            "status",
        ]

    def get_scope(self, obj):
        return "team" if obj.team_id else "project"


class CommunicationChannelCreateSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=150)
    teams_channel_id = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    teams_channel_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    teams_webhook_url = serializers.URLField(required=False, allow_blank=True, default="", max_length=1000)
    # "project" (défaut) ou "team" — voir apps.communication.services.create_channel.
    scope = serializers.ChoiceField(choices=["project", "team"], required=False, default="project")
    payload_template = serializers.JSONField(required=False, default=dict)
    notify_incident_created = serializers.BooleanField(required=False, default=False)


class CommunicationChannelUpdateSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=150, required=False)
    teams_channel_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    teams_channel_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    teams_webhook_url = serializers.URLField(required=False, allow_blank=True, max_length=1000)
    payload_template = serializers.JSONField(required=False)
    notify_incident_created = serializers.BooleanField(required=False)


class CommunicationDeliverySerializer(serializers.ModelSerializer):
    channel_label = serializers.CharField(source="channel.label", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = CommunicationDelivery
        fields = ["id", "channel", "channel_label", "status", "status_display", "response_detail", "responded_at"]


class CommunicationMessageSerializer(serializers.ModelSerializer):
    trigger_display = serializers.CharField(source="get_trigger_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_by = UserSerializer(read_only=True)
    deliveries = CommunicationDeliverySerializer(many=True, read_only=True)
    task_title = serializers.CharField(source="task.title", read_only=True, default=None)
    incident_title = serializers.CharField(source="incident.title", read_only=True, default=None)

    class Meta:
        model = CommunicationMessage
        fields = [
            "id",
            "subject",
            "body",
            "trigger",
            "trigger_display",
            "status",
            "status_display",
            "created_by",
            "deliveries",
            "task",
            "task_title",
            "incident",
            "incident_title",
            "created_at",
            "sent_at",
        ]


class CommunicationComposeSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=255)
    body = serializers.CharField()
    channel_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    # Rendent les champs de la tâche/de l'incident disponibles au gabarit de
    # payload (`{{task.*}}`/`{{incident.*}}`) — optionnels, aucun des deux
    # n'est requis pour un envoi manuel classique.
    task_id = serializers.UUIDField(required=False, allow_null=True)
    incident_id = serializers.UUIDField(required=False, allow_null=True)
