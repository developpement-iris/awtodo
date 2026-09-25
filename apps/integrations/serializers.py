from rest_framework import serializers

from .models import ApiKey


class ApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        # `key_hash` volontairement absent — même règle que
        # `O365Connection.client_secret` (jamais renvoyé en clair par l'API).
        fields = [
            "id",
            "name",
            "key_prefix",
            "is_active",
            "created_at",
            "revoked_at",
            "last_used_at",
        ]


class ApiKeyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
