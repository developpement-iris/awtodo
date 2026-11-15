"""Documentation OpenAPI des fiches d'évaluation — voir apps/common/schema.py."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view

from .serializers import (
    AnswersSerializer,
    ResponseItemSerializer,
    SheetResultsSerializer,
    CatalogListSerializer,
    CatalogQuestionCreateSerializer,
    CatalogQuestionSerializer,
    EvaluationMessageSerializer,
    MoveSerializer,
    PublicSheetSerializer,
    PublicSubmitSerializer,
    QuestionDefinitionInputSerializer,
    QuestionDefinitionUpdateSerializer,
    SheetCreateSerializer,
    SheetDetailSerializer,
    SheetQuestionSerializer,
    SheetSummarySerializer,
    SheetUpdateSerializer,
)

_SCOPE_DOC = (
    "Portée du catalogue : `team` (groupe) ou `project`. Un projet rattaché à un groupe "
    "renvoie vers le catalogue du groupe."
)

catalog_schema = extend_schema_view(
    list=extend_schema(
        description=_SCOPE_DOC,
        parameters=[
            OpenApiParameter("team", OpenApiTypes.UUID, description="Groupe"),
            OpenApiParameter("project", OpenApiTypes.UUID, description="Projet"),
            OpenApiParameter("include_archived", OpenApiTypes.BOOL, description="Inclut les questions archivées"),
        ],
        responses=CatalogListSerializer,
    ),
    create=extend_schema(
        description=_SCOPE_DOC, request=CatalogQuestionCreateSerializer, responses={201: CatalogQuestionSerializer}
    ),
    partial_update=extend_schema(
        description="Le type de réponse (`answer_type`) ne change pas après la création.",
        request=QuestionDefinitionUpdateSerializer,
        responses=CatalogQuestionSerializer,
    ),
    archive=extend_schema(request=None, responses=CatalogQuestionSerializer),
    restore=extend_schema(request=None, responses=CatalogQuestionSerializer),
    move=extend_schema(request=MoveSerializer, responses=CatalogQuestionSerializer),
)


def _sheet_action(request=None):
    return extend_schema(request=request, responses=SheetDetailSerializer)


_QUESTION_ID = OpenApiParameter("question_id", OpenApiTypes.UUID, OpenApiParameter.PATH)
_RESPONSE_ID = OpenApiParameter("response_id", OpenApiTypes.UUID, OpenApiParameter.PATH)


def _question_action(request=None):
    return extend_schema(request=request, responses=SheetQuestionSerializer, parameters=[_QUESTION_ID])


sheet_schema = extend_schema_view(
    list=extend_schema(
        parameters=[OpenApiParameter("project", OpenApiTypes.UUID, required=True, description="Projet")],
        responses=SheetSummarySerializer(many=True),
    ),
    create=extend_schema(request=SheetCreateSerializer, responses={201: SheetDetailSerializer}),
    retrieve=extend_schema(responses=SheetDetailSerializer),
    partial_update=_sheet_action(SheetUpdateSerializer),
    add_question=extend_schema(
        description="Question propre à la fiche (fiche en brouillon seulement).",
        request=QuestionDefinitionInputSerializer,
        responses={201: SheetQuestionSerializer},
    ),
    question_detail=_question_action(QuestionDefinitionUpdateSerializer),
    question_archive=_question_action(),
    question_move=_question_action(MoveSerializer),
    open=extend_schema(
        description="Brouillon -> ouverte : fige les questions et génère le lien public.",
        request=None,
        responses=SheetDetailSerializer,
    ),
    close=_sheet_action(),
    reopen=_sheet_action(),
    archive=_sheet_action(),
    rotate_link=extend_schema(
        description="Nouveau jeton : l'ancien lien cesse de fonctionner.", request=None, responses=SheetDetailSerializer
    ),
    internal=extend_schema(
        description=(
            "Partie chef de projet : une seule par fiche, enregistrement partiel, écrase la saisie précédente. "
            "Fiche ouverte ou close. `answers` : {id de question interne : valeur}."
        ),
        request=AnswersSerializer,
        responses=SheetDetailSerializer,
    ),
    results=extend_schema(responses=SheetResultsSerializer),
    responses=extend_schema(responses=ResponseItemSerializer(many=True)),
    response_discard=extend_schema(
        description="Écarte une réponse (spam, test) : elle sort des résultats, de l'export et des statistiques.",
        request=None,
        responses=ResponseItemSerializer(many=True),
        parameters=[_RESPONSE_ID],
    ),
    response_restore=extend_schema(
        request=None, responses=ResponseItemSerializer(many=True), parameters=[_RESPONSE_ID]
    ),
    export=extend_schema(
        description="Export CSV (séparateur « ; », encodage UTF-8 avec BOM pour Excel).",
        responses={(200, "text/csv"): OpenApiTypes.STR},
    ),
)


public_get_schema = extend_schema(
    description=(
        "Formulaire client, sans compte (lien public d'une fiche). N'expose que les questions client "
        "d'une fiche ouverte ; `closed` est vrai si la fiche est close. 404 si le lien est inconnu ou révoqué."
    ),
    responses=PublicSheetSerializer,
)

public_submit_schema = extend_schema(
    description=(
        "Envoi d'une réponse client, sans compte. `answers` : {id de question : valeur}. "
        "Limité à 10 envois par heure et par adresse IP. 410 si la fiche n'accepte plus de réponses."
    ),
    request=PublicSubmitSerializer,
    responses={201: EvaluationMessageSerializer},
)
