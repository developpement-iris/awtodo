from django.urls import path

from .views import (
    DashboardCatalogView,
    DashboardWidgetDetailView,
    GlobalDashboardView,
    ProjectDashboardView,
)

urlpatterns = [
    path("catalog/", DashboardCatalogView.as_view(), name="dashboard-catalog"),
    path("global/", GlobalDashboardView.as_view(), name="global-dashboard"),
    path("projects/<uuid:project_id>/", ProjectDashboardView.as_view(), name="project-dashboard"),
    path("widgets/<uuid:widget_id>/", DashboardWidgetDetailView.as_view(), name="dashboard-widget-detail"),
]
