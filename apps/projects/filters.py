import django_filters

from apps.common.filters import DefaultActiveStatusFilterMixin

from .models import Project


class ProjectFilterSet(DefaultActiveStatusFilterMixin, django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(field_name="status", choices=Project.STATUS_CHOICES)
    active_statuses = Project.ACTIVE_STATUSES

    class Meta:
        model = Project
        fields = ["status"]
