from django.apps import AppConfig


class DocumentationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.documentation"
    label = "documentation"

    def ready(self):
        from . import signals  # noqa: F401
