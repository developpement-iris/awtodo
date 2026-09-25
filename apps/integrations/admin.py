from django.contrib import admin

from .models import ApiKey


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "organisation", "key_prefix", "is_active", "created_at", "last_used_at")
    list_filter = ("is_active", "organisation")
    readonly_fields = ("key_prefix", "key_hash", "service_account", "created_by")
