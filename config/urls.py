from django.contrib import admin
from django.urls import include, path

api_v1_patterns = [
    path("accounts/", include("apps.accounts.urls")),
    path("projects/", include("apps.projects.urls")),
    path("tasks/", include("apps.tasks.urls")),
    path("incidents/", include("apps.incidents.urls")),
    path("docs/", include("apps.documentation.urls")),
    path("planning/", include("apps.planning.urls")),
    path("budgeting/", include("apps.budgeting.urls")),
    path("integrations/", include("apps.integrations.urls")),
    path("notifications/", include("apps.notifications.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1_patterns)),
]
