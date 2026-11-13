"""Catalogue de questions génériques d'un groupe (ou d'un projet sans groupe)."""

from apps.accounts.models import Team

from .defaults import DEFAULT_CATALOG
from .models import CatalogQuestion


def catalog_scope(project):
    """`Team` ou `Project` portant le catalogue de `project`."""
    return project.team if project.team_id else project


def scope_filter(scope):
    return {"team": scope} if isinstance(scope, Team) else {"project": scope}


def get_catalog(scope, section=None, include_archived=False):
    qs = CatalogQuestion.all_objects.filter(**scope_filter(scope))
    if section is not None:
        qs = qs.filter(section=section)
    if not include_archived:
        qs = qs.filter(status="active")
    return qs.order_by("section", "position", "created_at")


def _scope_filter_by_id(scope):
    # Dans une migration, `scope` est une instance du modèle historique : on
    # se fie au nom du modèle plutôt qu'à `isinstance(scope, Team)`.
    return {"team_id": scope.pk} if type(scope).__name__ == "Team" else {"project_id": scope.pk}


def seed_default_catalog(scope, question_model=CatalogQuestion):
    """Idempotent : rien si la portée a déjà au moins une question (même
    archivée). `question_model` permet l'appel depuis une migration de données.
    `_default_manager` = `all_objects` au runtime (`default_manager_name`), et
    le seul manager disponible sur un modèle historique."""
    manager = question_model._default_manager
    if manager.filter(**_scope_filter_by_id(scope)).exists():
        return
    created = [
        manager.create(
            section=spec["section"],
            label=spec["label"],
            answer_type=spec["answer_type"],
            options=list(spec.get("options", [])),
            required=spec.get("required", False),
            position=index,
            **_scope_filter_by_id(scope),
        )
        for index, spec in enumerate(DEFAULT_CATALOG)
    ]
    for index, spec in enumerate(DEFAULT_CATALOG):
        if "condition" in spec:
            target_index, values = spec["condition"]
            question = created[index]
            question.condition_on = created[target_index]
            question.condition_values = list(values)
            question.save(update_fields=["condition_on", "condition_values"])
