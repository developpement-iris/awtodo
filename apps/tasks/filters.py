import django_filters

from apps.common.filters import DefaultActiveStatusFilterMixin

from .models import Task


class TaskFilterSet(DefaultActiveStatusFilterMixin, django_filters.FilterSet):
    team = django_filters.UUIDFilter(method="filter_team", label="Groupe")
    # `?personal=true` : seulement les tâches sans projet (session du 2026-10-19).
    personal = django_filters.BooleanFilter(field_name="project", lookup_expr="isnull", label="Tâches personnelles")
    status = django_filters.MultipleChoiceFilter(field_name="status", choices=Task.STATUS_CHOICES)
    active_statuses = Task.ACTIVE_STATUSES

    class Meta:
        model = Task
        fields = ["project", "assignee", "team", "status", "version", "personal"]

    def filter_team(self, queryset, name, value):
        # Ne matche que les TeamMembership actives — un membre retiré du
        # groupe ne doit plus apparaître dans "tâches de mon groupe".
        return queryset.filter(
            assignee__team_memberships__team_id=value,
            assignee__team_memberships__status="active",
        )
