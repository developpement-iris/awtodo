from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Invitation, Organisation, PasswordResetRequest, PermissionProfile, Team, User
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
from .services import (
    AccountPermissionError,
    AccountValidationError,
    accept_invitation,
    add_team_member,
    archive_permission_profile,
    assign_permission_profile,
    authenticate_user,
    change_own_password,
    change_team_member_role,
    confirm_password_reset,
    create_invitation,
    create_organisation,
    create_permission_profile,
    create_team,
    deactivate_account,
    list_permission_profiles,
    reactivate_account,
    remove_team_member,
    rename_team,
    request_password_reset,
    resend_invitation,
    set_organisation_role,
    unassign_permission_profile,
    update_notification_preferences,
    update_organisation_branding,
    update_permission_profile,
    update_planning_preferences,
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
                "user": MeSerializer(user).data,
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
        return Response(MeSerializer(request.user).data)


class ChangePasswordView(APIView):
    """Écran Paramètres (session du 2026-09-16) — connecté, distinct du flux
    « mot de passe oublié » (public, voir `PasswordResetRequestView`)."""

    def post(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({"detail": "Utilisateur non identifié."}, status=401)
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            change_own_password(actor=request.user, **serializer.validated_data)
        except AccountValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response({"detail": "Mot de passe mis à jour."})


class NotificationPreferencesView(APIView):
    """Écran Paramètres (session du 2026-09-16) — un seul réglage pour
    l'instant (envoi par email), voir `User.email_notifications_enabled`."""

    def patch(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({"detail": "Utilisateur non identifié."}, status=401)
        serializer = NotificationPreferencesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated = update_notification_preferences(actor=request.user, **serializer.validated_data)
        return Response(MeSerializer(updated).data)


class OrganisationBrandingView(APIView):
    """Couleurs de marque de l'organisation courante (session du 2026-09-28,
    remplace l'ancienne préférence d'accent par utilisateur — écran
    Administration > Marque). Lecture ouverte à tout utilisateur
    authentifié (le thème doit s'appliquer avant même d'agir), écriture
    réservée à un admin d'organisation (garde dans le service)."""

    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({"detail": "Utilisateur non identifié."}, status=401)
        return Response(OrganisationBrandingSerializer(request.user.organisation).data)

    def patch(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({"detail": "Utilisateur non identifié."}, status=401)
        serializer = OrganisationBrandingUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            organisation = update_organisation_branding(
                actor=request.user, organisation=request.user.organisation, **serializer.validated_data
            )
        except AccountPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        return Response(OrganisationBrandingSerializer(organisation).data)


class PermissionProfileViewSet(viewsets.GenericViewSet):
    """Profils de droits personnalisés (session du 2026-09-28) — portée
    organisation, réservés à un admin d'organisation (garde dans chaque
    fonction de service). Voir CLAUDE.md > "Roadmap macro" pour le cadrage
    (couche additive aux rôles existants, jamais un remplacement)."""

    queryset = PermissionProfile.objects.none()
    serializer_class = PermissionProfileSerializer

    def _handle(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs), None
        except AccountPermissionError as exc:
            return None, Response({"detail": str(exc)}, status=403)
        except AccountValidationError as exc:
            return None, Response({"detail": str(exc)}, status=400)

    def list(self, request):
        profiles = list_permission_profiles(request.user.organisation)
        return Response(PermissionProfileSerializer(profiles, many=True).data)

    def create(self, request):
        serializer = PermissionProfileCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile, err = self._handle(
            create_permission_profile, actor=request.user, organisation=request.user.organisation, **serializer.validated_data
        )
        if err:
            return err
        return Response(PermissionProfileSerializer(profile).data, status=201)

    def partial_update(self, request, pk=None):
        profile = get_object_or_404(PermissionProfile.all_objects, id=pk, organisation=request.user.organisation)
        serializer = PermissionProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        profile, err = self._handle(update_permission_profile, actor=request.user, profile=profile, **serializer.validated_data)
        if err:
            return err
        return Response(PermissionProfileSerializer(profile).data)

    def destroy(self, request, pk=None):
        profile = get_object_or_404(PermissionProfile.all_objects, id=pk, organisation=request.user.organisation)
        _, err = self._handle(archive_permission_profile, actor=request.user, profile=profile)
        if err:
            return err
        return Response(status=204)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        profile = get_object_or_404(PermissionProfile.all_objects, id=pk, organisation=request.user.organisation)
        serializer = PermissionProfileAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_user = get_object_or_404(User, id=serializer.validated_data["user_id"])
        _, err = self._handle(assign_permission_profile, actor=request.user, profile=profile, target_user=target_user)
        if err:
            return err
        return Response(PermissionProfileSerializer(profile).data)

    @action(detail=True, methods=["post"])
    def unassign(self, request, pk=None):
        profile = get_object_or_404(PermissionProfile.all_objects, id=pk, organisation=request.user.organisation)
        serializer = PermissionProfileAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_user = get_object_or_404(User, id=serializer.validated_data["user_id"])
        _, err = self._handle(unassign_permission_profile, actor=request.user, profile=profile, target_user=target_user)
        if err:
            return err
        return Response(PermissionProfileSerializer(profile).data)


class PlanningPreferencesView(APIView):
    """Écran Planning (session du 2026-09-18) — couleur du calendrier
    personnel + horaires de travail affichés (grisent le reste de la grille).
    Mise à jour partielle, voir `update_planning_preferences`."""

    def patch(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({"detail": "Utilisateur non identifié."}, status=401)
        serializer = PlanningPreferencesSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            updated = update_planning_preferences(actor=request.user, **serializer.validated_data)
        except AccountValidationError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(MeSerializer(updated).data)


class PasswordResetRequestView(APIView):
    """Public par nature (voir `LoginView` ci-dessus, même raisonnement) — la
    personne a justement perdu l'accès à son compte.

    Deux modes selon `settings.PASSWORD_RESET_DIRECT_LINK` :
    - `False` (défaut, cible) : toujours 200 avec un message générique, que
      l'identifiant corresponde ou non (pas d'énumération de comptes), un
      email part si un compte correspond.
    - `True` (phase de test, pas d'ESP branché) : pas d'email ; si un compte
      correspond, la réponse inclut `reset_path` (`/reset-password/<token>/`)
      pour que le frontend y redirige directement. Assumé sans enjeu de
      sécurité pour le nombre d'utilisateurs actuel (voir settings)."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            reset = request_password_reset(**serializer.validated_data)
        except AccountValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        if getattr(settings, "PASSWORD_RESET_DIRECT_LINK", False):
            if reset is None:
                return Response({"detail": "Aucun compte ne correspond à cet identifiant."}, status=404)
            return Response(
                {"detail": "Choisissez un nouveau mot de passe.", "reset_path": f"/reset-password/{reset.token}/"}
            )

        return Response({"detail": "Si un compte correspond à cet identifiant, un email a été envoyé."})


class PasswordResetTokenView(APIView):
    """Lecture publique de l'état d'un lien de réinitialisation (voir
    `InvitationViewSet.retrieve` pour le même raisonnement — la personne n'a
    par définition pas de session utilisable). Sert à la page frontend à
    afficher "lien valide"/"lien expiré" avant même de tenter une
    soumission."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, token):
        reset = get_object_or_404(PasswordResetRequest, token=token)
        return Response(PasswordResetTokenSerializer(reset).data)


class PasswordResetConfirmView(APIView):
    """⚠️ Comme `InvitationViewSet`, publique par construction : en
    staging/production la permission par défaut est `IsAuthenticated`, sans
    ce `permission_classes` explicite le lien reçu par email renverrait 403."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, token):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            confirm_password_reset(token=token, **serializer.validated_data)
        except AccountValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response({"detail": "Mot de passe mis à jour."})


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

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        target_user = self.get_object()

        try:
            updated = deactivate_account(actor=request.user, target_user=target_user)
        except AccountPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except AccountValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(UserSerializer(updated).data)

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        target_user = self.get_object()

        try:
            updated = reactivate_account(actor=request.user, target_user=target_user)
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

    @action(detail=True, methods=["post"], url_path="members/role")
    def member_role(self, request, pk=None):
        team = self.get_object()
        serializer = TeamMemberRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = serializer.validated_data["membership"]

        if membership.team_id != team.id:
            return Response({"detail": "Cette adhésion n'appartient pas à ce groupe."}, status=400)

        try:
            change_team_member_role(actor=request.user, membership=membership, role=serializer.validated_data["role"])
        except AccountPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except AccountValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(team).data)

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
    l'écran Administration, pas un annuaire public.

    ⚠️ En staging/production la permission par défaut est `IsAuthenticated`
    (seul `config/settings/dev.py` l'assouplit) : sans le `get_permissions`
    ci-dessous, `retrieve`/`accept` renverraient 403 à l'invité et le lien
    d'activation afficherait "lien expiré ou invalide"."""

    queryset = Invitation.objects.all()
    serializer_class = InvitationSerializer
    lookup_field = "token"

    def get_permissions(self):
        if self.action in {"retrieve", "accept"}:
            return [AllowAny()]
        return super().get_permissions()

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
