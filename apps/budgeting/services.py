from decimal import Decimal, InvalidOperation

from apps.common.permissions import check_permission
from apps.projects.models import ProjectMembership
from apps.projects.services import is_project_manager, is_project_member

from .models import BudgetLine


class BudgetPermissionError(Exception):
    """L'acteur n'a pas le droit d'effectuer cette action."""


class BudgetValidationError(Exception):
    """Les données fournies ne permettent pas cette action."""


_BUDGET_EXCEPTIONS = (BudgetPermissionError, BudgetValidationError)


def _check(fn, *args):
    return check_permission(fn, *args, catch=_BUDGET_EXCEPTIONS)


def _require_actor(actor):
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise BudgetPermissionError("Utilisateur non identifié.")


# --- Fonctions de garde ---------------------------------------------------
# Même pattern que les autres apps (voir CLAUDE.md > "Permissions API — flags
# calculés") — mais la règle elle-même ("chef de projet de ce projet") est
# réutilisée depuis `apps.projects.services.is_project_manager` plutôt que
# réécrite ici : `apps.budgeting` a le droit d'importer `apps.projects`
# (hiérarchie de dépendances), donc pas de raison de dupliquer la requête
# `ProjectMembership`.


def _ensure_can_view_budget(actor, project):
    _require_actor(actor)
    if not is_project_member(actor, project):
        raise BudgetPermissionError("Seul un membre du projet peut consulter le budget.")


def _ensure_can_manage_budget(actor, project):
    _require_actor(actor)
    if not is_project_manager(actor, project):
        raise BudgetPermissionError("Seul un chef de projet peut gérer le budget.")


def can_view_budget(user, project):
    return _check(_ensure_can_view_budget, user, project)


def can_manage_budget_lines(user, project):
    return _check(_ensure_can_manage_budget, user, project)


def get_budget_lines(*, actor, project):
    _ensure_can_view_budget(actor, project)
    return BudgetLine.objects.filter(project=project).order_by("created_at")


def add_budget_line(*, actor, project, category, label, quantity, unit_price):
    _ensure_can_manage_budget(actor, project)

    valid_categories = {choice for choice, _ in BudgetLine.CATEGORY_CHOICES}
    if category not in valid_categories:
        raise BudgetValidationError("Catégorie de budget invalide (OPEX ou CAPEX attendu).")
    if not label or not label.strip():
        raise BudgetValidationError("Le libellé est obligatoire.")

    try:
        unit_price = Decimal(str(unit_price)) if unit_price is not None else None
    except InvalidOperation:
        raise BudgetValidationError("Le prix unitaire doit être un nombre.")
    if unit_price is None or unit_price < 0:
        raise BudgetValidationError("Le prix unitaire doit être un nombre positif ou nul.")

    # Quantité en unités entières uniquement (ex. "3 licences", "2 serveurs")
    # — pas de fraction d'unité, contrairement au prix unitaire qui reste en
    # Decimal. Passe par Decimal d'abord pour détecter proprement une valeur
    # fractionnaire ("2.5") plutôt que de la tronquer silencieusement via
    # `int()`.
    try:
        quantity = Decimal(str(quantity)) if quantity is not None else None
    except InvalidOperation:
        raise BudgetValidationError("La quantité doit être un nombre entier.")
    if quantity is None or quantity <= 0 or quantity != quantity.to_integral_value():
        raise BudgetValidationError("La quantité doit être un nombre entier positif (pas de décimales).")
    quantity = int(quantity)

    return BudgetLine.objects.create(
        project=project,
        category=category,
        label=label.strip(),
        quantity=quantity,
        unit_price=unit_price,
        created_by=actor,
    )


def remove_budget_line(*, actor, line):
    _ensure_can_manage_budget(actor, line.project)
    line.status = "removed"
    line.save(update_fields=["status"])
    return line


def get_budget_summary_for_manager(*, actor):
    """Écran Statistiques globales (voir docs/modeles-et-api.md) : budgets des
    projets où l'utilisateur courant est chef de projet — pas une règle de
    scoping générale, une capacité spécifique à ce rôle."""
    _require_actor(actor)

    memberships = ProjectMembership.objects.filter(
        user=actor, role="chef_de_projet", status="active"
    ).select_related("project")

    summary = []
    for membership in memberships:
        project = membership.project
        lines = BudgetLine.objects.filter(project=project)
        opex_total = sum((line.amount for line in lines if line.category == "opex"), Decimal("0"))
        capex_total = sum((line.amount for line in lines if line.category == "capex"), Decimal("0"))
        summary.append({"project": project, "opex_total": opex_total, "capex_total": capex_total})
    return summary
