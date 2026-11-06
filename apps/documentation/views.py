from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.http import content_disposition_header
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import ProjectVersion
from apps.projects.services import contributor_projects

from . import services
from .models import DocSpace
from .schema import doc_space_schema
from .serializers import (
    ContributorsUpdateSerializer,
    DocEntryCreateSerializer,
    DocEntryUpdateSerializer,
    DocPageCreateSerializer,
    DocPageUpdateSerializer,
    DocSpaceAppearanceSerializer,
    DocSpaceSlugSerializer,
)


def _attachment_download(attachment):
    # Toujours en téléchargement, jamais affiché sur le domaine d'Awtodo.
    response = HttpResponse(bytes(attachment.data), content_type=attachment.content_type)
    response["Content-Disposition"] = content_disposition_header(True, attachment.filename)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "no-store"
    return response


@doc_space_schema
@extend_schema(responses=OpenApiTypes.OBJECT)
class DocSpaceViewSet(viewsets.GenericViewSet):
    """Espace de documentation d'un projet — voir CLAUDE.md > Roadmap
    (session 2026-09-03). Toute la logique métier est dans
    `apps.documentation.services` ; ces méthodes ne font que router et
    traduire les exceptions en codes HTTP. `lookup_field = "project_id"` :
    la ressource est identifiée par l'UUID du projet, pas par un id propre.
    `GenericViewSet` (plutôt que `ViewSet`) uniquement pour que
    drf-spectacular génère un schéma exploitable ; le queryset n'est jamais
    utilisé pour le routage réel (voir `_project`)."""

    lookup_field = "project_id"
    queryset = DocSpace.objects.none()
    serializer_class = DocPageCreateSerializer

    def _project(self, request, project_id):
        return get_object_or_404(contributor_projects(request.user), id=project_id)

    def handle_exception(self, exc):
        if isinstance(exc, services.DocsPermissionError):
            return Response({"detail": str(exc)}, status=403)
        if isinstance(exc, services.DocsValidationError):
            return Response({"detail": str(exc)}, status=400)
        return super().handle_exception(exc)

    # --- Agrégat ---------------------------------------------------------
    def retrieve(self, request, project_id=None):
        project = self._project(request, project_id)
        bundle = services.get_documentation_bundle(actor=request.user, project=project, request=request)
        return Response(bundle)

    # --- Pages ----------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="pages")
    def create_page(self, request, project_id=None):
        project = self._project(request, project_id)
        serializer = DocPageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        page = services.create_page(
            actor=request.user,
            project=project,
            title=data["title"],
            parent_id=data.get("parent_id"),
            content=data.get("content", ""),
            section=data.get("section", "documentation"),
        )
        return Response(services._page_dict(page), status=201)

    @action(detail=True, methods=["patch", "delete"], url_path=r"pages/(?P<page_id>[^/.]+)")
    def page_detail(self, request, project_id=None, page_id=None):
        project = self._project(request, project_id)
        if request.method == "DELETE":
            services.archive_page(actor=request.user, project=project, page_id=page_id)
            return Response(status=204)
        serializer = DocPageUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        kwargs = {}
        if "title" in data:
            kwargs["title"] = data["title"]
        if "content" in data:
            kwargs["content"] = data["content"]
        if "order" in data:
            kwargs["order"] = data["order"]
        if "parent_id" in data:
            kwargs["parent_id"] = data["parent_id"]  # peut être None (racine)
        page = services.update_page(actor=request.user, project=project, page_id=page_id, **kwargs)
        return Response(services._page_dict(page))

    @action(detail=True, methods=["post"], url_path=r"pages/(?P<page_id>[^/.]+)/publish")
    def publish_page(self, request, project_id=None, page_id=None):
        project = self._project(request, project_id)
        page = services.publish_page(actor=request.user, project=project, page_id=page_id)
        return Response(services._page_dict(page))

    @action(detail=True, methods=["post"], url_path=r"pages/(?P<page_id>[^/.]+)/unpublish")
    def unpublish_page(self, request, project_id=None, page_id=None):
        project = self._project(request, project_id)
        page = services.unpublish_page(actor=request.user, project=project, page_id=page_id)
        return Response(services._page_dict(page))

    # --- Pièces jointes du « Support d'utilisation » ------------------
    # `_automation_project` : ouvert aussi à une clé API de l'organisation du
    # projet — uniquement ces endpoints et la personnalisation.
    def _automation_project(self, request, project_id):
        return get_object_or_404(services.automation_projects(request.user), id=project_id)

    @action(detail=True, methods=["get"], url_path="support-pages")
    def support_pages(self, request, project_id=None):
        project = self._automation_project(request, project_id)
        return Response(services.list_support_pages(actor=request.user, project=project))

    @action(
        detail=True,
        methods=["post"],
        url_path=r"pages/(?P<page_id>[^/.]+)/attachments",
        parser_classes=[MultiPartParser],
    )
    def page_attachments(self, request, project_id=None, page_id=None):
        project = self._automation_project(request, project_id)
        file = request.FILES.get("file")
        if file is not None and file.size > services.MAX_ATTACHMENT_BYTES:
            # Refusé avant lecture : inutile de charger un gros fichier en mémoire.
            raise services.DocsValidationError(
                f"Fichier trop lourd — {services.MAX_ATTACHMENT_BYTES // (1024 * 1024)} Mo maximum."
            )
        attachment = services.upload_attachment(
            actor=request.user,
            project=project,
            page_id=page_id,
            filename=file.name if file else "",
            data=file.read() if file else b"",
        )
        return Response(services.attachment_dict(attachment), status=201)

    @action(
        detail=True,
        methods=["get", "delete"],
        url_path=r"pages/(?P<page_id>[^/.]+)/attachments/(?P<attachment_id>[^/.]+)",
    )
    def page_attachment_detail(self, request, project_id=None, page_id=None, attachment_id=None):
        project = self._automation_project(request, project_id)
        if request.method == "DELETE":
            services.archive_attachment(
                actor=request.user, project=project, page_id=page_id, attachment_id=attachment_id
            )
            return Response(status=204)
        attachment = services.get_attachment(
            actor=request.user, project=project, page_id=page_id, attachment_id=attachment_id
        )
        return _attachment_download(attachment)

    # --- Fiches (DocEntry) --------------------------------------------
    @action(detail=True, methods=["post"], url_path="entries")
    def create_entry(self, request, project_id=None):
        project = self._project(request, project_id)
        serializer = DocEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        entry = services.create_entry(
            actor=request.user,
            project=project,
            kind=data["kind"],
            title=data["title"],
            description=data.get("description", ""),
        )
        return Response(services._entry_dict(entry), status=201)

    @action(detail=True, methods=["patch", "delete"], url_path=r"entries/(?P<entry_id>[^/.]+)")
    def entry_detail(self, request, project_id=None, entry_id=None):
        project = self._project(request, project_id)
        if request.method == "DELETE":
            entry = services.archive_entry(actor=request.user, project=project, entry_id=entry_id)
            return Response(services._entry_dict(entry))
        serializer = DocEntryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        if "version_id" in data:
            version_id = data.pop("version_id")
            if version_id is None:
                data["version"] = None
            else:
                data["version"] = get_object_or_404(ProjectVersion, id=version_id, project=project)
        entry = services.update_entry(actor=request.user, project=project, entry_id=entry_id, **data)
        return Response(services._entry_dict(entry))

    @action(detail=True, methods=["post"], url_path=r"entries/(?P<entry_id>[^/.]+)/publish")
    def publish_entry(self, request, project_id=None, entry_id=None):
        project = self._project(request, project_id)
        entry = services.publish_entry(actor=request.user, project=project, entry_id=entry_id)
        return Response(services._entry_dict(entry))

    @action(detail=True, methods=["post"], url_path=r"entries/(?P<entry_id>[^/.]+)/unpublish")
    def unpublish_entry(self, request, project_id=None, entry_id=None):
        project = self._project(request, project_id)
        entry = services.unpublish_entry(actor=request.user, project=project, entry_id=entry_id)
        return Response(services._entry_dict(entry))

    @action(detail=True, methods=["post"], url_path="seed-from-spec")
    def seed_from_spec(self, request, project_id=None):
        project = self._project(request, project_id)
        created = services.seed_features_from_spec(actor=request.user, project=project)
        return Response({"created": [services._entry_dict(e) for e in created]}, status=201)

    # --- File « À documenter » ---------------------------------------
    @action(detail=True, methods=["post"], url_path=r"pending/(?P<pending_id>[^/.]+)/create-entry")
    def pending_create_entry(self, request, project_id=None, pending_id=None):
        project = self._project(request, project_id)
        entry = services.create_entry_from_pending(
            actor=request.user, project=project, pending_id=pending_id
        )
        return Response(services._entry_dict(entry), status=201)

    @action(detail=True, methods=["post"], url_path=r"pending/(?P<pending_id>[^/.]+)/ignore")
    def pending_ignore(self, request, project_id=None, pending_id=None):
        project = self._project(request, project_id)
        services.ignore_pending(actor=request.user, project=project, pending_id=pending_id)
        return Response(status=204)

    # --- Fiche « Contributeurs » ---------------------------------------
    @action(detail=True, methods=["post"], url_path="contributors/generate")
    def generate_contributors(self, request, project_id=None):
        project = self._project(request, project_id)
        entry = services.generate_contributors_entry(actor=request.user, project=project)
        return Response(services._entry_dict(entry), status=201)

    @action(detail=True, methods=["patch"], url_path="contributors")
    def update_contributors(self, request, project_id=None):
        project = self._project(request, project_id)
        serializer = ContributorsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = services.update_contributors_entry(
            actor=request.user, project=project, rows=serializer.validated_data["rows"]
        )
        return Response(services._entry_dict(entry))

    # --- Lien public --------------------------------------------------
    @action(detail=True, methods=["post", "delete"], url_path="public-link")
    def public_link(self, request, project_id=None):
        project = self._project(request, project_id)
        if request.method == "DELETE":
            space = services.revoke_public_link(actor=request.user, project=project)
        else:
            space = services.enable_public_link(actor=request.user, project=project)
        return Response({"space": services._space_dict(space, request)})

    @action(detail=True, methods=["post"], url_path="public-link/rotate")
    def public_link_rotate(self, request, project_id=None):
        project = self._project(request, project_id)
        space = services.rotate_public_link(actor=request.user, project=project)
        return Response({"space": services._space_dict(space, request)})

    @action(detail=True, methods=["patch"], url_path="public-link/slug")
    def public_link_slug(self, request, project_id=None):
        project = self._project(request, project_id)
        serializer = DocSpaceSlugSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        space = services.set_public_slug(actor=request.user, project=project, slug=serializer.validated_data["slug"])
        return Response({"space": services._space_dict(space, request)})

    # --- Personnalisation (couleur, en-tête, pied de page) -------------
    @action(detail=True, methods=["get", "patch"], url_path="appearance")
    def appearance(self, request, project_id=None):
        project = self._automation_project(request, project_id)
        if request.method == "GET":
            space = services.get_space_for_appearance(actor=request.user, project=project)
            return Response({"space": services._space_dict(space, request)})
        serializer = DocSpaceAppearanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        space = services.update_space_appearance(actor=request.user, project=project, **serializer.validated_data)
        return Response({"space": services._space_dict(space, request)})


class PublicDocsView(APIView):
    """Lecture publique de la documentation *publiée* d'un projet — voir
    CLAUDE.md > Stack technique > Auth : seule exception au garde-fou
    « connexion obligatoire ». Aucune donnée de gestion n'est exposée ici."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, token):
        data = services.get_public_docs(token)
        if data is None:
            raise Http404
        return Response(data)


class PublicDocAttachmentView(APIView):
    """Téléchargement public d'une pièce jointe de page publiée — mêmes
    conditions d'accès que `PublicDocsView`."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    def get(self, request, token, attachment_id):
        attachment = services.get_public_attachment(token, attachment_id)
        if attachment is None:
            raise Http404
        return _attachment_download(attachment)
