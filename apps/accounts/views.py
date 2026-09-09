from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Invitation, Organisation, Team, User
from .serializers import (
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
    LoginSerializer,
    OrganisationCreateSerializer,
    OrganisationRoleUpdateSerializer,
    OrganisationSerializer,
    TeamCreateSerializer,
    TeamMemberSerializer,
    TeamRenameSerializer,
    TeamSerializer,
    UserSerializer,
)
from .services import (
    AccountPermissionError,
    AccountValidationError,
    accept_invitation,
    add_team_member,
    authenticate_user,
    create_invitation,
    create_organisation,
    create_team,
    remove_team_member,
    rename_team,
    resend_invitation,
    set_organisation_role,
)


class LoginView(APIView):
    """Connexion par mot de passe (voir CLAUDE.md > "Stack technique" > Auth,
    session du 2026-08-06) — publique par nature (c'est le point d'entrée
    avant d'avoir une identité), pas de permission ni d'authentification
    préalable requise."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = authenticate_user(**serializer.validated_data)
        except AccountValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            }
        )


class MeView(APIView):
    """"Qui suis-je" — permet au frontend de résoudre l'utilisateur courant à
    partir d'un token stocké (JWT) sans le décoder côté client. Fonctionne
    avec n'importe quel mécanisme d'authentification déjà résolu par DRF
    (JWT, header debug...), pas seulement le JWT."""

    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({"detail": "Utilisateur non identifié."}, status=401)
        return Response(UserSerializer(request.user).data)


class UserViewSet(ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    @action(detail=True, methods=["patch"], url_path="organisation-role")
    def organisation_role(self, request, pk=None):
        target_user = self.get_object()
        serializer = OrganisationRoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            updated = set_organisation_role(
                actor=request.user, target_user=target_user, role=serializer.validated_data["organisation_role"]
            )
        except AccountPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except AccountValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(UserSerializer(updated).data)


class TeamViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Team.objects.active()
    serializer_class = TeamSerializer

    def create(self, request, *args, **kwargs):
        serializer = TeamCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            team = create_team(actor=request.user, **serializer.validated_data)
        except AccountPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except AccountValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(team).data, status=201)

    @action(detail=True, methods=["post"], url_path="members")
    def members(self, request, pk=None):
        team = self.get_object()
        serializer = TeamMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            add_team_member(actor=request.user, team=team, **serializer.validated_data)
        except AccountPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except AccountValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(team).data, status=201)

    @action(detail=True, methods=["post"], url_path="members/remove")
    def remove_member(self, request, pk=None):
        team = self.get_object()
        serializer = TeamMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            remove_team_member(actor=request.user, team=team, **serializer.validated_data)
        except AccountPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except AccountValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(team).data)

    @action(detail=True, methods=["patch"], url_path="rename")
    def rename(self, request, pk=None):
        team = self.get_object()
        serializer = TeamRenameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            renamed = rename_team(actor=request.user, team=team, **serializer.validated_data)
        except AccountPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except AccountValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(renamed).data)


class OrganisationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Organisation.objects.all()
    serializer_class = OrganisationSerializer

    def _require_platform_admin(self, request):
        if not request.user or not getattr(request.user, "is_authenticated", False):
            return Response({"detail": "Utilisateur non identifié."}, status=403)
        if not request.user.is_platform_admin:
            return Response({"detail": "Réservé aux administrateurs de la plateforme."}, status=403)
        return None

    def list(self, request, *args, **kwargs):
        denied = self._require_platform_admin(request)
        if denied is not None:
            return denied
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = OrganisationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            organisation, admin_user = create_organisation(actor=request.user, **serializer.validated_data)
        except AccountPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except AccountValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        payload = OrganisationSerializer(organisation).data
        payload["admin"] = UserSerializer(admin_user).data
        return Response(payload, status=201)


class InvitationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """`retrieve` (par token) et `accept` sont volontairement publics —
    l'invité n'a par définition pas encore de session utilisable (voir
    CLAUDE.md > "Comptes et invitations", limite assumée : pas de vrai
    mécanisme de session tant que le SSO n'est pas fait). `list` est en
    revanche restreint (admin/chef_de_projet de l'organisation courante) et
    scopé à cette organisation — c'est la sous-section "Invitations" de
    l'écran Administration, pas un annuaire public."""

    queryset = Invitation.objects.all()
    serializer_class = InvitationSerializer
    lookup_field = "token"

    def get_queryset(self):
        if self.action == "list":
            return Invitation.objects.filter(organisation=self.request.user.organisation).order_by("-created_at")
        return super().get_queryset()

    def list(self, request, *args, **kwargs):
        if not request.user or not getattr(request.user, "is_authenticated", False):
            return Response({"detail": "Utilisateur non identifié."}, status=403)
        if request.user.organisation_role not in {"admin", "chef_de_projet"}:
            return Response({"detail": "Réservé aux administrateurs et chefs de projet."}, status=403)
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            invitation = create_invitation(actor=request.user, **serializer.validated_data)
        except AccountPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except AccountValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(InvitationSerializer(invitation).data, status=201)

    @action(detail=True, methods=["post"])
    def accept(self, request, token=None):
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            invitation = accept_invitation(token=token, **serializer.validated_data)
        except AccountValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(InvitationSerializer(invitation).data)

    @action(detail=True, methods=["post"])
    def resend(self, request, token=None):
        invitation = self.get_object()

        try:
            new_invitation = resend_invitation(actor=request.user, invitation=invitation)
        except AccountPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except AccountValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(InvitationSerializer(new_invitation).data, status=201)
