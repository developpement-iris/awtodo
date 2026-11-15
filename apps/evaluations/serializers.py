from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import ANSWER_TYPES, SECTIONS, CatalogQuestion, EvaluationSheet, SheetQuestion
from .services import can_manage_sheets, internal_evaluation, public_path, sheet_questions

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


# --- Fiches --------------------------------------------------------------


class SheetCreateSerializer(serializers.Serializer):
    project = serializers.UUIDField()
    title = serializers.CharField(max_length=200)
    client_intro = serializers.CharField(required=False, allow_blank=True, default="")


class SheetUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    client_intro = serializers.CharField(required=False, allow_blank=True)


class SheetQuestionSerializer(serializers.ModelSerializer):
    is_generic = serializers.SerializerMethodField()

    class Meta:
        model = SheetQuestion
        fields = QUESTION_FIELDS + ["is_generic"]

    def get_is_generic(self, obj) -> bool:
        return obj.catalog_question_id is not None


class SheetSummarySerializer(serializers.ModelSerializer):
    response_count = serializers.SerializerMethodField()
    public_path = serializers.SerializerMethodField()

    class Meta:
        model = EvaluationSheet
        fields = [
            "id", "project", "title", "client_intro", "status", "created_at", "opened_at", "closed_at",
            "response_count", "public_path",
        ]

    def get_response_count(self, obj) -> int:
        # Annoté en liste (`list_sheets`) ; compté à la demande en détail.
        count = getattr(obj, "response_count", None)
        if count is None:
            count = obj.client_responses.filter(status="retenue").count()
        return count

    def get_public_path(self, obj) -> str | None:
        return public_path(obj)


class SheetPermissionsSerializer(serializers.Serializer):
    can_manage = serializers.BooleanField()


class InternalPartSerializer(serializers.Serializer):
    answers = serializers.DictField(child=serializers.JSONField(allow_null=True))
    updated_at = serializers.DateTimeField(allow_null=True)
    updated_by = serializers.CharField(allow_null=True)


class SheetDetailSerializer(SheetSummarySerializer):
    """Détail d'une fiche : résumé, questions actives (les deux parties),
    partie chef de projet déjà saisie et droits."""

    questions = serializers.SerializerMethodField()
    internal = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta(SheetSummarySerializer.Meta):
        fields = SheetSummarySerializer.Meta.fields + ["questions", "internal", "permissions"]

    @extend_schema_field(InternalPartSerializer)
    def get_internal(self, obj):
        evaluation = internal_evaluation(obj)
        if evaluation is None:
            return {"answers": {}, "updated_at": None, "updated_by": None}
        user = evaluation.updated_by
        name = (f"{user.first_name} {user.last_name}".strip() or user.username) if user else None
        return {
            "answers": {str(a.question_id): a.value for a in evaluation.answers.all()},
            "updated_at": evaluation.updated_at,
            "updated_by": name,
        }

    @extend_schema_field(SheetQuestionSerializer(many=True))
    def get_questions(self, obj):
        return SheetQuestionSerializer(sheet_questions(obj), many=True).data

    @extend_schema_field(SheetPermissionsSerializer)
    def get_permissions(self, obj):
        user = self.context["request"].user
        return {"can_manage": can_manage_sheets(user, obj.project)}


class PublicSubmitSerializer(serializers.Serializer):
    respondent_name = serializers.CharField(max_length=150, allow_blank=True)
    answers = serializers.DictField(child=serializers.JSONField(allow_null=True), required=False, default=dict)


class PublicQuestionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    label = serializers.CharField()
    help_text = serializers.CharField()
    answer_type = serializers.ChoiceField(choices=ANSWER_TYPES)
    options = serializers.ListField(child=serializers.CharField())
    required = serializers.BooleanField()
    condition_on = serializers.UUIDField(allow_null=True)
    condition_values = serializers.ListField(child=serializers.JSONField())


class PublicSheetSerializer(serializers.Serializer):
    """Contenu exposé sans compte. `client_intro` et `questions` sont absents
    quand `closed` est vrai."""

    closed = serializers.BooleanField()
    title = serializers.CharField()
    project_name = serializers.CharField()
    client_intro = serializers.CharField(required=False)
    questions = PublicQuestionSerializer(many=True, required=False)


class DetailMessageSerializer(serializers.Serializer):
    detail = serializers.CharField()


class AnswersSerializer(serializers.Serializer):
    answers = serializers.DictField(child=serializers.JSONField(allow_null=True), required=False, default=dict)


class ResponseItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    respondent_name = serializers.CharField()
    created_at = serializers.DateTimeField()
    status = serializers.ChoiceField(choices=["retenue", "ecartee"])
    answers = serializers.DictField(child=serializers.JSONField(allow_null=True))


class ResultClientItemSerializer(serializers.Serializer):
    question_id = serializers.UUIDField()
    summary = serializers.DictField(help_text="Synthèse selon le type : note, nps, yes_no, choices ou text.")


class ResultInternalItemSerializer(serializers.Serializer):
    question_id = serializers.UUIDField()
    value = serializers.JSONField(allow_null=True)


class SheetResultsSerializer(serializers.Serializer):
    response_count = serializers.IntegerField()
    client = ResultClientItemSerializer(many=True)
    interne = ResultInternalItemSerializer(many=True)
