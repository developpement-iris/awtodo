from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.services import accessible_projects

from . import services
from .models import (
    CalendarEvent,
    CalendarShare,
    EventParticipant,
    ProjectPlanningEntry,
    ScheduledBlock,
)
from .serializers import (
    BlockCreateSerializer,
    BlockUpdateSerializer,
    EventCreateSerializer,
    EventUpdateSerializer,
    ParticipantAddSerializer,
    ProjectEntryCreateSerializer,
    ProjectEntryUpdateSerializer,
    RespondSerializer,
    ShareCreateSerializer,
)


class _PlanningExceptionMixin:
    """Traduit les exceptions du service en codes HTTP (comme
    `apps.documentation.views`) — les actions n'ont donc pas de try/except."""

    def handle_exception(self, exc):
        if isinstance(exc, services.PlanningPermissionError):
            return Response({"detail": str(exc)}, status=403)
        if isinstance(exc, services.PlanningValidationError):
            return Response({"detail": str(exc)}, status=400)
        return super().handle_exception(exc)


def _aware(dt):
    if dt is None:
        return None
    return dt if timezone.is_aware(dt) else timezone.make_aware(dt)


def _window_from_query(request):
    raw_start = request.query_params.get("from")
    raw_end = request.query_params.get("to")
    if not raw_start or not raw_end:
        raise services.PlanningValidationError("Les paramètres « from » et « to » sont obligatoires.")
    start = _aware(parse_datetime(raw_start))
    end = _aware(parse_datetime(raw_end))
    if start is None or end is None:
        raise services.PlanningValidationError("Dates « from » / « to » invalides (format ISO 8601 attendu).")
    if end <= start:
        raise services.PlanningValidationError("« to » doit être postérieur à « from ».")
    if end - start > timedelta(days=services.MAX_WINDOW_DAYS):
        raise services.PlanningValidationError(
            f"La fenêtre ne peut pas dépasser {services.MAX_WINDOW_DAYS} jours."
        )
    return start, end


def _id_list(request, name):
    raw = request.query_params.get(name)
    return [part for part in raw.split(",") if part] if raw else None


@extend_schema(responses=OpenApiTypes.OBJECT)
class CalendarView(_PlanningExceptionMixin, APIView):
    def get(self, request):
        start, end = _window_from_query(request)
        data = services.get_calendar(
            actor=request.user,
            window_start=start,
            window_end=end,
            owner_ids=_id_list(request, "owners"),
            project_ids=_id_list(request, "projects"),
        )
        return Response(data)


@extend_schema(responses=OpenApiTypes.OBJECT)
class CalendarEventViewSet(_PlanningExceptionMixin, viewsets.GenericViewSet):
    serializer_class = EventCreateSerializer

    def get_queryset(self):
        user = self.request.user
        from django.db.models import Q

        return (
            CalendarEvent.all_objects.filter(
                Q(owner=user) | Q(participants__user=user, participants__status="active")
            )
            .distinct()
            .select_related("owner")
            .prefetch_related("participants__user")
        )

    def list(self, request):
        events = self.get_queryset()
        return Response([services._event_detail_dict(e, actor=request.user) for e in events])

    def retrieve(self, request, pk=None):
        event = self.get_object()
        return Response(services._event_detail_dict(event, actor=request.user))

    def create(self, request):
        serializer = EventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = services.create_event(actor=request.user, **serializer.validated_data)
        return Response(services._event_detail_dict(event, actor=request.user), status=201)

    def partial_update(self, request, pk=None):
        event = self.get_object()
        serializer = EventUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = services.update_event(actor=request.user, event=event, **serializer.validated_data)
        return Response(services._event_detail_dict(event, actor=request.user))

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        event = self.get_object()
        services.cancel_event(actor=request.user, event=event)
        return Response(status=204)

    @action(detail=True, methods=["post"], url_path="participants")
    def add_participant(self, request, pk=None):
        event = self.get_object()
        serializer = ParticipantAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.add_participant(
            actor=request.user, event=event, user=serializer.validated_data["user"]
        )
        return Response(services._event_detail_dict(event, actor=request.user), status=201)

    @action(detail=True, methods=["delete"], url_path=r"participants/(?P<participant_id>[^/.]+)")
    def remove_participant(self, request, pk=None, participant_id=None):
        event = self.get_object()
        participant = get_object_or_404(
            EventParticipant.all_objects, id=participant_id, event=event
        )
        services.remove_participant(actor=request.user, participant=participant)
        return Response(status=204)

    @action(detail=True, methods=["post"], url_path="respond")
    def respond(self, request, pk=None):
        event = self.get_object()
        serializer = RespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.respond_to_event(
            actor=request.user, event=event, response=serializer.validated_data["response"]
        )
        return Response(services._event_detail_dict(event, actor=request.user))


