from apps.accounts.models import Team
from apps.accounts.services import can_manage_team, is_active_team_member
from apps.common.audit import record_changes
from apps.common.permissions import check_permission
from apps.projects.services import is_project_contributor, is_project_manager

from .models import Incident, IncidentComment
from .signals import incident_commented, incident_resolved


class IncidentPermissionError(Exception):
    """L'acteur n'a pas le droit d'effectuer cette action."""


class IncidentValidationError(Exception):
    """Le statut de départ ne permet pas cette transition."""


_INCIDENT_EXCEPTIONS = (IncidentPermissionError, IncidentValidationError)


def _check(fn, *args):
    return check_permission(fn, *args, catch=_INCIDENT_EXCEPTIONS)


def _require_actor(actor):
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise IncidentPermissionError("Utilisateur non identifié.")


def _is_member_via_project(user, project):
    """Membre du groupe attribué au projet (collaboratif) ; à défaut de groupe
    (projet individuel), contributeur du projet lui-même. Un membre `lecteur`
    n'a **pas** accès aux incidents (session du 2026-09-10) — d'où
    `is_project_contributor`, pas `is_project_member` ; côté projet
    collaboratif la question ne se pose pas, un lecteur n'est pas dans le
    groupe."""
    if project.team_id:
        return is_active_team_member(user, project.team)
    return is_project_contributor(user, project)


def _is_member_via_team(user, team):
    return is_active_team_member(user, team)


def _is_authorized_member(user, incident):
    """Un incident est rattaché soit à un projet, soit directement à un groupe
    (incident non-affecté, voir `create_incident`) — jamais les deux, jamais
    aucun des deux. L'autorisation suit celui des deux qui est renseigné."""
    if incident.team_id:
        return _is_member_via_team(user, incident.team)
    return _is_member_via_project(user, incident.project)


def _require_member(actor, incident):
    _require_actor(actor)
    if not _is_authorized_member(actor, incident):
        raise IncidentPermissionError("Seul un membre du groupe concerné peut effectuer cette action.")


def accessible_inbox_teams(user):
    """Groupes dont `user` peut voir la boîte de réception d'incidents non-
    affectés — même logique que `accessible_projects` (apps.projects.services)
    mais côté groupe : admin plateforme voit tout, sinon uniquement les
    groupes où l'appartenance est active."""
    if user is None or not getattr(user, "is_authenticated", False):
        return Team.objects.none()
    if getattr(user, "is_platform_admin", False):
        return Team.objects.all()
    return Team.objects.filter(memberships__user=user, memberships__status="active").distinct()


# --- Fonctions de garde ---------------------------------------------------
# Même pattern que `apps.tasks.services` : seule source de vérité pour
# chaque règle, réutilisée à la fois par la transition réelle et par le flag
# `can_*` correspondant (voir `get_incident_permissions`).


def _ensure_can_start(actor, incident):
    _require_member(actor, incident)
    if incident.status != "signale":
        raise IncidentValidationError("Seul un incident signalé peut être démarré.")


def _ensure_can_resolve(actor, incident):
    _require_member(actor, incident)
    if incident.status != "en_cours":
        raise IncidentValidationError("Seul un incident en cours peut être résolu.")


def _ensure_can_archive(actor, incident):
    _require_member(actor, incident)
    if incident.status != "resolu":
        raise IncidentValidationError("Seul un incident résolu peut être archivé.")


def _ensure_can_comment(actor, incident):
    _require_member(actor, incident)


def _ensure_can_edit_description(actor, incident):
    _require_member(actor, incident)


def _ensure_can_assign_project(actor, incident):
    _require_member(actor, incident)
    if incident.project_id is not None:
        raise IncidentValidationError("Cet incident est déjà rattaché à un projet.")


def _ensure_can_claim(actor, incident):
    """S'assigner soi-même : ouvert à n'importe quel membre du groupe, comme
    le reste du cycle de vie d'un incident (voir "Différence volontaire avec
    les tâches" ci-dessus) — aucune restriction du type "déjà assigné à
    quelqu'un d'autre", se réassigner écrase simplement l'assigné précédent."""
    _require_member(actor, incident)


def _is_incident_admin(user, incident):
    """"Administrateur" pour une action sur un incident (changement de
    priorité, session du 11/08/2026) : admin du groupe rattaché — direct
    (`team`) ou via le groupe du projet collaboratif — même définition que
    partout ailleurs (`apps.accounts.services.can_manage_team`). Pour un
    incident rattaché à un projet individuel (pas de groupe), le chef de
    projet de ce projet joue le même rôle, faute de groupe à vérifier."""
    if incident.team_id:
        return can_manage_team(user, incident.team)
    if incident.project_id:
        if incident.project.team_id:
            return can_manage_team(user, incident.project.team)
        return is_project_manager(user, incident.project)
    return False


