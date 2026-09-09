from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.common.views import ListOnlyFilterMixin
from apps.projects.services import accessible_projects

from .filters import TaskFilterSet
from .models import Task
from .serializers import (
    GlobalTaskStatsSerializer,
    ProjectUserStatsSerializer,
    TaskCommentCreateSerializer,
    TaskCommentSerializer,
    TaskCreateSerializer,
    TaskDetailSerializer,
    TaskInsightsSerializer,
    TaskSerializer,
)
from .services import (
    InvalidTransitionError,
    TaskPermissionError,
    add_comment,
    assign_task,
    claim_task,
    complete_task,
    create_task,
    get_assigned_tasks_for_admin,
    get_global_task_stats,
    get_project_task_insights,
    get_project_user_stats,
    reject_task,
    rename_task,
    start_task,
    update_task_description,
    update_task_estimated_hours,
    validate_task,
)


def _resolve_assignee(user_id):
    if not user_id:
        return None, None
    try:
        return User.objects.get(pk=user_id), None
    except (User.DoesNotExist, ValueError, TypeError):
        return None, Response({"detail": "Utilisateur introuvable."}, status=400)


class TaskViewSet(ListOnlyFilterMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    # Schéma/introspection uniquement — la portée réelle vient de
    # `get_queryset()` (voir CLAUDE.md > "Scoping des listes par appartenance").
    queryset = Task.objects.active().select_related("project", "assignee")
    serializer_class = TaskSerializer
    filterset_class = TaskFilterSet

    def get_serializer_class(self):
        if self.action == "retrieve":
            return TaskDetailSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        # `all_objects`, pas `.active()` : le filtre par défaut du statut
        # (voir "Filtre d'état généralisé", docs/modeles-et-api.md) est du
        # ressort de `TaskFilterSet.filter_status`, pas du queryset de base —
        # sinon une tâche archivée/rejetée resterait invisible même en la
        # demandant explicitement via `?status=archivee`.
        return (
            Task.all_objects.filter(project__in=accessible_projects(self.request.user))
            .select_related("project", "assignee")
        )

    def create(self, request, *args, **kwargs):
        serializer = TaskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            task = create_task(actor=request.user, **serializer.validated_data)
        except TaskPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except InvalidTransitionError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(task).data, status=201)

    @action(detail=False, methods=["get"], url_path="assigned-to/(?P<user_id>[^/.]+)")
    def assigned_to(self, request, user_id=None):
        # Fiche utilisateur (écran Administration > Membres) — voir
        # docs/organisation-et-comptes.md. Contourne délibérément le scoping
        # par appartenance habituel (`get_queryset()`), la garde vit dans
        # `get_assigned_tasks_for_admin` elle-même, pas ici.
        try:
            target_user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "Utilisateur introuvable."}, status=404)

        try:
            tasks = get_assigned_tasks_for_admin(actor=request.user, target_user=target_user)
        except TaskPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)

        return Response(TaskSerializer(tasks, many=True, context=self.get_serializer_context()).data)

    @action(detail=False, methods=["get"], url_path="project-stats/(?P<project_id>[^/.]+)")
    def project_stats(self, request, project_id=None):
        # Résolu via `accessible_projects` (pas `Project.objects.all()`) pour
        # 404 sur un projet hors de la portée par appartenance de l'acteur,
        # cohérent avec "Scoping des listes par appartenance" — la garde de
        # rôle (membre vs chef de projet) vit ensuite dans le service.
        project = get_object_or_404(accessible_projects(request.user), pk=project_id)

        try:
            stats = get_project_user_stats(actor=request.user, project=project)
        except TaskPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)

        return Response(ProjectUserStatsSerializer(stats, many=True, context=self.get_serializer_context()).data)

    @action(detail=False, methods=["get"], url_path="project-insights/(?P<project_id>[^/.]+)")
    def project_insights(self, request, project_id=None):
        project = get_object_or_404(accessible_projects(request.user), pk=project_id)

        try:
            insights = get_project_task_insights(actor=request.user, project=project)
        except TaskPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)

        return Response(TaskInsightsSerializer(insights, context=self.get_serializer_context()).data)

    @action(detail=False, methods=["get"], url_path="global-stats")
    def global_stats(self, request):
        try:
            stats = get_global_task_stats(actor=request.user)
        except TaskPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)

        return Response(GlobalTaskStatsSerializer(stats, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def rename(self, request, pk=None):
        task = self.get_object()

        try:
            rename_task(actor=request.user, task=task, title=request.data.get("title"))
        except TaskPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except InvalidTransitionError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"], url_path="update-description")
    def update_description(self, request, pk=None):
        task = self.get_object()

        try:
            update_task_description(actor=request.user, task=task, description=request.data.get("description", ""))
        except TaskPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)

        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"], url_path="update-estimated-hours")
    def update_estimated_hours(self, request, pk=None):
        task = self.get_object()

        try:
            update_task_estimated_hours(
                actor=request.user, task=task, estimated_hours=request.data.get("estimated_hours")
            )
        except TaskPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except InvalidTransitionError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def validate(self, request, pk=None):
        task = self.get_object()
        assignee, error = _resolve_assignee(request.data.get("assignee"))
        if error:
            return error

        try:
            validate_task(actor=request.user, task=task, assignee=assignee)
        except TaskPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except InvalidTransitionError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        task = self.get_object()

        try:
            reject_task(
                actor=request.user,
                task=task,
                rejection_reason=request.data.get("rejection_reason"),
            )
        except TaskPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except InvalidTransitionError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def claim(self, request, pk=None):
        task = self.get_object()

        try:
            claim_task(actor=request.user, task=task)
        except TaskPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except InvalidTransitionError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        task = self.get_object()
        assignee, error = _resolve_assignee(request.data.get("assignee"))
        if error:
            return error

        try:
            assign_task(actor=request.user, task=task, assignee=assignee)
        except TaskPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except InvalidTransitionError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        task = self.get_object()

        try:
            start_task(actor=request.user, task=task)
        except TaskPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except InvalidTransitionError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        task = self.get_object()

        try:
            complete_task(actor=request.user, task=task, time_spent=request.data.get("time_spent"))
        except TaskPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except InvalidTransitionError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"], url_path="comments")
    def comments(self, request, pk=None):
        task = self.get_object()
        serializer = TaskCommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            comment = add_comment(actor=request.user, task=task, **serializer.validated_data)
        except TaskPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except InvalidTransitionError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(TaskCommentSerializer(comment).data, status=201)
