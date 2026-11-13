"""Fiches d'évaluation : création (copie figée du catalogue), questions
propres à la fiche, cycle de vie et lien public."""

import secrets

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.services import can_manage_team, is_organisation_admin
from apps.common.audit import record_event
from apps.projects.services import is_project_manager

from .answers import AnswerError, clean_answers
from .catalog import catalog_scope, get_catalog, swap_position
from .definitions import (
    EvaluationPermissionError,
    EvaluationValidationError,
    clean_definition,
    definition_of,
    ensure_no_dependents,
)
from .models import Answer, ClientResponse, EvaluationSheet, SheetQuestion

# Contrairement au catalogue, une question propre à une fiche en brouillon
# peut changer de type : elle n'a encore aucune réponse.
_EDITABLE = {"label", "help_text", "answer_type", "options", "required", "condition_on", "condition_values"}


# --- Droits --------------------------------------------------------------


def can_manage_sheets(user, project):
    return is_project_manager(user, project)


def can_view_sheets(user, project):
    """Chefs de projet, admins du groupe du projet, admins d'organisation —
    décision du 2026-11-13 (les deux parties de la fiche leur sont visibles)."""
    if is_project_manager(user, project) or is_organisation_admin(user, project.organisation):
        return True
    return bool(project.team_id and can_manage_team(user, project.team))


def _ensure_manage(actor, project):
    if not can_manage_sheets(actor, project):
        raise EvaluationPermissionError("Réservé aux chefs de projet.")


def _ensure_view(actor, project):
    if not can_view_sheets(actor, project):
        raise EvaluationPermissionError("Réservé aux chefs de projet et aux administrateurs.")


# --- Lecture -------------------------------------------------------------


def sheet_questions(sheet, section=None):
    qs = SheetQuestion.all_objects.filter(sheet=sheet, status="active")
    if section is not None:
        qs = qs.filter(section=section)
    return qs.order_by("section", "position", "created_at")


def public_path(sheet):
    if sheet.status == "ouverte" and sheet.public_token:
        return f"/evaluation/{sheet.public_token}"
    return None


def list_sheets(*, actor, project):
    _ensure_view(actor, project)
    return (
        EvaluationSheet.all_objects.filter(project=project)
        .annotate(response_count=Count("client_responses", filter=Q(client_responses__status="retenue")))
        .order_by("-created_at")
    )


def get_sheet(*, actor, sheet):
    _ensure_view(actor, sheet.project)
    return sheet


# --- Création / édition --------------------------------------------------


def _clean_title(title):
    title = (title or "").strip()
    if not title:
        raise EvaluationValidationError("Le titre de la fiche ne peut pas être vide.")
    return title[:200]


@transaction.atomic
def create_sheet(*, actor, project, title, client_intro=""):
    """Copie les questions actives du catalogue (groupe ou projet sans groupe)
    dans la fiche, conditions comprises : modifier le catalogue ensuite ne
    change rien à cette fiche."""
    _ensure_manage(actor, project)
    sheet = EvaluationSheet.all_objects.create(
        project=project, title=_clean_title(title), client_intro=(client_intro or "").strip(), created_by=actor
    )
    sources = list(get_catalog(catalog_scope(project)))
    copies = {}
    for position, source in enumerate(sources):
        copies[source.pk] = SheetQuestion.all_objects.create(
            sheet=sheet, catalog_question=source, section=source.section, label=source.label,
            help_text=source.help_text, answer_type=source.answer_type, options=list(source.options),
            required=source.required, position=position, condition_values=list(source.condition_values),
        )
    for source in sources:
        if source.condition_on_id:
            copy = copies[source.pk]
            copy.condition_on = copies.get(source.condition_on_id)
            if copy.condition_on is None:  # cible archivée entre-temps
                copy.condition_values = []
            copy.save(update_fields=["condition_on", "condition_values"])
    record_event(
        sheet, actor=actor, verb="created", description=f"Fiche d'évaluation créée : {sheet.title}", project=project
    )
    return sheet


def update_sheet(*, actor, sheet, title=None, client_intro=None):
    _ensure_manage(actor, sheet.project)
    if sheet.status == "archivee":
        raise EvaluationValidationError("Cette fiche est archivée.")
    if title is not None:
        sheet.title = _clean_title(title)
    if client_intro is not None:
        sheet.client_intro = client_intro.strip()
    sheet.save()
    return sheet


def _ensure_draft(sheet):
    if sheet.status != "brouillon":
        raise EvaluationValidationError("Les questions ne se modifient plus une fois la fiche ouverte.")


def _ensure_custom(question):
    if question.catalog_question_id:
        raise EvaluationValidationError(
            "Question générique : modifiez-la dans le catalogue du groupe, elle s'appliquera aux prochaines fiches."
        )


def add_sheet_question(*, actor, sheet, section, label, answer_type, help_text="", options=None,
                       required=False, condition_on=None, condition_values=None):
    _ensure_manage(actor, sheet.project)
    _ensure_draft(sheet)
    fields = clean_definition(
        siblings=list(sheet_questions(sheet)), current=None, section=section, label=label, help_text=help_text,
        answer_type=answer_type, options=options, required=required, condition_on=condition_on,
        condition_values=condition_values,
    )
    last = SheetQuestion.all_objects.filter(sheet=sheet, section=section).order_by("-position").first()
    return SheetQuestion.all_objects.create(sheet=sheet, position=(last.position + 1) if last else 0, **fields)


