import csv

from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import Team
from apps.projects.models import Project
from apps.projects.services import accessible_projects

from . import catalog, results, services
from .answers import AnswerError
from .definitions import EvaluationPermissionError, EvaluationValidationError
from .models import CatalogQuestion, ClientResponse, EvaluationSheet, SheetQuestion
from .throttles import EvaluationSubmitThrottle
from .schema import catalog_schema, public_get_schema, public_submit_schema, sheet_schema
from .serializers import (
    AnswersSerializer,
    ResponseItemSerializer,
    SheetResultsSerializer,
    CatalogQuestionCreateSerializer,
    CatalogQuestionSerializer,
    MoveSerializer,
    PublicSubmitSerializer,
    QuestionDefinitionInputSerializer,
    QuestionDefinitionUpdateSerializer,
    SheetCreateSerializer,
    SheetDetailSerializer,
    SheetQuestionSerializer,
    SheetSummarySerializer,
    SheetUpdateSerializer,
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


@sheet_schema
class SheetViewSet(EvaluationErrorsMixin, viewsets.GenericViewSet):
    """Fiches d'évaluation d'un projet. Toutes les règles d'accès vivent dans
    `services` : un objet hors de portée donne 403, comme le catalogue."""

    queryset = EvaluationSheet.all_objects.select_related("project")
    serializer_class = SheetDetailSerializer

    def _detail(self, sheet, status_code=200):
        sheet.refresh_from_db()
        return Response(SheetDetailSerializer(sheet, context={"request": self.request}).data, status=status_code)

    def _question(self, sheet, question_id):
        try:
            return get_object_or_404(SheetQuestion.all_objects, pk=question_id, sheet=sheet)
        except (ValueError, ValidationError):
            raise Http404

    def list(self, request):
        project_id = request.query_params.get("project")
        if not project_id:
            raise EvaluationValidationError("Paramètre `project` requis.")
        try:
            project = get_object_or_404(Project.all_objects, pk=project_id)
        except (ValueError, ValidationError):
            raise EvaluationValidationError("Projet invalide.")
        sheets = services.list_sheets(actor=request.user, project=project)
        return Response(SheetSummarySerializer(sheets, many=True).data)

    def create(self, request):
        serializer = SheetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        project = get_object_or_404(Project.all_objects, pk=data.pop("project"))
        sheet = services.create_sheet(actor=request.user, project=project, **data)
        return self._detail(sheet, status_code=201)

    def retrieve(self, request, pk=None):
        return self._detail(services.get_sheet(actor=request.user, sheet=self.get_object()))

    def partial_update(self, request, pk=None):
        serializer = SheetUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        sheet = services.update_sheet(actor=request.user, sheet=self.get_object(), **serializer.validated_data)
        return self._detail(sheet)

    @action(detail=True, methods=["post"], url_path="questions")
    def add_question(self, request, pk=None):
        serializer = QuestionDefinitionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = services.add_sheet_question(
            actor=request.user, sheet=self.get_object(), **serializer.validated_data
        )
        return Response(SheetQuestionSerializer(question).data, status=201)

    @action(detail=True, methods=["patch"], url_path=r"questions/(?P<question_id>[^/.]+)")
    def question_detail(self, request, pk=None, question_id=None):
        serializer = QuestionDefinitionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        question = services.update_sheet_question(
            actor=request.user, question=self._question(self.get_object(), question_id), **serializer.validated_data
        )
        return Response(SheetQuestionSerializer(question).data)

    @action(detail=True, methods=["post"], url_path=r"questions/(?P<question_id>[^/.]+)/archive")
    def question_archive(self, request, pk=None, question_id=None):
        question = services.archive_sheet_question(
            actor=request.user, question=self._question(self.get_object(), question_id)
        )
        return Response(SheetQuestionSerializer(question).data)

    @action(detail=True, methods=["post"], url_path=r"questions/(?P<question_id>[^/.]+)/move")
    def question_move(self, request, pk=None, question_id=None):
        serializer = MoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = services.move_sheet_question(
            actor=request.user, question=self._question(self.get_object(), question_id),
            direction=serializer.validated_data["direction"],
        )
        return Response(SheetQuestionSerializer(question).data)

    def _lifecycle(self, fn):
        return self._detail(fn(actor=self.request.user, sheet=self.get_object()))

    @action(detail=True, methods=["post"])
    def open(self, request, pk=None):
        return self._lifecycle(services.open_sheet)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        return self._lifecycle(services.close_sheet)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        return self._lifecycle(services.reopen_sheet)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        return self._lifecycle(services.archive_sheet)

    @action(detail=True, methods=["post"], url_path="rotate-link")
    def rotate_link(self, request, pk=None):
        return self._lifecycle(services.rotate_sheet_link)

    @action(detail=True, methods=["put"])
    def internal(self, request, pk=None):
        serializer = AnswersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sheet = self.get_object()
        services.save_internal_evaluation(actor=request.user, sheet=sheet, answers=serializer.validated_data["answers"])
        return self._detail(sheet)

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        sheet = services.get_sheet(actor=request.user, sheet=self.get_object())
        return Response(SheetResultsSerializer(results.sheet_results(sheet)).data)

    @action(detail=True, methods=["get"])
    def responses(self, request, pk=None):
        items = services.list_responses(actor=request.user, sheet=self.get_object())
        return Response(ResponseItemSerializer(items, many=True).data)

    def _response(self, sheet, response_id):
        try:
            return get_object_or_404(ClientResponse.all_objects, pk=response_id, sheet=sheet)
        except (ValueError, ValidationError):
            raise Http404

    def _responses_after(self, sheet):
        return Response(ResponseItemSerializer(services.list_responses(actor=self.request.user, sheet=sheet), many=True).data)

    @action(detail=True, methods=["post"], url_path=r"responses/(?P<response_id>[^/.]+)/discard")
    def response_discard(self, request, pk=None, response_id=None):
        sheet = self.get_object()
        services.discard_response(actor=request.user, response=self._response(sheet, response_id))
        return self._responses_after(sheet)

    @action(detail=True, methods=["post"], url_path=r"responses/(?P<response_id>[^/.]+)/restore")
    def response_restore(self, request, pk=None, response_id=None):
        sheet = self.get_object()
        services.restore_response(actor=request.user, response=self._response(sheet, response_id))
        return self._responses_after(sheet)

    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        sheet = services.get_sheet(actor=request.user, sheet=self.get_object())
        header, rows = results.export_csv_rows(sheet)
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="evaluation-{slugify(sheet.title) or sheet.id}.csv"'
        response.write("\ufeff")  # BOM : accents corrects à l'ouverture dans Excel
        writer = csv.writer(response, delimiter=";")
        writer.writerow(header)
        writer.writerows(rows)
        return response


class PublicEvaluationView(EvaluationErrorsMixin, APIView):
    """Formulaire client public — 2ᵉ exception au garde-fou « connexion
    obligatoire » (CLAUDE.md > Stack technique > Auth). N'expose que les
    questions client d'une fiche ouverte."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @public_get_schema
    def get(self, request, token):
        data = services.get_public_sheet(token)
        if data is None:
            raise Http404
        return Response(data)


class PublicEvaluationSubmitView(EvaluationErrorsMixin, APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, EvaluationSubmitThrottle]
    throttle_scope = "evaluation_submit"

    @public_submit_schema
    def post(self, request, token):
        serializer = PublicSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            response = services.submit_client_response(token=token, **serializer.validated_data)
        except services.SheetClosedError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_410_GONE)
        if response is None:
            raise Http404
        return Response({"detail": "Merci, votre réponse a bien été enregistrée."}, status=201)