@extend_schema(responses=OpenApiTypes.OBJECT)
class ScheduledBlockViewSet(_PlanningExceptionMixin, viewsets.GenericViewSet):
    serializer_class = BlockCreateSerializer

    def get_queryset(self):
        return ScheduledBlock.all_objects.filter(owner=self.request.user).select_related(
            "task", "task__project", "incident", "incident__project"
        )

    def list(self, request):
        return Response([services._block_dict(b) for b in self.get_queryset()])

    def create(self, request):
        serializer = BlockCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        block = services.create_block(actor=request.user, **serializer.validated_data)
        return Response(services._block_dict(block), status=201)

    def partial_update(self, request, pk=None):
        block = self.get_object()
        serializer = BlockUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        block = services.update_block(actor=request.user, block=block, **serializer.validated_data)
        return Response(services._block_dict(block))

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        block = self.get_object()
        services.cancel_block(actor=request.user, block=block)
        return Response(status=204)


@extend_schema(responses=OpenApiTypes.OBJECT)
class CalendarShareViewSet(_PlanningExceptionMixin, viewsets.GenericViewSet):
    serializer_class = ShareCreateSerializer

    def get_queryset(self):
        from django.db.models import Q

        user = self.request.user
        return CalendarShare.all_objects.filter(Q(owner=user) | Q(grantee=user))

    def list(self, request):
        return Response(services.list_shares(actor=request.user))

    def create(self, request):
        serializer = ShareCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        share = services.create_share(actor=request.user, grantee=serializer.validated_data["grantee"])
        return Response(services._share_dict(share), status=201)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        share = self.get_object()
        services.revoke_share(actor=request.user, share=share)
        return Response(status=204)


@extend_schema(responses=OpenApiTypes.OBJECT)
class ProjectPlanningViewSet(_PlanningExceptionMixin, viewsets.GenericViewSet):
    lookup_field = "project_id"
    queryset = ProjectPlanningEntry.objects.none()
    serializer_class = ProjectEntryCreateSerializer

    def _project(self, request, project_id):
        return get_object_or_404(accessible_projects(request.user), id=project_id)

    def _entry(self, project, entry_id):
        return get_object_or_404(ProjectPlanningEntry.all_objects, id=entry_id, project=project)

    @action(detail=True, methods=["get", "post"], url_path="entries")
    def entries(self, request, project_id=None):
        project = self._project(request, project_id)
        if request.method == "GET":
            start, end = _window_from_query(request)
            return Response(
                services.list_project_entries(
                    actor=request.user, project=project, window_start=start, window_end=end
                )
            )
        serializer = ProjectEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = services.create_project_entry(
            actor=request.user, project=project, **serializer.validated_data
        )
        return Response(
            services._project_entry_occurrence_dict(
                {"source": entry, "occurrence_start": entry.start, "start": entry.start, "end": entry.end},
                actor=request.user,
            ),
            status=201,
        )

    @action(detail=True, methods=["patch"], url_path=r"entries/(?P<entry_id>[^/.]+)")
    def entry_detail(self, request, project_id=None, entry_id=None):
        project = self._project(request, project_id)
        entry = self._entry(project, entry_id)
        serializer = ProjectEntryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = services.update_project_entry(
            actor=request.user, entry=entry, **serializer.validated_data
        )
        return Response(
            services._project_entry_occurrence_dict(
                {"source": entry, "occurrence_start": entry.start, "start": entry.start, "end": entry.end},
                actor=request.user,
            )
        )

    @action(detail=True, methods=["post"], url_path=r"entries/(?P<entry_id>[^/.]+)/cancel")
    def entry_cancel(self, request, project_id=None, entry_id=None):
        project = self._project(request, project_id)
        entry = self._entry(project, entry_id)
        services.cancel_project_entry(actor=request.user, entry=entry)
        return Response(status=204)
