from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.services import contributor_projects

from . import services
from .models import DocSpace
from .serializers import (
    DocEntryCreateSerializer,
    DocEntryUpdateSerializer,
    DocPageCreateSerializer,
    DocPageUpdateSerializer,
)


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
        entry = services.update_entry(
            actor=request.user, project=project, entry_id=entry_id, **serializer.validated_data
        )
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
