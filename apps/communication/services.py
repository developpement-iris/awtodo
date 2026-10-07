from django.db import transaction
from django.db.models import Q

from apps.accounts.services import has_capability, is_organisation_admin
from apps.common.audit import record_event
from apps.incidents.models import Incident
from apps.projects.models import ProjectMembership
from apps.projects.services import can_manage_team_communication, is_project_contributor, is_project_manager
from apps.tasks.models import Task

from .models import CommunicationChannel, CommunicationDelivery, CommunicationMessage, O365Connection
from .payload import PayloadTemplateError, validate_payload_template


class CommunicationPermissionError(Exception):
    pass


class CommunicationValidationError(Exception):
    pass


def _ensure_can_manage_project_communication(actor, project):
    # Configuration des canaux — chef de projet uniquement (même règle que la
    # fonction de garde homonyme dans apps.projects.services, qui alimente le
    # flag `permissions.can_manage_project_communication`).
    if not is_project_manager(actor, project):
        raise CommunicationPermissionError(
            "Seul un chef de projet peut configurer la communication du projet."
        )


def _ensure_can_send_project_communication(actor, project):
    if not is_project_contributor(actor, project):
        raise CommunicationPermissionError("Seul un contributeur du projet peut envoyer une communication.")


def _ensure_can_manage_team_communication(actor, project):
    # Canaux au niveau groupe (session du 2026-10-07) — voir
    # apps.projects.services._ensure_can_manage_team_communication pour la
    # règle elle-même (chef de projet d'UN projet du groupe, pas forcément
    # de `project`). Le "pas de groupe" est vérifié séparément ici (400,
    # erreur de requête) plutôt que de se fier au booléen de
    # `can_manage_team_communication` (403 uniquement) — sinon un projet
    # individuel sans groupe renverrait à tort "permission refusée".
    if project.team_id is None:
        raise CommunicationValidationError("Ce projet n'appartient à aucun groupe.")
    if not can_manage_team_communication(actor, project):
        raise CommunicationPermissionError(
            "Seul un chef de projet d'un projet de ce groupe peut configurer sa communication."
        )


def _ensure_can_manage_channel(actor, channel):
    """Choisit la bonne garde selon la portée réelle du canal (groupe ou
    projet) — un canal groupe n'est pas rattaché à `channel.project`
    (toujours `None` dans ce cas), donc pas question de réutiliser
    `_ensure_can_manage_project_communication` telle quelle."""
    if channel.team_id:
        if not ProjectMembership.objects.filter(
            project__team_id=channel.team_id, user=actor, status="active", role="chef_de_projet"
        ).exists():
            raise CommunicationPermissionError(
                "Seul un chef de projet d'un projet de ce groupe peut configurer sa communication."
            )
    else:
        _ensure_can_manage_project_communication(actor, channel.project)


# --- Connexion Office 365 (portée organisation, synchro Outlook uniquement) --


def get_o365_connection(organisation):
    connection, _ = O365Connection.objects.get_or_create(organisation=organisation)
    return connection


_O365_FIELDS = ("tenant_id", "client_id", "client_secret", "is_enabled")


def update_o365_connection(*, actor, organisation, **fields):
    if not (is_organisation_admin(actor, organisation) or has_capability(actor, "manage_integrations", organisation)):
        raise CommunicationPermissionError(
            "Seul un administrateur de l'organisation peut modifier la connexion Office 365."
        )
    connection = get_o365_connection(organisation)
    changed = []
    for name in _O365_FIELDS:
        if name in fields and fields[name] is not None:
            setattr(connection, name, fields[name])
            changed.append(name)
    if changed:
        connection.save(update_fields=[*changed, "updated_at"])
    return connection


# --- Canaux Teams (portée projet OU groupe) -----------------------------


def list_channels(project):
    """Canaux utilisables par ce projet : ses canaux propres, plus ceux de
    son groupe le cas échéant (héritage, session du 2026-10-07) — un projet
    individuel (sans groupe) n'a que les siens."""
    query = Q(project=project)
    if project.team_id:
        query |= Q(team_id=project.team_id)
    return CommunicationChannel.objects.filter(query)


def _validate_channel_fields(*, teams_channel_id, teams_channel_name, teams_webhook_url):
    if not teams_channel_id:
        raise CommunicationValidationError("L'ID du canal Teams est requis.")
    if not teams_channel_name:
        raise CommunicationValidationError("Le nom du canal Teams est requis.")
    if not teams_webhook_url:
        raise CommunicationValidationError("L'URL du flux Power Automate est requise.")


