from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.services import contributor_projects

from . import services
from .models import CommunicationChannel
from .serializers import (
    CommunicationChannelCreateSerializer,
    CommunicationChannelSerializer,
    CommunicationChannelUpdateSerializer,
    CommunicationComposeSerializer,
    CommunicationMessageSerializer,
    O365ConnectionSerializer,
)


class _CommunicationExceptionMixin:
    """Traduit les exceptions de service en codes HTTP (comme
    apps.planning / apps.documentation)."""

    def handle_exception(self, exc):
        if isinstance(exc, services.CommunicationPermissionError):
            return Response({"detail": str(exc)}, status=403)
        if isinstance(exc, services.CommunicationValidationError):
            return Response({"detail": str(exc)}, status=400)
        return super().handle_exception(exc)


@extend_schema(responses=O365ConnectionSerializer)
class O365ConnectionView(_CommunicationExceptionMixin, APIView):
    """Connexion Office 365 de l'organisation de l'utilisateur courant.
    Lecture ouverte à tout membre de l'organisation ; écriture réservée à un
    admin d'organisation (garde dans le service)."""

    def get(self, request):
        connection = services.get_o365_connection(request.user.organisation)
        return Response(O365ConnectionSerializer(connection).data)

    def put(self, request):
        serializer = O365ConnectionSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        connection = services.update_o365_connection(
            actor=request.user, organisation=request.user.organisation, **serializer.validated_data
        )
        return Response(O365ConnectionSerializer(connection).data)


@extend_schema(responses=OpenApiTypes.OBJECT)
class ProjectCommunicationViewSet(_CommunicationExceptionMixin, viewsets.GenericViewSet):
    lookup_field = "project_id"
    queryset = CommunicationChannel.objects.none()
    serializer_class = CommunicationChannelSerializer

    def _project(self, request, project_id):
        # `contributor_projects` : un lecteur du projet n'a pas accès à
        # l'onglet Communication (cohérent avec Incidents/Planning/Budget).
        return get_object_or_404(contributor_projects(request.user), id=project_id)

    @action(detail=True, methods=["get", "post"], url_path="channels")
    def channels(self, request, project_id=None):
        project = self._project(request, project_id)
        if request.method == "GET":
            return Response(
                CommunicationChannelSerializer(services.list_channels(project), many=True).data
            )
        serializer = CommunicationChannelCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        channel = services.create_channel(actor=request.user, project=project, **serializer.validated_data)
        return Response(CommunicationChannelSerializer(channel).data, status=201)

    @action(detail=True, methods=["patch", "delete"], url_path=r"channels/(?P<channel_id>[^/.]+)")
    def channel_detail(self, request, project_id=None, channel_id=None):
        project = self._project(request, project_id)
        channel = get_object_or_404(CommunicationChannel.all_objects, id=channel_id, project=project)
        if request.method == "DELETE":
            services.archive_channel(actor=request.user, channel=channel)
            return Response(status=204)
        serializer = CommunicationChannelUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        channel = services.update_channel(actor=request.user, channel=channel, **serializer.validated_data)
        return Response(CommunicationChannelSerializer(channel).data)

    @action(detail=True, methods=["get", "post"], url_path="messages")
    def messages(self, request, project_id=None):
        project = self._project(request, project_id)
        if request.method == "GET":
            return Response(
                CommunicationMessageSerializer(services.list_messages(project), many=True).data
            )
        serializer = CommunicationComposeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = services.compose_message(
            actor=request.user,
            project=project,
            subject=serializer.validated_data["subject"],
            body=serializer.validated_data["body"],
            channel_ids=serializer.validated_data["channel_ids"],
        )
        return Response(CommunicationMessageSerializer(message).data, status=201)
