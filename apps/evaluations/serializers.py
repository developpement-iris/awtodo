from rest_framework import serializers

from .models import ANSWER_TYPES, SECTIONS, CatalogQuestion

QUESTION_FIELDS = [
    "id", "section", "label", "help_text", "answer_type", "options", "required",
    "position", "condition_on", "condition_values", "status",
]


class QuestionDefinitionInputSerializer(serializers.Serializer):
    section = serializers.ChoiceField(choices=SECTIONS)
    label = serializers.CharField(max_length=300)
    help_text = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    answer_type = serializers.ChoiceField(choices=ANSWER_TYPES)
    options = serializers.ListField(child=serializers.CharField(max_length=150), required=False, default=list)
    required = serializers.BooleanField(required=False, default=False)
    condition_on = serializers.UUIDField(required=False, allow_null=True, default=None)
    condition_values = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class CatalogQuestionCreateSerializer(QuestionDefinitionInputSerializer):
    team = serializers.UUIDField(required=False, allow_null=True, default=None)
    project = serializers.UUIDField(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        if bool(attrs.get("team")) == bool(attrs.get("project")):
            raise serializers.ValidationError("Indiquez soit un groupe, soit un projet.")
        return attrs


class QuestionDefinitionUpdateSerializer(serializers.Serializer):
    """Mise à jour partielle : seuls les champs envoyés changent."""

    label = serializers.CharField(max_length=300, required=False)
    help_text = serializers.CharField(max_length=500, required=False, allow_blank=True)
    answer_type = serializers.ChoiceField(choices=ANSWER_TYPES, required=False)
    options = serializers.ListField(child=serializers.CharField(max_length=150), required=False)
    required = serializers.BooleanField(required=False)
    condition_on = serializers.UUIDField(required=False, allow_null=True)
    condition_values = serializers.ListField(child=serializers.CharField(), required=False)


class MoveSerializer(serializers.Serializer):
    direction = serializers.ChoiceField(choices=["up", "down"])


class CatalogQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogQuestion
        fields = QUESTION_FIELDS + ["team", "project"]


class CatalogScopeSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["team", "project"])
    id = serializers.UUIDField()
    name = serializers.CharField()


class CatalogListSerializer(serializers.Serializer):
    scope = CatalogScopeSerializer()
    can_manage = serializers.BooleanField()
    questions = CatalogQuestionSerializer(many=True)
