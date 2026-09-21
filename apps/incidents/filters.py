import django_filters

from apps.common.filters import DefaultActiveStatusFilterMixin

from .models import Incident


class IncidentFilterSet(DefaultActiveStatusFilterMixin, django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(field_name="status", choices=Incident.STATUS_CHOICES)
    active_statuses = Incident.ACTIVE_STATUSES

    class Meta:
        model = Incident
        # "assigned_to" ajouté pour le panneau "À planifier" du planning
        # (session du 2026-09-21) — mêmes incidents que ceux que je peux
        # glisser sur mon calendrier.
        fields = ["project", "status", "team", "assigned_to"]
