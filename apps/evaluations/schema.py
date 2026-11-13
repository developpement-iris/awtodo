"""Documentation OpenAPI des fiches d'évaluation — voir apps/common/schema.py."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view

from .serializers import (
    CatalogListSerializer,
    CatalogQuestionCreateSerializer,
    CatalogQuestionSerializer,
    MoveSerializer,
    QuestionDefinitionUpdateSerializer,
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
