from rest_framework.routers import SimpleRouter

from .views import CatalogQuestionViewSet

router = SimpleRouter(trailing_slash=True)
router.register("catalog", CatalogQuestionViewSet, basename="evaluation-catalog")

urlpatterns = [*router.urls]
