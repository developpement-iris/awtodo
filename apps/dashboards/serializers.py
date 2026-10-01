from rest_framework import serializers

from .catalog import DEFAULT_METRICS
from .models import DashboardWidget


class DashboardWidgetCreateSerializer(serializers.Serializer):
    widget_type = serializers.ChoiceField(choices=[c for c, _ in DashboardWidget.WIDGET_TYPE_CHOICES])
    metric_key = serializers.CharField(required=False, allow_blank=True, default="")
    config = serializers.JSONField(required=False, default=dict)
    visibility = serializers.ChoiceField(
        choices=[c for c, _ in DashboardWidget.VISIBILITY_CHOICES], required=False, default="individuel"
    )
    title = serializers.CharField(required=False, allow_blank=True, default="")
    x = serializers.IntegerField(required=False, default=0, min_value=0)
    y = serializers.IntegerField(required=False, default=0, min_value=0)
    w = serializers.IntegerField(required=False, default=4, min_value=1)
    h = serializers.IntegerField(required=False, default=3, min_value=1)


class DashboardWidgetPositionSerializer(serializers.Serializer):
    x = serializers.IntegerField(min_value=0)
    y = serializers.IntegerField(min_value=0)
    w = serializers.IntegerField(min_value=1)
    h = serializers.IntegerField(min_value=1)


def serialize_widget_entry(entry):
    """`entry` = `{"widget": DashboardWidget, "data": dict}` tel que renvoyé
    par `apps.dashboards.services.get_dashboard` — pas un `ModelSerializer`
    classique, le champ `data` dépend d'un calcul fait en dehors du modèle."""
    widget = entry["widget"]
    metric = DEFAULT_METRICS.get(widget.metric_key) if widget.widget_type == "defaut" else None
    return {
        "id": str(widget.id),
        "widget_type": widget.widget_type,
        "metric_key": widget.metric_key,
        "config": widget.config,
        "visibility": widget.visibility,
        "title": widget.title or (metric["label"] if metric else ""),
        "render_hint": metric["render_hint"] if metric else _custom_render_hint(widget.config),
        "x": widget.x,
        "y": widget.y,
        "w": widget.w,
        "h": widget.h,
        "data": entry["data"],
    }


def _custom_render_hint(config):
    """Un widget personnalisé sans regroupement est une valeur unique
    (`stat_card`) ; avec regroupement, une série (`bar`, le plus lisible par
    défaut pour une liste de catégories — pas de notion de courbe temporelle
    hors `group_by="week"`, auquel cas une aire est plus parlante)."""
    if not isinstance(config, dict):
        return "stat_card"
    if config.get("group_by", "none") == "none":
        return "stat_card"
    if config.get("group_by") == "week":
        return "area"
    return "bar"
