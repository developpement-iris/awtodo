from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.views import ListOnlyFilterMixin
from apps.projects.services import accessible_projects

from .filters import IncidentFilterSet
from .models import Incident
from .serializers import (
    IncidentAssignProjectSerializer,
    IncidentCommentCreateSerializer,
    IncidentCommentSerializer,
    IncidentCreateSerializer,
    IncidentDetailSerializer,
    IncidentPriorityUpdateSerializer,
    IncidentSerializer,
)
from .services import (
    IncidentPermissionError,
    IncidentValidationError,
    accessible_inbox_teams,
    add_comment,
    archive_incident,
    assign_incident_to_project,
    claim_incident,
    create_incident,
    resolve_incident,
    start_incident,
    update_incident_description,
    update_incident_priority,
)


class IncidentViewSet(ListOnlyFilterMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    # Schéma/introspection uniquement — la portée réelle vient de
    # `get_queryset()` (voir CLAUDE.md > "Scoping des listes par appartenance").
    queryset = Incident.objects.active().select_related("project", "team")
    serializer_class = IncidentSerializer
    filterset_class = IncidentFilterSet

    def get_queryset(self):
        # `all_objects`, pas `.active()` — voir TaskViewSet.get_queryset()
        # pour la même raison (le filtre par défaut vit dans le FilterSet).
        base = Incident.all_objects.select_related("project", "team")
        if self.action == "list":
            # Liste "par projet" par défaut : les incidents non-affectés
            # (team-only) ne s'y mélangent jamais — ils ne sont listés que via
            # `inbox()`, qui a son propre scoping dédié.
            return base.filter(project__in=accessible_projects(self.request.user))
        # `retrieve` et les actions de détail (start/resolve/archive/comments/
        # assign-project) doivent aussi résoudre un incident non-affecté pour
        # un membre autorisé de son groupe — sinon `self.get_object()` 404
        # systématiquement sur tout incident de la boîte de réception. La
        # décision d'autorisation elle-même reste dans les fonctions de garde
        # de `services.py` (403) ; cette portée ne gère que l'existence (404),
        # même convention que `accessible_projects`.
        return base.filter(
            Q(project__in=accessible_projects(self.request.user))
            | Q(project__isnull=True, team__in=accessible_inbox_teams(self.request.user))
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return IncidentDetailSerializer
        return super().get_serializer_class()

    def create(self, request, *args, **kwargs):
        serializer = IncidentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Un compte marqué `is_service_account` (voir apps.accounts.models.User)
        # simule le futur appel système de l'intégration ticketing : `actor=None`
        # fait délibérément sauter la contrainte de groupe/projet dans
        # `create_incident`, contrairement à un appel identifié normalement.
        actor = None if getattr(request.user, "is_service_account", False) else request.user

        try:
            incident = create_incident(actor=actor, **serializer.validated_data)
        except IncidentPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except IncidentValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(incident).data, status=201)

    @action(detail=False, methods=["get"])
    def inbox(self, request):
        queryset = Incident.all_objects.filter(
            project__isnull=True, team__in=accessible_inbox_teams(request.user)
        ).select_related("team")
        queryset = self.filter_queryset(queryset)
        return Response(self.get_serializer(queryset, many=True).data)

    @action(detail=True, methods=["post"], url_path="assign-project")
    def assign_project(self, request, pk=None):
        incident = self.get_object()
        serializer = IncidentAssignProjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            assign_incident_to_project(actor=request.user, incident=incident, **serializer.validated_data)
        except IncidentPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except IncidentValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(incident).data)

    @action(detail=True, methods=["post"])
    def claim(self, request, pk=None):
        incident = self.get_object()

        try:
            claim_incident(actor=request.user, incident=incident)
        except IncidentPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)

        return Response(self.get_serializer(incident).data)

    @action(detail=True, methods=["post"], url_path="update-priority")
    def update_priority(self, request, pk=None):
        incident = self.get_object()
        serializer = IncidentPriorityUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            update_incident_priority(actor=request.user, incident=incident, **serializer.validated_data)
        except IncidentPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)

        return Response(self.get_serializer(incident).data)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        incident = self.get_object()

        try:
            start_incident(actor=request.user, incident=incident)
        except IncidentPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except IncidentValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(incident).data)

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        incident = self.get_object()

        try:
            resolve_incident(actor=request.user, incident=incident)
        except IncidentPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except IncidentValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(incident).data)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        incident = self.get_object()

        try:
            archive_incident(actor=request.user, incident=incident)
        except IncidentPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except IncidentValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(incident).data)

    @action(detail=True, methods=["post"], url_path="update-description")
    def update_description(self, request, pk=None):
        incident = self.get_object()

        try:
            update_incident_description(
                actor=request.user, incident=incident, description=request.data.get("description", "")
            )
        except IncidentPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)

        return Response(self.get_serializer(incident).data)

    @action(detail=True, methods=["post"], url_path="comments")
    def comments(self, request, pk=None):
        incident = self.get_object()
        serializer = IncidentCommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            comment = add_comment(actor=request.user, incident=incident, **serializer.validated_data)
        except IncidentPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except IncidentValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(IncidentCommentSerializer(comment).data, status=201)
