from django.urls import path

from .views import McpView

urlpatterns = [
    path("mcp", McpView.as_view(), name="mcp"),
]