def _ensure_can_change_priority(actor, incident):
    _require_actor(actor)
    if incident.assigned_to_id == actor.id or _is_incident_admin(actor, incident):
        return
    raise IncidentPermissionError(
        "Seul l'assigné de l'incident ou un administrateur du groupe concerné peut changer la priorité."
    )


def can_start_incident(user, incident):
    return _check(_ensure_can_start, user, incident)


def can_resolve_incident(user, incident):
    return _check(_ensure_can_resolve, user, incident)


def can_archive_incident(user, incident):
    return _check(_ensure_can_archive, user, incident)


def can_comment_incident(user, incident):
    return _check(_ensure_can_comment, user, incident)


def can_edit_description_incident(user, incident):
    return _check(_ensure_can_edit_description, user, incident)


def can_assign_project_incident(user, incident):
    return _check(_ensure_can_assign_project, user, incident)


def can_claim_incident(user, incident):
    return _check(_ensure_can_claim, user, incident)


def can_change_priority_incident(user, incident):
    return _check(_ensure_can_change_priority, user, incident)


def get_incident_permissions(user, incident):
    return {
        "can_start": can_start_incident(user, incident),
        "can_resolve": can_resolve_incident(user, incident),
        "can_archive": can_archive_incident(user, incident),
        "can_comment": can_comment_incident(user, incident),
        "can_assign_project": can_assign_project_incident(user, incident),
        "can_edit_description": can_edit_description_incident(user, incident),
        "can_claim": can_claim_incident(user, incident),
        "can_change_priority": can_change_priority_incident(user, incident),
    }


def create_incident(
    *, title, project=None, team=None, description="", priority="moyenne", external_reference_id=None, actor=None
):
    if bool(project) == bool(team):
        raise IncidentValidationError(
            "Un incident doit être rattaché à un projet ou à un groupe, jamais les deux, jamais aucun des deux."
        )

    if actor is not None:
        _require_member(actor, Incident(project=project, team=team))
    # actor is None : appel système — pas de contrainte de groupe, l'appel ne
    # vient pas d'un utilisateur. Intégration ticketing réelle pas encore
    # construite, mais atteignable dès maintenant en dev via le
    # debug-user-id marqué `is_service_account` (voir
    # `apps.incidents.views.IncidentViewSet.create`), qui passe `actor=None`
    # exprès pour simuler ce futur appel.

    return Incident.objects.create(
        project=project,
        team=team,
        title=title,
        description=description,
        priority=priority,
        external_reference_id=external_reference_id,
        status="signale",
    )


def assign_incident_to_project(*, actor, incident, project):
    _ensure_can_assign_project(actor, incident)
    # Même règle d'appartenance que partout ailleurs dans cette app (voir
    # `_is_member_via_project`) : pour un projet collaboratif, l'appartenance
    # au groupe suffit, pas besoin d'une `ProjectMembership` individuelle.
    if not _is_member_via_project(actor, project):
        raise IncidentPermissionError("Vous devez être membre du projet de destination pour y rattacher cet incident.")

    with record_changes(incident, actor=actor):
        incident.project = project
        incident.team = None
        incident.save(update_fields=["project", "team"])
    return incident


def claim_incident(*, actor, incident):
    _ensure_can_claim(actor, incident)

    with record_changes(incident, actor=actor):
        incident.assigned_to = actor
        incident.save(update_fields=["assigned_to"])
    return incident


def update_incident_priority(*, actor, incident, priority):
    _ensure_can_change_priority(actor, incident)

    with record_changes(incident, actor=actor):
        incident.priority = priority
        incident.save(update_fields=["priority"])
    return incident


def start_incident(*, actor, incident):
    _ensure_can_start(actor, incident)

    with record_changes(incident, actor=actor):
        incident.status = "en_cours"
        incident.save()
    return incident


def resolve_incident(*, actor, incident):
    _ensure_can_resolve(actor, incident)

    with record_changes(incident, actor=actor):
        incident.status = "resolu"
        incident.save()
    incident_resolved.send(sender=Incident, incident=incident, actor=actor)
    return incident


def archive_incident(*, actor, incident):
    _ensure_can_archive(actor, incident)

    with record_changes(incident, actor=actor):
        incident.status = "archive"
        incident.save()
    return incident


def update_incident_description(*, actor, incident, description):
    _ensure_can_edit_description(actor, incident)

    with record_changes(incident, actor=actor):
        incident.description = description.strip()
        incident.save()
    return incident


def add_comment(*, actor, incident, content):
    _ensure_can_comment(actor, incident)
    if not content or not content.strip():
        raise IncidentValidationError("Le commentaire ne peut pas être vide.")

    comment = IncidentComment.objects.create(incident=incident, author=actor, content=content.strip())
    incident_commented.send(sender=Incident, incident=incident, comment=comment, actor=actor)
    return comment
