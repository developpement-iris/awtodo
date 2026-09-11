from apps.accounts.services import is_organisation_admin
from apps.projects.services import is_project_contributor, is_project_manager

from .models import CommunicationChannel, CommunicationMessage, O365Connection


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


# --- Connexion Office 365 (portée organisation) -------------------------


def get_o365_connection(organisation):
    connection, _ = O365Connection.objects.get_or_create(organisation=organisation)
    return connection


_O365_FIELDS = ("tenant_id", "client_id", "client_secret", "sender_mailbox", "is_enabled")


def update_o365_connection(*, actor, organisation, **fields):
    if not is_organisation_admin(actor, organisation):
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


# --- Canaux de communication (portée projet) --------------------------


def list_channels(project):
    return CommunicationChannel.objects.filter(project=project)


def _validate_channel_fields(*, channel_type, email, teams_webhook_url):
    if channel_type == "email" and not email:
        raise CommunicationValidationError("Une adresse mail est requise pour un canal de type « Adresse mail ».")
    if channel_type == "teams" and not teams_webhook_url:
        raise CommunicationValidationError(
            "L'URL du flux Power Automate est requise pour un canal de type « Canal Teams »."
        )


def create_channel(
    *, actor, project, channel_type, label, email="", teams_webhook_url="", notify_incident_created=False
):
    _ensure_can_manage_project_communication(actor, project)
    _validate_channel_fields(channel_type=channel_type, email=email, teams_webhook_url=teams_webhook_url)
    return CommunicationChannel.objects.create(
        project=project,
        channel_type=channel_type,
        label=label,
        email=email or "",
        teams_webhook_url=teams_webhook_url or "",
        notify_incident_created=notify_incident_created,
    )


def update_channel(*, actor, channel, **fields):
    _ensure_can_manage_project_communication(actor, channel.project)
    for name in ("label", "email", "teams_webhook_url", "notify_incident_created"):
        if name in fields and fields[name] is not None:
            setattr(channel, name, fields[name])
    _validate_channel_fields(
        channel_type=channel.channel_type, email=channel.email, teams_webhook_url=channel.teams_webhook_url
    )
    channel.save()
    return channel


def archive_channel(*, actor, channel):
    _ensure_can_manage_project_communication(actor, channel.project)
    channel.status = "archived"
    channel.save(update_fields=["status", "updated_at"])
    return channel


# --- Messages (journal / boîte d'envoi) -------------------------------


def list_messages(project):
    return (
        CommunicationMessage.objects.filter(project=project)
        .select_related("created_by", "incident")
        .prefetch_related("channels")
    )


def compose_message(*, actor, project, subject, body, channel_ids):
    """Rédaction manuelle. Crée un `CommunicationMessage` en attente — **aucun
    envoi** dans cette passe (le câblage suivra le déploiement AWS)."""
    _ensure_can_send_project_communication(actor, project)
    if not subject or not subject.strip():
        raise CommunicationValidationError("L'objet est obligatoire.")
    if not body or not body.strip():
        raise CommunicationValidationError("Le corps du message est obligatoire.")
    channels = list(
        CommunicationChannel.objects.filter(project=project, status="active", id__in=list(channel_ids))
    )
    if not channels:
        raise CommunicationValidationError("Sélectionnez au moins un destinataire actif.")
    message = CommunicationMessage.objects.create(
        project=project,
        subject=subject.strip()[:255],
        body=body.strip(),
        trigger="manuel",
        created_by=actor,
        status="en_attente",
    )
    message.channels.set(channels)
    # TODO(déploiement AWS) : déclencher ici l'envoi asynchrone (signal →
    # tâche Celery), jamais dans le flux HTTP.
    return message
