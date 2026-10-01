from django.contrib import admin

from .models import DashboardWidget


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ("owner", "scope", "widget_type", "metric_key", "visibility", "status", "created_at")
    list_filter = ("scope", "widget_type", "visibility", "status")
    search_fields = ("owner__username", "metric_key", "title")
