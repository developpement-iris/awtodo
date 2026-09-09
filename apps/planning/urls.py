from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    CalendarEventViewSet,
    CalendarShareViewSet,
    CalendarView,
    ProjectPlanningViewSet,
    ScheduledBlockViewSet,
)

router = SimpleRouter(trailing_slash=True)
router.register("events", CalendarEventViewSet, basename="planning-event")
router.register("blocks", ScheduledBlockViewSet, basename="planning-block")
router.register("shares", CalendarShareViewSet, basename="planning-share")
router.register("projects", ProjectPlanningViewSet, basename="planning-project")

urlpatterns = [
    path("calendar/", CalendarView.as_view(), name="planning-calendar"),
    *router.urls,
]
