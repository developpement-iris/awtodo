from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import serializers

from apps.common.choices import PRIORITY_CHOICES
from apps.common.schema import body, no_body

from .serializers import (
    GlobalTaskStatsSerializer,
    ProjectUserStatsSerializer,
    TaskCommentCreateSerializer,
    TaskCommentSerializer,
    TaskCreateSerializer,
    TaskInsightsSerializer,
    TaskSerializer,
    TaskTypeSerializer,
)

_SCOPE_DOC = "Exactement l'un des deux : `team` (groupe) ou `project` (projet sans groupe)."


def _transition(name, **fields):
    return extend_schema(request=body(name, **fields), responses=TaskSerializer)


task_type_schema = extend_schema_view(
    list=extend_schema(
        description=_SCOPE_DOC,
        parameters=[
            OpenApiParameter("team", OpenApiTypes.UUID, description="Groupe"),
            OpenApiParameter("project", OpenApiTypes.UUID, description="Projet sans groupe"),
            OpenApiParameter("include_archived", OpenApiTypes.BOOL, description="Inclut les types archivés"),
        ],
        responses=body(
            "TaskTypeList",
            scope=body(
                "TaskTypeScope",
                kind=serializers.ChoiceField(choices=["team", "project"]),
                id=serializers.UUIDField(),
                name=serializers.CharField(),
            ),
            can_manage=serializers.BooleanField(),
            types=TaskTypeSerializer(many=True),
        ),
    ),
    create=extend_schema(
        description=_SCOPE_DOC,
        request=body(
            "TaskTypeCreateRequest",
            team=serializers.UUIDField(required=False),
            project=serializers.UUIDField(required=False),
            label=serializers.CharField(),
            icon=serializers.CharField(required=False),
        ),
        responses={201: TaskTypeSerializer},
    ),
    partial_update=extend_schema(
        request=body(
            "TaskTypeUpdateRequest",
            label=serializers.CharField(required=False),
            icon=serializers.CharField(required=False),
        ),
        responses=TaskTypeSerializer,
    ),
    archive=no_body(TaskTypeSerializer),
    restore=no_body(TaskTypeSerializer),
)

task_schema = extend_schema_view(
    create=extend_schema(request=TaskCreateSerializer, responses={201: TaskSerializer}),
    assigned_to=extend_schema(responses=TaskSerializer(many=True)),
    project_stats=extend_schema(responses=ProjectUserStatsSerializer(many=True)),
    project_insights=extend_schema(responses=TaskInsightsSerializer),
    global_stats=extend_schema(responses=GlobalTaskStatsSerializer),
    rename=_transition("TaskRenameRequest", title=serializers.CharField()),
    update_description=_transition("TaskDescriptionRequest", description=serializers.CharField(allow_blank=True)),
    update_estimated_hours=_transition(
        "TaskEstimatedHoursRequest",
        estimated_hours=serializers.DecimalField(max_digits=6, decimal_places=2, allow_null=True),
    ),
    update_deadline=_transition(
        "TaskDeadlineRequest",
        deadline=serializers.DateField(allow_null=True, help_text="`null` ou vide : retire l'échéance."),
    ),
    update_type=_transition(
        "TaskTypeUpdateOnTaskRequest", task_type=serializers.CharField(help_text="Clé d'un type actif de la portée.")
    ),
    update_priority=_transition("TaskPriorityRequest", priority=serializers.ChoiceField(choices=PRIORITY_CHOICES)),
    validate=_transition("TaskValidateRequest", assignee=serializers.UUIDField(required=False, allow_null=True)),
    reject=_transition("TaskRejectRequest", rejection_reason=serializers.CharField()),
    cancel=_transition("TaskCancelRequest", cancellation_reason=serializers.CharField()),
    reactivate=no_body(TaskSerializer),
    claim=no_body(TaskSerializer),
    assign=_transition("TaskAssignRequest", assignee=serializers.UUIDField()),
    start=no_body(TaskSerializer),
    complete=_transition(
        "TaskCompleteRequest", time_spent=serializers.DecimalField(max_digits=6, decimal_places=2)
    ),
    comments=extend_schema(request=TaskCommentCreateSerializer, responses={201: TaskCommentSerializer}),
)
