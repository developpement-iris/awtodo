from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import AuditLogEntry


class AuditLogEntrySerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)

    class Meta:
        model = AuditLogEntry
        fields = ["id", "actor", "field_name", "old_value", "new_value", "created_at"]
