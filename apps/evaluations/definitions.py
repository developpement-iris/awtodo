"""Validation d'une définition de question — partagée par le catalogue et
par les questions propres à une fiche."""

from .models import ANSWER_TYPES, CHOICE_TYPES, CONDITIONABLE_TYPES, SECTIONS


class EvaluationPermissionError(Exception):
    pass


class EvaluationValidationError(Exception):
    pass


def _clean_label(label):
    label = (label or "").strip()
    if not label:
        raise EvaluationValidationError("Le libellé de la question ne peut pas être vide.")
    if len(label) > 300:
        raise EvaluationValidationError("Le libellé ne peut pas dépasser 300 caractères.")
    return label


def _clean_options(answer_type, options):
    if answer_type not in CHOICE_TYPES:
        return []
    cleaned = [str(option).strip() for option in (options or []) if str(option).strip()]
    if len(cleaned) < 2:
        raise EvaluationValidationError("Un choix demande au moins deux options.")
    if len({option.casefold() for option in cleaned}) != len(cleaned):
        raise EvaluationValidationError("Deux options portent le même libellé.")
    if any(len(option) > 150 for option in cleaned):
        raise EvaluationValidationError("Une option ne peut pas dépasser 150 caractères.")
    return cleaned


def allowed_condition_values(answer_type, options):
    return ["oui", "non"] if answer_type == "oui_non" else list(options)


def _creates_cycle(current, target, by_id):
    """Vrai si `target` dépend (directement ou non) de `current`."""
    node, seen = target, set()
    while node is not None and node.pk not in seen:
        if current is not None and node.pk == current.pk:
            return True
        seen.add(node.pk)
        node = by_id.get(node.condition_on_id)
    return False


def clean_definition(*, siblings, current, section, label, help_text, answer_type, options, required,
                     condition_on, condition_values):
    """Valide une définition complète et renvoie les champs à enregistrer.
    `siblings` : questions actives de la même portée (catalogue ou fiche) ;
    `current` : la question modifiée, ou `None` à la création ;
    `condition_on` : UUID (ou instance, ou `None`) d'une question de `siblings`."""
    if section not in SECTIONS:
        raise EvaluationValidationError("Partie inconnue.")
    if answer_type not in ANSWER_TYPES:
        raise EvaluationValidationError("Type de réponse inconnu.")
    help_text = (help_text or "").strip()
    if len(help_text) > 500:
        raise EvaluationValidationError("L'aide ne peut pas dépasser 500 caractères.")
    cleaned = {
        "section": section,
        "label": _clean_label(label),
        "help_text": help_text,
        "answer_type": answer_type,
        "options": _clean_options(answer_type, options),
        "required": bool(required),
        "condition_on": None,
        "condition_values": [],
    }

    if condition_on:
        target_id = str(getattr(condition_on, "pk", condition_on))
        target = next((sibling for sibling in siblings if str(sibling.pk) == target_id), None)
        if target is None:
            raise EvaluationValidationError("La question dont dépend celle-ci est introuvable.")
        if current is not None and target.pk == current.pk:
            raise EvaluationValidationError("Une question ne peut pas dépendre d'elle-même.")
        if target.section != section:
            raise EvaluationValidationError("Une condition porte sur une question de la même partie.")
        if target.answer_type not in CONDITIONABLE_TYPES:
            raise EvaluationValidationError("Une condition porte sur une question oui/non ou à choix unique.")
        if _creates_cycle(current, target, {sibling.pk: sibling for sibling in siblings}):
            raise EvaluationValidationError("Cette condition créerait une boucle entre questions.")
        values = [str(value) for value in (condition_values or [])]
        allowed = allowed_condition_values(target.answer_type, target.options)
        if not values or any(value not in allowed for value in values):
            raise EvaluationValidationError("Choisissez au moins une réponse qui affiche la question.")
        cleaned["condition_on"] = target
        cleaned["condition_values"] = values

    # Une question dont d'autres dépendent doit garder des réponses compatibles.
    if current is not None:
        for dependent in current.dependents.filter(status="active"):
            if cleaned["answer_type"] not in CONDITIONABLE_TYPES:
                raise EvaluationValidationError("D'autres questions dépendent de celle-ci.")
            allowed = allowed_condition_values(cleaned["answer_type"], cleaned["options"])
            if any(value not in allowed for value in dependent.condition_values):
                raise EvaluationValidationError(
                    f"La question « {dependent.label} » dépend d'une réponse que vous retirez."
                )
    return cleaned


def ensure_no_dependents(question):
    if question.dependents.filter(status="active").exists():
        raise EvaluationValidationError(
            "D'autres questions dépendent de celle-ci : retirez d'abord leur condition."
        )


def definition_of(question):
    """Champs actuels d'une question, pour fusionner une modification partielle."""
    return {
        "section": question.section,
        "label": question.label,
        "help_text": question.help_text,
        "answer_type": question.answer_type,
        "options": question.options,
        "required": question.required,
        "condition_on": question.condition_on_id,
        "condition_values": question.condition_values,
    }
