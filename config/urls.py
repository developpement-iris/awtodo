from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView

from config.api_docs import ApiDocsView
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
    path("dashboards/", include("apps.dashboards.urls")),
    # Documentation de l'API : schéma filtré selon l'appelant, voir SPECTACULAR_SETTINGS.
    path("schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("docs-api/", ApiDocsView.as_view(), name="api-docs"),
]

urlpatterns = [
    path("api/health/", health),
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1_patterns)),
    # Serveur MCP pour le connecteur Claude + son serveur d'autorisation
    # OAuth (apps.mcp). Avant le fallback SPA, qui attraperait sinon /mcp,
    # /o/... et /.well-known/....
    path("", include("apps.mcp.urls")),
    path("", include("apps.mcp.oauth_urls")),
    # Fallback SPA (staging : Django sert le build Vite). Toute route qui
    # n'est ni l'API, ni l'admin, ni un statique renvoie index.html.
    re_path(r"^(?!api/|admin/|static/).*$", spa_index),
]