def update_sheet_question(*, actor, question, **changes):
    sheet = question.sheet
    _ensure_manage(actor, sheet.project)
    _ensure_draft(sheet)
    _ensure_custom(question)
    if set(changes) - _EDITABLE:
        raise EvaluationValidationError("Champ non modifiable.")
    merged = definition_of(question)
    merged.update(changes)
    fields = clean_definition(siblings=list(sheet_questions(sheet)), current=question, **merged)
    for key, value in fields.items():
        setattr(question, key, value)
    question.save()
    return question


def archive_sheet_question(*, actor, question):
    _ensure_manage(actor, question.sheet.project)
    _ensure_draft(question.sheet)
    _ensure_custom(question)
    ensure_no_dependents(question)
    question.status = "archived"
    question.save(update_fields=["status", "updated_at"])
    return question


def move_sheet_question(*, actor, question, direction):
    """Réordonner reste permis pour les questions génériques : l'ordre
    n'affecte pas les statistiques."""
    _ensure_manage(actor, question.sheet.project)
    _ensure_draft(question.sheet)
    swap_position(list(sheet_questions(question.sheet, section=question.section)), question, direction)
    return question


# --- Cycle de vie --------------------------------------------------------


def _ensure_status(actor, sheet, allowed, message):
    _ensure_manage(actor, sheet.project)
    if sheet.status not in allowed:
        raise EvaluationValidationError(message)


def open_sheet(*, actor, sheet):
    _ensure_status(actor, sheet, {"brouillon"}, "Seule une fiche en brouillon s'ouvre.")
    if not sheet_questions(sheet, section="client").exists():
        raise EvaluationValidationError("Ajoutez au moins une question client avant d'ouvrir la fiche.")
    sheet.status = "ouverte"
    sheet.public_token = sheet.public_token or secrets.token_urlsafe(24)
    sheet.opened_at = timezone.now()
    sheet.save()
    record_event(
        sheet, actor=actor, verb="sent", description=f"Fiche d'évaluation ouverte : {sheet.title}",
        project=sheet.project,
    )
    return sheet


def close_sheet(*, actor, sheet):
    _ensure_status(actor, sheet, {"ouverte"}, "Seule une fiche ouverte se clôt.")
    sheet.status = "close"
    sheet.closed_at = timezone.now()
    sheet.save()
    return sheet


def reopen_sheet(*, actor, sheet):
    _ensure_status(actor, sheet, {"close"}, "Seule une fiche close se rouvre.")
    sheet.status = "ouverte"
    sheet.closed_at = None
    sheet.save()
    return sheet


def archive_sheet(*, actor, sheet):
    _ensure_status(actor, sheet, {"brouillon", "close"}, "Clôturez la fiche avant de l'archiver.")
    sheet.status = "archivee"
    sheet.save()
    record_event(
        sheet, actor=actor, verb="archived", description=f"Fiche d'évaluation archivée : {sheet.title}",
        project=sheet.project,
    )
    return sheet


def rotate_sheet_link(*, actor, sheet):
    """Nouveau jeton : l'ancien lien cesse aussitôt de fonctionner."""
    _ensure_status(actor, sheet, {"ouverte"}, "Le lien ne se régénère que sur une fiche ouverte.")
    sheet.public_token = secrets.token_urlsafe(24)
    sheet.save(update_fields=["public_token", "updated_at"])
    return sheet


# --- Formulaire public (sans compte) -------------------------------------


class SheetClosedError(Exception):
    pass


def _public_question(question):
    return {
        "id": str(question.id), "label": question.label, "help_text": question.help_text,
        "answer_type": question.answer_type, "options": question.options, "required": question.required,
        "condition_on": str(question.condition_on_id) if question.condition_on_id else None,
        "condition_values": question.condition_values,
    }


def _sheet_by_token(token):
    if not token:
        return None
    return (
        EvaluationSheet.all_objects.select_related("project")
        .filter(public_token=token).exclude(status__in=["brouillon", "archivee"]).first()
    )


def get_public_sheet(token):
    """Seul contenu exposé sans compte : titre, intro, nom du projet et
    questions client d'une fiche ouverte. Jamais la partie chef de projet."""
    sheet = _sheet_by_token(token)
    if sheet is None:
        return None
    if sheet.status != "ouverte":
        return {"closed": True, "title": sheet.title, "project_name": sheet.project.name}
    return {
        "closed": False,
        "title": sheet.title,
        "client_intro": sheet.client_intro,
        "project_name": sheet.project.name,
        "questions": [_public_question(q) for q in sheet_questions(sheet, section="client")],
    }


@transaction.atomic
def submit_client_response(*, token, respondent_name, answers):
    """`None` si le lien est inconnu. Seules les questions client sont
    acceptées : une réponse à une question interne est refusée."""
    sheet = _sheet_by_token(token)
    if sheet is None:
        return None
    if sheet.status != "ouverte":
        raise SheetClosedError("Ce formulaire n'accepte plus de réponses.")
    name = (respondent_name or "").strip()
    if not name:
        raise AnswerError(None, "Indiquez votre nom.")
    if len(name) > 150:
        raise AnswerError(None, "Le nom ne peut pas dépasser 150 caractères.")
    questions = list(sheet_questions(sheet, section="client"))
    cleaned = clean_answers(questions, answers, enforce_required=True)
    response = ClientResponse.all_objects.create(sheet=sheet, respondent_name=name)
    Answer.objects.bulk_create(
        Answer(question=question, client_response=response, value=cleaned[str(question.id)])
        for question in questions
    )
    return response
