from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.services import contributor_projects

from . import services
from .models import DashboardWidget
from .serializers import (
    DashboardWidgetCreateSerializer,
    DashboardWidgetPositionSerializer,
    serialize_widget_entry,
)


class _DashboardExceptionMixin:
    """Traduit les exceptions de service en codes HTTP (même patron que
    `apps.communication.views._CommunicationExceptionMixin`)."""

    def handle_exception(self, exc):
        if isinstance(exc, services.DashboardPermissionError):
            return Response({"detail": str(exc)}, status=403)
        if isinstance(exc, services.DashboardValidationError):
            return Response({"detail": str(exc)}, status=400)
        return super().handle_exception(exc)


def _serialize_dashboard(entries):
    return {"widgets": [serialize_widget_entry(entry) for entry in entries]}


@extend_schema(responses=OpenApiTypes.OBJECT)
class ProjectDashboardView(_DashboardExceptionMixin, APIView):
    """Dashboard personnalisable d'un projet, propre à l'utilisateur courant.
    `contributor_projects` : un lecteur n'a pas accès à cet onglet, cohérent
    avec Budget/Incidents/Planning/Communication (même famille que l'onglet
    Statistiques qu'il remplace)."""

    def get(self, request, project_id):
        project = get_object_or_404(contributor_projects(request.user), id=project_id)
        entries = services.get_dashboard(actor=request.user, scope="projet", project=project)
        return Response(_serialize_dashboard(entries))

    def post(self, request, project_id):
        project = get_object_or_404(contributor_projects(request.user), id=project_id)
        serializer = DashboardWidgetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        widget = services.create_widget(actor=request.user, scope="projet", project=project, **serializer.validated_data)
        entry = {"widget": widget, "data": services.compute_widget_data(actor=request.user, widget=widget)}
        return Response(serialize_widget_entry(entry), status=201)


@extend_schema(responses=OpenApiTypes.OBJECT)
class GlobalDashboardView(_DashboardExceptionMixin, APIView):
    """Dashboard personnalisable de l'écran Statistiques global."""

    def get(self, request):
        entries = services.get_dashboard(actor=request.user, scope="global", project=None)
        return Response(_serialize_dashboard(entries))

    def post(self, request):
        serializer = DashboardWidgetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        widget = services.create_widget(actor=request.user, scope="global", project=None, **serializer.validated_data)
        entry = {"widget": widget, "data": services.compute_widget_data(actor=request.user, widget=widget)}
        return Response(serialize_widget_entry(entry), status=201)


@extend_schema(responses=OpenApiTypes.OBJECT)
class DashboardWidgetDetailView(_DashboardExceptionMixin, APIView):
    """`owner=request.user` dans le queryset, pas une vérification a
    posteriori : un widget d'un autre utilisateur renvoie 404, pas 403 —
    cohérent avec le reste du repo (ex. historique d'activité)."""

    def _widget(self, request, widget_id):
        return get_object_or_404(DashboardWidget.objects, id=widget_id, owner=request.user)

    def patch(self, request, widget_id):
        widget = self._widget(request, widget_id)
        serializer = DashboardWidgetPositionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        widget = services.update_widget_position(actor=request.user, widget=widget, **serializer.validated_data)
        return Response({"id": str(widget.id), "x": widget.x, "y": widget.y, "w": widget.w, "h": widget.h})

    def delete(self, request, widget_id):
        widget = self._widget(request, widget_id)
        services.remove_widget(actor=request.user, widget=widget)
        return Response(status=204)


@extend_schema(responses=OpenApiTypes.OBJECT)
class DashboardCatalogView(_DashboardExceptionMixin, APIView):
    """Catalogue des widgets disponibles, filtré selon les droits de
    l'utilisateur courant sur la portée demandée — `?scope=projet&project_id=`
    ou `?scope=global`."""

    def get(self, request):
        scope = request.query_params.get("scope")
        if scope not in ("projet", "global"):
            return Response({"detail": "Paramètre « scope » invalide (projet ou global attendu)."}, status=400)

        project = None
        if scope == "projet":
            project_id = request.query_params.get("project_id")
            if not project_id:
                return Response({"detail": "Paramètre « project_id » requis pour la portée projet."}, status=400)
            project = get_object_or_404(contributor_projects(request.user), id=project_id)

        return Response(services.get_catalog(actor=request.user, scope=scope, project=project))
