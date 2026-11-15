from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    CalendarEventViewSet,
    CalendarShareViewSet,
    CalendarView,
    ProjectPlanningViewSet,
    RoadmapView,
    ScheduledBlockViewSet,
    WorkingHoursView,
    WorkloadView,
)

router = SimpleRouter(trailing_slash=True)
router.register("events", CalendarEventViewSet, basename="planning-event")
router.register("blocks", ScheduledBlockViewSet, basename="planning-block")
router.register("shares", CalendarShareViewSet, basename="planning-share")
router.register("projects", ProjectPlanningViewSet, basename="planning-project")

urlpatterns = [
    path("calendar/", CalendarView.as_view(), name="planning-calendar"),
    path("working-hours/", WorkingHoursView.as_view(), name="planning-working-hours"),
    path("roadmap/", RoadmapView.as_view(), name="planning-roadmap"),
    path("workload/", WorkloadView.as_view(), name="planning-workload"),
    *router.urls,
]
