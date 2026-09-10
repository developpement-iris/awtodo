from django.db.models import Count, Prefetch, Q
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import TeamMembership
from apps.accounts.services import AccountPermissionError, AccountValidationError, create_invitation
from apps.common.views import ListOnlyFilterMixin

from .filters import ProjectFilterSet
from .models import Project, ProjectMembership, ProjectVersion
from .serializers import (
    NON_REJECTED_TASK_STATUSES,
    ProjectCreateSerializer,
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
from .services import (
    ProjectPermissionError,
    ProjectValidationError,
    accessible_projects,
    add_project_member,
    change_project_member_role,
    close_project,
    create_project,
    create_project_version,
    get_spec_sections,
    prefetched_project_roles,
    remove_project_member,
    reopen_project,
    update_project_notepad,
    update_spec_section,
)


class ProjectViewSet(
    ListOnlyFilterMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    # Schéma/introspection uniquement (drf-spectacular, etc.) — la portée
    # réelle vient de `get_queryset()`, qui dépend de l'utilisateur courant
    # et ne peut donc pas être un simple attribut de classe.
    queryset = Project.objects.active()
    serializer_class = ProjectSerializer
    filterset_class = ProjectFilterSet

    def get_queryset(self):
        base = accessible_projects(self.request.user)
        if self.action != "list":
            # Détail / actions : le serializer a des chemins de repli (voir
            # `hasattr` dans ProjectSerializer). Surtout, les `@action` qui
            # modifient un membre/une version puis re-sérialisent le même
            # objet ne doivent pas voir un `prefetch_related(to_attr=...)`
            # figé d'avant la modification.
            return base
        return (
            base.select_related("team")
            .prefetch_related(
                # `get_members` / `get_current_version_id` du serializer lisent
                # ces attributs préchargés au lieu de requêter par projet.
                Prefetch(
                    "memberships",
                    queryset=ProjectMembership.objects.select_related("user").prefetch_related(
                        # `UserSerializer.get_teams` de chaque membre — sinon
                        # un SELECT par membre par projet.
                        Prefetch(
                            "user__team_memberships",
                            queryset=TeamMembership.objects.filter(status="active"),
                            to_attr="_active_memberships",
                        )
                    ),
                    to_attr="_prefetched_members",
                ),
                Prefetch(
                    "versions",
                    queryset=ProjectVersion.objects.filter(is_current=True),
                    to_attr="_current_versions",
                ),
            )
            .annotate(
                tasks_total=Count("tasks", filter=Q(tasks__status__in=NON_REJECTED_TASK_STATUSES), distinct=True),
                tasks_done=Count("tasks", filter=Q(tasks__status="archivee"), distinct=True),
            )
        )

    def list(self, request, *args, **kwargs):
        # Sérialisation de la liste enroulée dans le cache d'appartenances
        # (voir apps/projects/services.py) : le bloc `permissions` de chaque
        # projet se calcule alors sans requête par ligne.
        objects = list(self.filter_queryset(self.get_queryset()))
        with prefetched_project_roles(request.user, [p.id for p in objects]):
            return Response(self.get_serializer(objects, many=True).data)

    def create(self, request, *args, **kwargs):
        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            project = create_project(actor=request.user, **serializer.validated_data)
        except ProjectPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except ProjectValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(project).data, status=201)

    def update(self, request, *args, **kwargs):
        # Seul le bloc-notes est modifiable via cet endpoint (voir CLAUDE.md
        # — pas d'édition des autres champs du projet dans ce chantier). Le
        # cahier des charges passe par `spec_sections`/`spec_section_detail`
        # ci-dessous, pas par cet endpoint.
        project = self.get_object()
        serializer = ProjectNotepadUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            updated = update_project_notepad(actor=request.user, project=project, **serializer.validated_data)
        except ProjectPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)

        return Response(self.get_serializer(updated).data)

    @action(detail=True, methods=["get"], url_path="spec-sections")
    def spec_sections(self, request, pk=None):
        project = self.get_object()

        try:
            sections = get_spec_sections(actor=request.user, project=project)
        except ProjectPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)

        return Response(SpecSectionSerializer(sections, many=True).data)

    @action(detail=True, methods=["patch"], url_path="spec-sections/(?P<section_key>[^/.]+)")
    def spec_section_detail(self, request, pk=None, section_key=None):
        project = self.get_object()
        serializer = SpecSectionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            section = update_spec_section(
                actor=request.user, project=project, section_key=section_key, **serializer.validated_data
            )
        except ProjectPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except ProjectValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(SpecSectionSerializer(section).data)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        project = self.get_object()

        try:
            close_project(actor=request.user, project=project)
        except ProjectPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except ProjectValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(project).data)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        project = self.get_object()

        try:
            reopen_project(actor=request.user, project=project)
        except ProjectPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except ProjectValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(project).data)

    @action(detail=True, methods=["get", "post"])
    def versions(self, request, pk=None):
        project = self.get_object()

        if request.method == "GET":
            # Voir docs/modeles-et-api.md : lecture réservée aux membres du
            # projet — déjà garanti par le scoping de `get_queryset()`
            # (`self.get_object()` 404 sinon), pas de vérification en plus ici.
            versions = ProjectVersion.objects.filter(project=project)
            return Response(ProjectVersionSerializer(versions, many=True).data)

        serializer = ProjectVersionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            version = create_project_version(actor=request.user, project=project, **serializer.validated_data)
        except ProjectPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except ProjectValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(ProjectVersionSerializer(version).data, status=201)

    @action(detail=True, methods=["post"], url_path="members")
    def members(self, request, pk=None):
        project = self.get_object()
        serializer = ProjectMemberAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            add_project_member(actor=request.user, project=project, **serializer.validated_data)
        except ProjectPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except ProjectValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(project).data, status=201)

    @action(detail=True, methods=["post"], url_path="members/role")
    def member_role(self, request, pk=None):
        project = self.get_object()
        serializer = ProjectMemberRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = serializer.validated_data["membership"]

        if membership.project_id != project.id:
            return Response({"detail": "Cette adhésion n'appartient pas à ce projet."}, status=400)

        try:
            change_project_member_role(actor=request.user, membership=membership, role=serializer.validated_data["role"])
        except ProjectPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except ProjectValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(project).data)

    @action(detail=True, methods=["post"], url_path="members/invite")
    def invite_member(self, request, pk=None):
        # 3ᵉ cas de "ajout de membre" — personne sans compte, crée un compte
        # externe + une invitation (voir CLAUDE.md > "Comptes et invitations").
        # Délègue à apps.accounts.services : projects peut importer accounts
        # (sens de dépendance autorisé), l'inverse ne l'est pas.
        project = self.get_object()
        serializer = ProjectInviteExternalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            create_invitation(actor=request.user, project=project, **serializer.validated_data)
        except AccountPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except AccountValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(project).data, status=201)

    @action(detail=True, methods=["post"], url_path="members/remove")
    def remove_member(self, request, pk=None):
        project = self.get_object()
        serializer = ProjectMemberRemoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = serializer.validated_data["membership"]

        if membership.project_id != project.id:
            return Response({"detail": "Cette adhésion n'appartient pas à ce projet."}, status=400)

        try:
            remove_project_member(actor=request.user, membership=membership)
        except ProjectPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except ProjectValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(project).data)
