from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.projects.services import accessible_projects

from .models import BudgetLine
from .serializers import BudgetLineCreateSerializer, BudgetLineSerializer, BudgetSummarySerializer
from .services import (
    BudgetPermissionError,
    BudgetValidationError,
    add_budget_line,
    get_budget_lines,
    get_budget_summary_for_manager,
    remove_budget_line,
)


class BudgetLineViewSet(viewsets.GenericViewSet):
    # Schéma/introspection uniquement — les endpoints réels sont tous des
    # `@action` scopées par projet (voir docs/modeles-et-api.md), pas de
    # list()/retrieve() générique sur ce ViewSet.
    queryset = BudgetLine.objects.all()
    serializer_class = BudgetLineSerializer

    def get_queryset(self):
        # Scope `self.get_object()` (utilisé par `remove`) aux lignes des
        # projets accessibles à l'acteur — 404 plutôt qu'un 403 qui
        # révélerait l'existence d'une ligne sur un projet hors de portée,
        # cohérent avec "Scoping des listes par appartenance".
        return BudgetLine.objects.filter(project__in=accessible_projects(self.request.user))

    @action(detail=False, methods=["get", "post"], url_path="projects/(?P<project_id>[^/.]+)/lines")
    def lines(self, request, project_id=None):
        # Résolu via `accessible_projects` : 404 (pas 403) si l'acteur n'a
        # pas de `ProjectMembership` sur ce projet, cohérent avec "Scoping
        # des listes par appartenance" — la garde de rôle fine (membre vs
        # chef de projet) vit ensuite dans le service.
        project = get_object_or_404(accessible_projects(request.user), pk=project_id)

        if request.method == "GET":
            try:
                lines = get_budget_lines(actor=request.user, project=project)
            except BudgetPermissionError as exc:
                return Response({"detail": str(exc)}, status=403)
            return Response(self.get_serializer(lines, many=True).data)

        serializer = BudgetLineCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            line = add_budget_line(actor=request.user, project=project, **serializer.validated_data)
        except BudgetPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except BudgetValidationError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(self.get_serializer(line).data, status=201)

    @action(detail=True, methods=["post"], url_path="remove")
    def remove(self, request, pk=None):
        line = self.get_object()
        try:
            remove_budget_line(actor=request.user, line=line)
        except BudgetPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        return Response(self.get_serializer(line).data)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        try:
            summary = get_budget_summary_for_manager(actor=request.user)
        except BudgetPermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        return Response(BudgetSummarySerializer(summary, many=True, context=self.get_serializer_context()).data)
