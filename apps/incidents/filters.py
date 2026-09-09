import django_filters

from apps.common.filters import DefaultActiveStatusFilterMixin

from .models import Incident


class IncidentFilterSet(DefaultActiveStatusFilterMixin, django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(field_name="status", choices=Incident.STATUS_CHOICES)
    active_statuses = Incident.ACTIVE_STATUSES

    class Meta:
        model = Incident
        fields = ["project", "status", "team"]
