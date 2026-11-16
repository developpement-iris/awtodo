from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import CatalogQuestionViewSet, PublicEvaluationSubmitView, PublicEvaluationView, SheetViewSet

router = SimpleRouter(trailing_slash=True)
router.register("catalog", CatalogQuestionViewSet, basename="evaluation-catalog")
router.register("sheets", SheetViewSet, basename="evaluation-sheet")

urlpatterns = [
    path("public/<str:token>/", PublicEvaluationView.as_view(), name="evaluation-public"),
    path("public/<str:token>/responses/", PublicEvaluationSubmitView.as_view(), name="evaluation-public-submit"),
    *router.urls,
]
