from rest_framework import serializers

from .models import DocEntry


class DocPageCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    parent_id = serializers.UUIDField(required=False, allow_null=True)
    content = serializers.CharField(required=False, allow_blank=True, default="")


class DocPageUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    content = serializers.CharField(required=False, allow_blank=True)
    # `parent_id` absent = parent inchangé ; `parent_id: null` = page remontée
    # à la racine (voir services.update_page, sentinelle `_UNSET`).
    parent_id = serializers.UUIDField(required=False, allow_null=True)
    order = serializers.IntegerField(required=False, min_value=0)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Aucun champ à mettre à jour.")
        return attrs


class DocEntryCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=DocEntry.KIND_CHOICES)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")


class DocEntryUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    order = serializers.IntegerField(required=False, min_value=0)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Aucun champ à mettre à jour.")
        return attrs
