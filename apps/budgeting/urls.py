from rest_framework.routers import DefaultRouter

from .views import BudgetLineViewSet

router = DefaultRouter()
# Préfixe vide : chaque action définit déjà son propre `url_path` complet
# (`projects/{id}/lines/`, `{id}/remove/`, `summary/`) — un préfixe non vide
# doublerait inutilement le segment "lines" dans l'URL finale.
router.register("", BudgetLineViewSet, basename="budget-line")

urlpatterns = router.urls
