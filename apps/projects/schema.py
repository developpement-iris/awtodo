from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.common.schema import FILE_UPLOAD, file_response, no_body
from apps.common.serializers import ProjectHistoryEntrySerializer

from .serializers import (
    ProjectConvertToCollaborativeSerializer,
    ProjectCreateSerializer,
    ProjectDetailsUpdateSerializer,
    ProjectInviteExternalSerializer,
    ProjectMemberAddSerializer,
    ProjectMemberRemoveSerializer,
    ProjectMemberRoleSerializer,
    ProjectNotepadUpdateSerializer,
    ProjectSerializer,
    ProjectVersionCreateSerializer,
    ProjectVersionSerializer,
    SpecSectionSerializer,
    SpecSectionUpdateSerializer,
)


def _update(request):
    return extend_schema(request=request, responses=ProjectSerializer)


project_schema = extend_schema_view(
    create=extend_schema(request=ProjectCreateSerializer, responses={201: ProjectSerializer}),
    update=_update(ProjectNotepadUpdateSerializer),
    partial_update=_update(ProjectNotepadUpdateSerializer),
    spec_sections=extend_schema(responses=SpecSectionSerializer(many=True)),
    spec_section_detail=extend_schema(request=SpecSectionUpdateSerializer, responses=SpecSectionSerializer),
    close=no_body(ProjectSerializer),
    reopen=no_body(ProjectSerializer),
    versions=[
        extend_schema(methods=["GET"], responses=ProjectVersionSerializer(many=True)),
        extend_schema(
            methods=["POST"], request=ProjectVersionCreateSerializer, responses={201: ProjectVersionSerializer}
        ),
    ],
    members=extend_schema(request=ProjectMemberAddSerializer, responses={201: ProjectSerializer}),
    member_role=_update(ProjectMemberRoleSerializer),
    update_details=_update(ProjectDetailsUpdateSerializer),
    cover=[
        extend_schema(methods=["GET"], responses=file_response("image/webp")),
        extend_schema(methods=["POST"], request=FILE_UPLOAD, responses=ProjectSerializer),
    ],
    convert_to_collaborative=_update(ProjectConvertToCollaborativeSerializer),
    invite_member=extend_schema(request=ProjectInviteExternalSerializer, responses={201: ProjectSerializer}),
    remove_member=_update(ProjectMemberRemoveSerializer),
    history=extend_schema(responses=ProjectHistoryEntrySerializer(many=True)),
    history_export=extend_schema(responses={(200, "text/csv"): OpenApiTypes.STR}),
)