def create_channel(
    *,
    actor,
    project,
    label,
    teams_channel_id,
    teams_channel_name,
    teams_webhook_url,
    scope="project",
    payload_template=None,
    notify_incident_created=False,
):
    """`scope="project"` (défaut) crée un canal propre à `project` ; `scope="team"`
    le crée au niveau du groupe de `project` — visible et utilisable ensuite
    par tous les projets de ce groupe (`list_channels`). `project` reste
    toujours le point d'entrée (c'est depuis l'onglet d'un projet qu'on
    ajoute un canal), seule la ligne créée diffère."""
    if scope == "team":
        _ensure_can_manage_team_communication(actor, project)
        channel_project, channel_team = None, project.team
    else:
        _ensure_can_manage_project_communication(actor, project)
        channel_project, channel_team = project, None
    _validate_channel_fields(
        teams_channel_id=teams_channel_id, teams_channel_name=teams_channel_name, teams_webhook_url=teams_webhook_url
    )
    try:
        payload_template = validate_payload_template(payload_template)
    except PayloadTemplateError as exc:
        raise CommunicationValidationError(str(exc)) from exc
    channel = CommunicationChannel.objects.create(
        project=channel_project,
        team=channel_team,
        label=label,
        teams_channel_id=teams_channel_id,
        teams_channel_name=teams_channel_name,
        teams_webhook_url=teams_webhook_url,
        payload_template=payload_template,
        notify_incident_created=notify_incident_created,
    )
    record_event(
        channel,
        actor=actor,
        verb="created",
        description=f"Canal « {channel.label} » ajouté",
        project=channel_project,
        team=channel_team,
    )
    return channel


def update_channel(*, actor, channel, **fields):
    _ensure_can_manage_channel(actor, channel)
    for name in (
        "label",
        "teams_channel_id",
        "teams_channel_name",
        "teams_webhook_url",
        "payload_template",
        "notify_incident_created",
    ):
        if name in fields and fields[name] is not None:
            setattr(channel, name, fields[name])
    _validate_channel_fields(
        teams_channel_id=channel.teams_channel_id,
        teams_channel_name=channel.teams_channel_name,
        teams_webhook_url=channel.teams_webhook_url,
    )
    try:
        channel.payload_template = validate_payload_template(channel.payload_template)
    except PayloadTemplateError as exc:
        raise CommunicationValidationError(str(exc)) from exc
    channel.save()
    return channel


def archive_channel(*, actor, channel):
    _ensure_can_manage_channel(actor, channel)
    channel.status = "archived"
    channel.save(update_fields=["status", "updated_at"])
    record_event(
        channel,
        actor=actor,
        verb="archived",
        description=f"Canal « {channel.label} » archivé",
        project=channel.project,
        team=channel.team,
    )
    return channel


# --- Messages (journal / boîte d'envoi) -------------------------------


def list_messages(project):
    return (
        CommunicationMessage.objects.filter(project=project)
        .select_related("created_by", "incident", "task")
        .prefetch_related("deliveries__channel")
    )


def compose_message(*, actor, project, subject, body, channel_ids, task_id=None, incident_id=None):
    """Rédaction manuelle. Crée le `CommunicationMessage` + une
    `CommunicationDelivery` par canal ciblé, puis déclenche l'envoi réel
    (tâche Celery, jamais synchrone dans le flux HTTP — voir
    apps.communication.tasks) après commit de la transaction.

    `task_id`/`incident_id` optionnels : joignent une tâche/un incident du
    même projet au message, rendant ses champs disponibles au gabarit de
    payload d'un canal (`{{task.*}}`/`{{incident.*}}`, voir
    apps.communication.payload)."""
    _ensure_can_send_project_communication(actor, project)
    if not subject or not subject.strip():
        raise CommunicationValidationError("L'objet est obligatoire.")
    if not body or not body.strip():
        raise CommunicationValidationError("Le corps du message est obligatoire.")
    scope_query = Q(project=project)
    if project.team_id:
        scope_query |= Q(team_id=project.team_id)
    channels = list(
        CommunicationChannel.objects.filter(scope_query, status="active", id__in=list(channel_ids))
    )
    if not channels:
        raise CommunicationValidationError("Sélectionnez au moins un destinataire actif.")

    task = None
    if task_id is not None:
        task = Task.all_objects.filter(id=task_id, project=project).first()
        if task is None:
            raise CommunicationValidationError("Tâche introuvable sur ce projet.")

    incident = None
    if incident_id is not None:
        incident = Incident.all_objects.filter(id=incident_id, project=project).first()
        if incident is None:
            raise CommunicationValidationError("Incident introuvable sur ce projet.")

    with transaction.atomic():
        message = CommunicationMessage.objects.create(
            project=project,
            subject=subject.strip()[:255],
            body=body.strip(),
            trigger="manuel",
            created_by=actor,
            status="en_attente",
            task=task,
            incident=incident,
        )
        CommunicationDelivery.objects.bulk_create(
            [CommunicationDelivery(message=message, channel=channel) for channel in channels]
        )
        record_event(
            message,
            actor=actor,
            verb="sent",
            description=f"Communication envoyée : « {message.subject} » ({len(channels)} canal/canaux)",
            project=project,
        )

    def _dispatch():
        from .tasks import send_communication_message

        send_communication_message.delay(str(message.id))

    transaction.on_commit(_dispatch)
    return message
