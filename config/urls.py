from django.contrib import admin
from django.urls import include, path, re_path

from config.health import health
from config.spa import spa_index

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
    path("communication/", include("apps.communication.urls")),
]

urlpatterns = [
    path("api/health/", health),
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1_patterns)),
    # Fallback SPA (staging : Django sert le build Vite). Toute route qui
    # n'est ni l'API, ni l'admin, ni un statique renvoie index.html.
    re_path(r"^(?!api/|admin/|static/).*$", spa_index),
]
