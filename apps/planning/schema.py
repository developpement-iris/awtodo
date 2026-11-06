"""Les réponses du planning sont des dicts assemblés par `services` : décrites
comme des objets génériques, seuls les corps de requête sont détaillés."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view

from apps.common.schema import no_body

from .serializers import (
    BlockCreateSerializer,
    BlockUpdateSerializer,
    EventCreateSerializer,
    EventOccurrenceCancelSerializer,
    EventOccurrenceUpdateSerializer,
    EventUpdateSerializer,
    ParticipantAddSerializer,
    ProjectEntryCreateSerializer,
    ProjectEntryUpdateSerializer,
    RespondSerializer,
    ShareCreateSerializer,
    SharePermissionsUpdateSerializer,
    WorkingHoursUpdateSerializer,
)

_OBJECT = OpenApiTypes.OBJECT
_LIST = {200: {"type": "array", "items": {"type": "object"}}}
_WINDOW = [
    OpenApiParameter("from", OpenApiTypes.DATETIME, required=True, description="Début de la fenêtre (ISO 8601)."),
    OpenApiParameter("to", OpenApiTypes.DATETIME, required=True, description="Fin de la fenêtre (ISO 8601)."),
]
_WORKING_HOURS = [
    OpenApiParameter("user", OpenApiTypes.UUID, description="Personne concernée, si elle vous a délégué ce droit."),
    OpenApiParameter("week", OpenApiTypes.DATE, description="Un jour de la semaine visée (exception ponctuelle)."),
]


def _create(request):
    return extend_schema(request=request, responses={201: _OBJECT})


def _update(request):
    return extend_schema(request=request, responses=_OBJECT)


calendar_schema = extend_schema_view(
    get=extend_schema(
        parameters=[
            *_WINDOW,
            OpenApiParameter("owners", OpenApiTypes.STR, description="Identifiants séparés par des virgules."),
            OpenApiParameter("projects", OpenApiTypes.STR, description="Identifiants séparés par des virgules."),
            OpenApiParameter("outlook", OpenApiTypes.BOOL, description="Ajoute les rendez-vous Outlook (lecture seule)."),
        ],
        responses=_OBJECT,
    )
)
event_schema = extend_schema_view(
    list=extend_schema(operation_id="planning_events_list", responses=_LIST),
    retrieve=extend_schema(responses=_OBJECT),
    create=_create(EventCreateSerializer),
    partial_update=_update(EventUpdateSerializer),
    cancel=no_body(),
    update_occurrence=_update(EventOccurrenceUpdateSerializer),
    cancel_occurrence=extend_schema(request=EventOccurrenceCancelSerializer, responses={204: None}),
    add_participant=_update(ParticipantAddSerializer),
    remove_participant=no_body(),
    respond=_update(RespondSerializer),
)
block_schema = extend_schema_view(
    list=extend_schema(responses=_LIST),
    create=_create(BlockCreateSerializer),
    partial_update=_update(BlockUpdateSerializer),
    cancel=no_body(),
)
share_schema = extend_schema_view(
    list=extend_schema(responses=_OBJECT),
    create=_create(ShareCreateSerializer),
    revoke=no_body(),
    permissions=_update(SharePermissionsUpdateSerializer),
)
working_hours_schema = extend_schema_view(
    get=extend_schema(parameters=_WORKING_HOURS, responses=_OBJECT),
    patch=extend_schema(parameters=_WORKING_HOURS, request=WorkingHoursUpdateSerializer, responses=_OBJECT),
    delete=extend_schema(parameters=_WORKING_HOURS, request=None, responses=_OBJECT),
)
project_planning_schema = extend_schema_view(
    entries=[
        extend_schema(methods=["GET"], parameters=_WINDOW, responses=_LIST),
        extend_schema(methods=["POST"], request=ProjectEntryCreateSerializer, responses={201: _OBJECT}),
    ],
    entry_detail=_update(ProjectEntryUpdateSerializer),
    entry_cancel=no_body(),
)
