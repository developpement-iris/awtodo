from django.apps import AppConfig


class EvaluationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.evaluations"
    label = "evaluations"
    verbose_name = "Évaluations de projet"

    def ready(self):
        from . import receivers  # noqa: F401
