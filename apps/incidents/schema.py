from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers

from apps.common.schema import body, no_body

from .serializers import (
    IncidentAssignProjectSerializer,
    IncidentCommentCreateSerializer,
    IncidentCommentSerializer,
    IncidentCreateSerializer,
    IncidentPriorityUpdateSerializer,
    IncidentReassignTeamSerializer,
    IncidentResolveSerializer,
    IncidentSerializer,
)


def _transition(request):
    return extend_schema(request=request, responses=IncidentSerializer)


incident_schema = extend_schema_view(
    create=extend_schema(request=IncidentCreateSerializer, responses={201: IncidentSerializer}),
    assign_project=_transition(IncidentAssignProjectSerializer),
    reassign_team=_transition(IncidentReassignTeamSerializer),
    claim=no_body(IncidentSerializer),
    update_priority=_transition(IncidentPriorityUpdateSerializer),
    start=no_body(IncidentSerializer),
    resolve=_transition(IncidentResolveSerializer),
    archive=no_body(IncidentSerializer),
    cancel=_transition(body("IncidentCancelRequest", cancellation_reason=serializers.CharField())),
    update_description=_transition(
        body("IncidentDescriptionRequest", description=serializers.CharField(allow_blank=True))
    ),
    comments=extend_schema(request=IncidentCommentCreateSerializer, responses={201: IncidentCommentSerializer}),
)
