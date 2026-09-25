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


class ApiKeyCreatedSerializer(ApiKeySerializer):
    """Documentation OpenAPI uniquement (`@extend_schema`, voir views.py) —
    jamais utilisée pour sérialiser réellement une réponse, la vue construit
    le dict à la main (`{**ApiKeySerializer(...).data, "key": raw_key}`).
    Décrit la forme exacte de la réponse de génération, `key` en plus : la
    seule et unique fois où la valeur en clair est renvoyée."""

    key = serializers.CharField()

    class Meta(ApiKeySerializer.Meta):
        fields = ApiKeySerializer.Meta.fields + ["key"]
