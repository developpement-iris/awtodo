from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import CommunicationChannel, CommunicationMessage, O365Connection


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
            "sender_mailbox",
            "is_enabled",
            "is_configured",
        ]

    def get_has_client_secret(self, obj):
        return bool(obj.client_secret)


class CommunicationChannelSerializer(serializers.ModelSerializer):
    channel_type_display = serializers.CharField(source="get_channel_type_display", read_only=True)

    class Meta:
        model = CommunicationChannel
        fields = [
            "id",
            "channel_type",
            "channel_type_display",
            "label",
            "email",
            "teams_webhook_url",
            "notify_incident_created",
            "status",
        ]


class CommunicationChannelCreateSerializer(serializers.Serializer):
    channel_type = serializers.ChoiceField(choices=CommunicationChannel.TYPE_CHOICES)
    label = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    teams_webhook_url = serializers.URLField(required=False, allow_blank=True, default="")
    notify_incident_created = serializers.BooleanField(required=False, default=False)


class CommunicationChannelUpdateSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False, allow_blank=True)
    teams_webhook_url = serializers.URLField(required=False, allow_blank=True)
    notify_incident_created = serializers.BooleanField(required=False)


class CommunicationMessageSerializer(serializers.ModelSerializer):
    trigger_display = serializers.CharField(source="get_trigger_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_by = UserSerializer(read_only=True)
    channels = CommunicationChannelSerializer(many=True, read_only=True)

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
            "channels",
            "incident",
            "created_at",
            "sent_at",
        ]


class CommunicationComposeSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=255)
    body = serializers.CharField()
    channel_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
