from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers

from apps.common.schema import DetailMessage, body, no_body

from .serializers import (
    ChangePasswordSerializer,
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
    LoginSerializer,
    MeSerializer,
    NotificationPreferencesSerializer,
    OrganisationBrandingSerializer,
    OrganisationBrandingUpdateSerializer,
    OrganisationCreateSerializer,
    OrganisationRoleUpdateSerializer,
    OrganisationSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PasswordResetTokenSerializer,
    PermissionProfileAssignSerializer,
    PermissionProfileCreateSerializer,
    PermissionProfileSerializer,
    PermissionProfileUpdateSerializer,
    PlanningPreferencesSerializer,
    TeamCreateSerializer,
    TeamMemberRoleSerializer,
    TeamMemberSerializer,
    TeamRenameSerializer,
    TeamSerializer,
    UserSerializer,
)

login_schema = extend_schema_view(
    post=extend_schema(
        request=LoginSerializer,
        responses=body(
            "LoginResponse",
            access=serializers.CharField(),
            refresh=serializers.CharField(),
            user=MeSerializer(),
        ),
    )
)
me_schema = extend_schema_view(get=extend_schema(responses=MeSerializer))
change_password_schema = extend_schema_view(
    post=extend_schema(request=ChangePasswordSerializer, responses=DetailMessage)
)
notification_preferences_schema = extend_schema_view(
    patch=extend_schema(request=NotificationPreferencesSerializer, responses=MeSerializer)
)
planning_preferences_schema = extend_schema_view(
    patch=extend_schema(request=PlanningPreferencesSerializer, responses=MeSerializer)
)
organisation_branding_schema = extend_schema_view(
    get=extend_schema(responses=OrganisationBrandingSerializer),
    patch=extend_schema(request=OrganisationBrandingUpdateSerializer, responses=OrganisationBrandingSerializer),
)
password_reset_request_schema = extend_schema_view(
    post=extend_schema(request=PasswordResetRequestSerializer, responses=DetailMessage)
)
password_reset_token_schema = extend_schema_view(get=extend_schema(responses=PasswordResetTokenSerializer))
password_reset_confirm_schema = extend_schema_view(
    post=extend_schema(request=PasswordResetConfirmSerializer, responses=DetailMessage)
)

permission_profile_schema = extend_schema_view(
    list=extend_schema(responses=PermissionProfileSerializer(many=True)),
    create=extend_schema(request=PermissionProfileCreateSerializer, responses={201: PermissionProfileSerializer}),
    partial_update=extend_schema(request=PermissionProfileUpdateSerializer, responses=PermissionProfileSerializer),
    destroy=no_body(),
    assign=extend_schema(request=PermissionProfileAssignSerializer, responses=PermissionProfileSerializer),
    unassign=extend_schema(request=PermissionProfileAssignSerializer, responses=PermissionProfileSerializer),
)
user_schema = extend_schema_view(
    organisation_role=extend_schema(request=OrganisationRoleUpdateSerializer, responses=UserSerializer),
    deactivate=no_body(UserSerializer),
    reactivate=no_body(UserSerializer),
)
team_schema = extend_schema_view(
    create=extend_schema(request=TeamCreateSerializer, responses={201: TeamSerializer}),
    members=extend_schema(request=TeamMemberSerializer, responses={201: TeamSerializer}),
    member_role=extend_schema(request=TeamMemberRoleSerializer, responses=TeamSerializer),
    remove_member=extend_schema(request=TeamMemberSerializer, responses=TeamSerializer),
    rename=extend_schema(request=TeamRenameSerializer, responses=TeamSerializer),
)
organisation_schema = extend_schema_view(
    create=extend_schema(request=OrganisationCreateSerializer, responses={201: OrganisationSerializer}),
)
invitation_schema = extend_schema_view(
    create=extend_schema(request=InvitationCreateSerializer, responses={201: InvitationSerializer}),
    accept=extend_schema(request=InvitationAcceptSerializer, responses=InvitationSerializer),
    resend=no_body({201: InvitationSerializer}),
)
