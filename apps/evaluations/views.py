from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import Team
from apps.projects.services import accessible_projects

from . import catalog
from .answers import AnswerError
from .definitions import EvaluationPermissionError, EvaluationValidationError
from .models import CatalogQuestion
from .schema import catalog_schema
from .serializers import (
    CatalogQuestionCreateSerializer,
    CatalogQuestionSerializer,
    MoveSerializer,
    QuestionDefinitionUpdateSerializer,
)


class EvaluationErrorsMixin:
    """Erreurs de service -> 403 / 400 (`question` : id de la question fautive)."""

    def handle_exception(self, exc):
        if isinstance(exc, EvaluationPermissionError):
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        if isinstance(exc, AnswerError):
            return Response(
                {"detail": exc.message, "question": exc.question_id}, status=status.HTTP_400_BAD_REQUEST
            )
        if isinstance(exc, EvaluationValidationError):
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return super().handle_exception(exc)


@catalog_schema
class CatalogQuestionViewSet(EvaluationErrorsMixin, viewsets.GenericViewSet):
    """Catalogue de questions génériques. Comme pour les types de tâche, un
    `project` rattaché à un groupe renvoie vers le catalogue du groupe."""

    queryset = CatalogQuestion.all_objects.all()
    serializer_class = CatalogQuestionSerializer

    def _resolve_scope(self, team_id, project_id):
        try:
            if project_id:
                project = get_object_or_404(accessible_projects(self.request.user), pk=project_id)
                return catalog.catalog_scope(project)
            if team_id:
                return get_object_or_404(Team.objects.all(), pk=team_id)
        except (ValueError, ValidationError):
            raise EvaluationValidationError("Portée invalide.")
        raise EvaluationValidationError("Paramètre `team` ou `project` requis.")

    @staticmethod
    def _scope_payload(scope):
        is_team = isinstance(scope, Team)
        return {"kind": "team" if is_team else "project", "id": str(scope.id), "name": scope.name}

    def list(self, request):
        params = request.query_params
        scope = self._resolve_scope(params.get("team"), params.get("project"))
        questions = catalog.list_catalog(
            actor=request.user, scope=scope, include_archived=params.get("include_archived") in ("1", "true")
        )
        return Response({
            "scope": self._scope_payload(scope),
            "can_manage": catalog.can_manage_catalog(request.user, scope),
            "questions": CatalogQuestionSerializer(questions, many=True).data,
        })

    def create(self, request):
        serializer = CatalogQuestionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        scope = self._resolve_scope(data.pop("team"), data.pop("project"))
        question = catalog.create_catalog_question(actor=request.user, scope=scope, **data)
        return Response(CatalogQuestionSerializer(question).data, status=201)

    def partial_update(self, request, pk=None):
        serializer = QuestionDefinitionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        question = catalog.update_catalog_question(
            actor=request.user, question=self.get_object(), **serializer.validated_data
        )
        return Response(CatalogQuestionSerializer(question).data)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        question = catalog.archive_catalog_question(actor=request.user, question=self.get_object())
        return Response(CatalogQuestionSerializer(question).data)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        question = catalog.restore_catalog_question(actor=request.user, question=self.get_object())
        return Response(CatalogQuestionSerializer(question).data)

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        serializer = MoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = catalog.move_catalog_question(
            actor=request.user, question=self.get_object(), direction=serializer.validated_data["direction"]
        )
        return Response(CatalogQuestionSerializer(question).data)
