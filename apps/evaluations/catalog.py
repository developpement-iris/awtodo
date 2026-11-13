"""Catalogue de questions génériques d'un groupe (ou d'un projet sans groupe)."""

from apps.accounts.models import Team
from apps.accounts.services import can_manage_team, is_active_team_member
from apps.projects.services import is_project_manager, is_project_member

from .defaults import DEFAULT_CATALOG
from .definitions import (
    EvaluationPermissionError,
    EvaluationValidationError,
    clean_definition,
    definition_of,
    ensure_no_dependents,
)
from .models import CatalogQuestion

_EDITABLE = {"label", "help_text", "options", "required", "condition_on", "condition_values"}


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


# --- Droits --------------------------------------------------------------


def can_view_catalog(user, scope):
    if isinstance(scope, Team):
        return is_active_team_member(user, scope) or can_manage_team(user, scope)
    return is_project_member(user, scope)


def can_manage_catalog(user, scope):
    """Groupe : tout administrateur du groupe (décision du 2026-11-13, sans
    capacité de profil, contrairement aux types de tâche). Projet sans
    groupe : son chef de projet."""
    if isinstance(scope, Team):
        return can_manage_team(user, scope)
    return is_project_manager(user, scope)


def _ensure_manage(actor, scope):
    if not can_manage_catalog(actor, scope):
        raise EvaluationPermissionError("Réservé à un administrateur du groupe (ou au chef de projet).")


def scope_of(question):
    return question.team if question.team_id else question.project


# --- Services ------------------------------------------------------------


def list_catalog(*, actor, scope, include_archived=False):
    if not can_view_catalog(actor, scope):
        raise EvaluationPermissionError("Réservé aux membres du groupe ou du projet.")
    return get_catalog(scope, include_archived=include_archived)


def create_catalog_question(*, actor, scope, section, label, answer_type, help_text="", options=None,
                            required=False, condition_on=None, condition_values=None):
    _ensure_manage(actor, scope)
    fields = clean_definition(
        siblings=list(get_catalog(scope)), current=None, section=section, label=label, help_text=help_text,
        answer_type=answer_type, options=options, required=required, condition_on=condition_on,
        condition_values=condition_values,
    )
    last = get_catalog(scope, section=section, include_archived=True).order_by("-position").first()
    return CatalogQuestion.all_objects.create(
        position=(last.position + 1) if last else 0, **fields, **scope_filter(scope)
    )


def update_catalog_question(*, actor, question, **changes):
    """Le type de réponse est figé : le changer mélangerait des échelles
    différentes dans les statistiques des fiches déjà remplies."""
    scope = scope_of(question)
    _ensure_manage(actor, scope)
    if "answer_type" in changes and changes.pop("answer_type") != question.answer_type:
        raise EvaluationValidationError("Le type de réponse d'une question ne change pas après sa création.")
    if set(changes) - _EDITABLE:
        raise EvaluationValidationError("Champ non modifiable.")
    merged = definition_of(question)
    merged.update(changes)
    fields = clean_definition(siblings=list(get_catalog(scope)), current=question, **merged)
    for key, value in fields.items():
        setattr(question, key, value)
    question.save()
    return question


def archive_catalog_question(*, actor, question):
    _ensure_manage(actor, scope_of(question))
    if question.status != "active":
        raise EvaluationValidationError("Cette question est déjà archivée.")
    ensure_no_dependents(question)
    question.status = "archived"
    question.save(update_fields=["status", "updated_at"])
    return question


def restore_catalog_question(*, actor, question):
    _ensure_manage(actor, scope_of(question))
    if question.status != "archived":
        raise EvaluationValidationError("Cette question n'est pas archivée.")
    if question.condition_on_id and question.condition_on.status != "active":
        raise EvaluationValidationError("La question dont elle dépend est archivée : restaurez-la d'abord.")
    question.status = "active"
    question.save(update_fields=["status", "updated_at"])
    return question


def move_catalog_question(*, actor, question, direction):
    _ensure_manage(actor, scope_of(question))
    swap_position(list(get_catalog(scope_of(question), section=question.section)), question, direction)
    return question


def swap_position(ordered, question, direction):
    """Échange `question` avec sa voisine dans `ordered` (une section) et
    renumérote la section. Partagé avec les questions de fiche."""
    if direction not in ("up", "down"):
        raise EvaluationValidationError("Direction inconnue.")
    index = next((i for i, item in enumerate(ordered) if item.pk == question.pk), None)
    if index is None:
        raise EvaluationValidationError("Question introuvable dans cette section.")
    other = index - 1 if direction == "up" else index + 1
    if not 0 <= other < len(ordered):
        return
    ordered[index], ordered[other] = ordered[other], ordered[index]
    for position, item in enumerate(ordered):
        if item.position != position:
            item.position = position
            item.save(update_fields=["position", "updated_at"])
