from rest_framework.routers import DefaultRouter

from .views import TaskTypeViewSet, TaskViewSet

router = DefaultRouter()
# Enregistré avant `TaskViewSet` (préfixe vide) : sinon `types/` serait
# capturé comme l'identifiant d'une tâche par la route de détail.
router.register("types", TaskTypeViewSet, basename="task-type")
router.register("", TaskViewSet, basename="task")

urlpatterns = router.urls
