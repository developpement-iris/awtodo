from django.contrib import admin

from .models import CatalogQuestion, ClientResponse, EvaluationSheet


@admin.register(CatalogQuestion)
class CatalogQuestionAdmin(admin.ModelAdmin):
    list_display = ("label", "section", "answer_type", "team", "project", "status")
    list_filter = ("section", "status")


@admin.register(EvaluationSheet)
class EvaluationSheetAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "status", "created_at")
    list_filter = ("status",)


@admin.register(ClientResponse)
class ClientResponseAdmin(admin.ModelAdmin):
    list_display = ("respondent_name", "sheet", "status", "created_at")
    list_filter = ("status",)
