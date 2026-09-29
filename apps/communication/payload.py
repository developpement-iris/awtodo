"""Gabarit de payload personnalisable par canal (session du 2026-09-28).

Chaque canal Teams peut définir son propre `CommunicationChannel.payload_template`
(objet JSON plat `{clé: valeur}`) plutôt que de recevoir toujours le même
payload figé. Une valeur de la forme `{{espace.champ}}` est résolue contre un
contexte de champs connus (message/projet/expéditeur/canal/tâche/incident) ;
toute autre valeur est envoyée telle quelle (« custom attribute » — l'admin y
met ce qu'il veut pour sa propre automatisation, jamais interprété).

Volontairement **pas** un moteur de templating générique (Jinja2/`eval`) :
seule une liste blanche de champs connus peut être injectée, ce qui exclut
toute exécution de code ou lecture de données hors de cette liste — un choix
de sécurité, pas une limitation technique.
"""

import re

_PLACEHOLDER_RE = re.compile(r"^\{\{\s*([a-z_]+)\.([a-z_]+)\s*\}\}$")

# Catalogue des champs disponibles, exposé tel quel au frontend (bouton
# "insérer un champ" du gabarit) — toute clé absente d'ici est ignorée à la
# résolution (résolue en chaîne vide), jamais une erreur serveur.
AVAILABLE_FIELDS = {
    "message": ["subject", "body", "trigger", "created_at", "sent_at"],
    "project": ["name", "id"],
    "sender": ["username", "first_name", "last_name", "email", "display_name"],
    "channel": ["id", "name", "label"],
    "task": ["title", "description", "status", "priority", "type", "deadline", "estimated_hours", "assignee"],
    "incident": ["title", "description", "status", "priority", "assigned_to", "author_name", "author_email"],
}

# Utilisé quand `CommunicationChannel.payload_template` est vide — reproduit
# le payload fixe envoyé avant l'introduction des gabarits, pour que les
# canaux déjà configurés continuent de recevoir exactement la même forme.
DEFAULT_TEMPLATE = {
    "subject": "{{message.subject}}",
    "body": "{{message.body}}",
    "project": "{{project.name}}",
    "sender_name": "{{sender.display_name}}",
    "trigger": "{{message.trigger}}",
    "sent_at": "{{message.sent_at}}",
    "channel_id": "{{channel.id}}",
    "channel_name": "{{channel.name}}",
}


def _display_name(user):
    if user is None:
        return "Awtodo"
    full = f"{user.first_name} {user.last_name}".strip()
    return full or user.username


def _user_fields(user):
    if user is None:
        return {"username": "", "first_name": "", "last_name": "", "email": "", "display_name": "Awtodo"}
    return {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "display_name": _display_name(user),
    }


def _task_fields(task):
    if task is None:
        return {}
    return {
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "type": task.task_type,
        "deadline": task.deadline.isoformat() if task.deadline else "",
        "estimated_hours": str(task.estimated_hours) if task.estimated_hours is not None else "",
        "assignee": task.assignee.username if task.assignee_id else "",
    }


def _incident_fields(incident):
    if incident is None:
        return {}
    return {
        "title": incident.title,
        "description": incident.description,
        "status": incident.status,
        "priority": incident.priority,
        "assigned_to": incident.assigned_to.username if incident.assigned_to_id else "",
        "author_name": incident.author_name,
        "author_email": incident.author_email,
    }


def build_message_context(message):
    """Contexte commun à tous les canaux d'un même message — le contexte
    `channel` est ajouté séparément par `render_payload_for_channel` (varie
    par destinataire)."""
    return {
        "message": {
            "subject": message.subject,
            "body": message.body,
            "trigger": message.trigger,
            "created_at": message.created_at.isoformat(),
        },
        "project": {"name": message.project.name, "id": str(message.project_id)},
        "sender": _user_fields(message.created_by),
        "task": _task_fields(getattr(message, "task", None)),
        "incident": _incident_fields(message.incident),
    }


def render_payload_for_channel(channel, base_context):
    context = {
        **base_context,
        "channel": {"id": channel.teams_channel_id, "name": channel.teams_channel_name, "label": channel.label},
    }
    template = channel.payload_template or DEFAULT_TEMPLATE
    rendered = {}
    for key, value in template.items():
        if isinstance(value, str):
            match = _PLACEHOLDER_RE.match(value.strip())
            if match:
                namespace, field = match.groups()
                rendered[key] = context.get(namespace, {}).get(field, "")
                continue
        rendered[key] = value
    return rendered


class PayloadTemplateError(Exception):
    pass


def validate_payload_template(template):
    """Le gabarit doit rester un objet JSON plat (pas de nesting, pas de
    tableau) — assez pour couvrir le cas d'usage décrit (des paires
    clé/valeur postées à un flow Power Automate) sans la complexité d'un
    vrai moteur de templates."""
    if template is None:
        return {}
    if not isinstance(template, dict):
        raise PayloadTemplateError("Le gabarit de payload doit être un objet JSON (clé → valeur).")
    for key, value in template.items():
        if not isinstance(key, str) or not key:
            raise PayloadTemplateError("Chaque clé du gabarit doit être une chaîne non vide.")
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            raise PayloadTemplateError(f"La valeur de « {key} » doit être un texte, un nombre ou un booléen.")
    return template
