"""Logique métier du module Planning.

Toute la logique vit ici (gardes de permission + transitions + mise en forme
des dicts de réponse), les vues ne font que router et traduire les exceptions
(CLAUDE.md règle n°1). Pattern « fonction de garde » identique au reste du
projet : `_ensure_can_X` lève, `can_X` renvoie un booléen via `_check`.
"""

from dateutil.rrule import rrulestr
from django.db.models import Q
from django.utils import timezone

from apps.common.audit import record_changes
from apps.common.permissions import check_permission
from apps.projects.models import ProjectMembership
from apps.projects.services import is_project_manager, is_project_member

from .models import (
    CalendarEvent,
    CalendarShare,
    EventParticipant,
    ProjectPlanningEntry,
    ScheduledBlock,
)
from .signals import event_participant_invited


class PlanningPermissionError(Exception):
    """L'acteur n'a pas le droit d'effectuer cette action."""


class PlanningValidationError(Exception):
    """Les données fournies sont invalides."""


_PLANNING_EXCEPTIONS = (PlanningPermissionError, PlanningValidationError)

# Garde-fou : une série n'est jamais expansée au-delà de cette limite dans une
# fenêtre donnée, même si la RRULE est infinie.
MAX_OCCURRENCES = 366
# Largeur maximale d'une fenêtre de lecture (jours) — appliquée par la vue.
MAX_WINDOW_DAYS = 92


def _check(fn, *args):
    return check_permission(fn, *args, catch=_PLANNING_EXCEPTIONS)


def _require_actor(actor):
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise PlanningPermissionError("Utilisateur non identifié.")


# --- Validation --------------------------------------------------------------


def _validate_window(start, end):
    if end <= start:
        raise PlanningValidationError("La fin doit être postérieure au début.")


# Fréquences sous-journalières refusées : une fenêtre de 92 jours en
# FREQ=SECONDLY forcerait `rrule.between` à matérialiser des millions de
# dates avant même le plafond MAX_OCCURRENCES — refus à l'écriture (l'API
# est ouverte, cf. CLAUDE.md).
_FORBIDDEN_FREQ = ("SECONDLY", "MINUTELY", "HOURLY")


def _validate_recurrence_rule(rule, dtstart):
    if not rule or not rule.strip():
        return ""
    cleaned = rule.strip()
    upper = cleaned.upper()
    if any(f"FREQ={freq}" in upper for freq in _FORBIDDEN_FREQ):
        raise PlanningValidationError(
            "Les récurrences infra-journalières ne sont pas prises en charge."
        )
    try:
        rrulestr(cleaned, dtstart=dtstart)
    except (ValueError, TypeError) as exc:  # pragma: no cover - message only
        raise PlanningValidationError(f"Règle de récurrence invalide : {exc}")
    return cleaned


# --- Expansion des occurrences ---------------------------------------------


def _overlaps(occ_start, occ_end, window_start, window_end):
    return occ_start < window_end and occ_end > window_start


def expand_occurrences(sources, window_start, window_end):
    """Développe une liste d'objets récurrents (portant `.start`, `.end`,
    `.recurrence_rule`) en occurrences concrètes chevauchant
    [window_start, window_end].

    Retourne une liste de dicts ``{"source", "occurrence_start", "start",
    "end"}`` (datetimes aware), triée par `start`. Un événement ponctuel donne
    0 ou 1 occurrence ; une série est bornée par la fenêtre ET par
    ``MAX_OCCURRENCES``.

    L'expansion se fait en heure locale (Europe/Paris) pour que l'heure
    d'horloge reste stable de part et d'autre des changements d'heure été/hiver
    — chaque occurrence est ensuite reconvertie en datetime aware.
    """

    results = []
    local_window_start = timezone.localtime(window_start)
    local_window_end = timezone.localtime(window_end)

    for source in sources:
        duration = source.end - source.start
        rule = (source.recurrence_rule or "").strip()

        if not rule:
            if _overlaps(source.start, source.end, window_start, window_end):
                results.append(
                    {
                        "source": source,
                        "occurrence_start": source.start,
                        "start": source.start,
                        "end": source.end,
                    }
                )
            continue

        local_start = timezone.localtime(source.start)
        try:
            recurrence = rrulestr(rule, dtstart=local_start)
        except (ValueError, TypeError):
            continue

        # `.between` renvoie les débuts d'occurrence dans l'intervalle ; on
        # élargit la borne basse d'une durée pour attraper une occurrence qui
        # commence avant la fenêtre mais s'y termine.
        candidates = recurrence.between(
            local_window_start - duration, local_window_end, inc=True
        )
        for occ_local_start in candidates[:MAX_OCCURRENCES]:
            occ_start = occ_local_start.astimezone(timezone.get_current_timezone())
            occ_end = occ_start + duration
            if _overlaps(occ_start, occ_end, window_start, window_end):
                results.append(
                    {
                        "source": source,
                        "occurrence_start": occ_start,
                        "start": occ_start,
                        "end": occ_end,
                    }
                )

    results.sort(key=lambda item: item["start"])
    return results


# --- Mise en forme ---------------------------------------------------------


def _user_dict(user):
    if user is None:
        return None
    return {
        "id": str(user.id),
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


def _iso(dt):
    """ISO 8601 en heure locale (Europe/Paris) — cohérent entre les occurrences
    expansées (déjà localisées) et les datetimes bruts de la BDD (stockés en
    UTC). Le frontend s'appuie sur l'offset local pour dériver le jour."""
    if dt is None:
        return None
    if timezone.is_aware(dt):
        return timezone.localtime(dt).isoformat()
    return dt.isoformat()


def _participants_payload(event):
    return [
        {
            "id": str(p.id),
            "user": _user_dict(p.user),
            "response": p.response,
            "response_display": p.get_response_display(),
        }
        for p in event.participants.all()
        if p.status == "active"
    ]


def _event_occurrence_dict(occ, *, actor, read_only=False):
    event = occ["source"]
    my_response = None
    if not read_only:
        mine = next(
            (p for p in event.participants.all() if p.user_id == actor.id and p.status == "active"),
            None,
        )
        my_response = mine.response if mine else None
    return {
        "type": "event",
        "id": str(event.id),
        "occurrence_start": _iso(occ["occurrence_start"]),
        "start": _iso(occ["start"]),
        "end": _iso(occ["end"]),
        "all_day": event.all_day,
        "title": event.title,
        "description": event.description,
        "location": event.location,
        "status": event.status,
        "recurrence_rule": event.recurrence_rule,
        "is_recurring": bool(event.recurrence_rule),
        "owner": _user_dict(event.owner),
        "is_owner": event.owner_id == actor.id,
        "read_only": read_only or event.owner_id != actor.id,
        "participants": _participants_payload(event) if not read_only else [],
        "my_response": my_response,
        "permissions": get_calendar_event_permissions(actor, event),
    }


def _task_summary(task):
    if task is None:
        return None
    return {
        "id": str(task.id),
        "title": task.title,
        "status": task.status,
        "status_display": task.get_status_display(),
        "priority": task.priority,
        "project_id": str(task.project_id),
        "project_name": task.project.name,
    }


def _incident_summary(incident):
    if incident is None:
        return None
    return {
        "id": str(incident.id),
        "title": incident.title,
        "status": incident.status,
        "status_display": incident.get_status_display(),
        "priority": incident.priority,
        "project_id": str(incident.project_id) if incident.project_id else None,
    }


def _block_dict(block):
    return {
        "type": "block",
        "id": str(block.id),
        "start": _iso(block.start),
        "end": _iso(block.end),
        "status": block.status,
        "title": (block.task.title if block.task_id else block.incident.title),
        "task": _task_summary(block.task) if block.task_id else None,
        "incident": _incident_summary(block.incident) if block.incident_id else None,
    }


def _project_entry_occurrence_dict(occ, *, actor):
    entry = occ["source"]
    return {
        "type": "project_entry",
        "id": str(entry.id),
        "occurrence_start": _iso(occ["occurrence_start"]),
        "start": _iso(occ["start"]),
        "end": _iso(occ["end"]),
        "all_day": entry.all_day,
        "title": entry.title,
        "description": entry.description,
        "kind": entry.kind,
        "kind_display": entry.get_kind_display(),
        "status": entry.status,
        "project_id": str(entry.project_id),
        "project_name": entry.project.name,
        "assignee": _user_dict(entry.assignee) if entry.assignee_id else None,
        "recurrence_rule": entry.recurrence_rule,
        "is_recurring": bool(entry.recurrence_rule),
        "permissions": {"can_manage": is_project_manager(actor, entry.project)},
    }


# --- Agrégat calendrier ---------------------------------------------------


def _member_project_ids(actor):
    return list(
        ProjectMembership.objects.filter(user=actor, status="active").values_list("project_id", flat=True)
    )


def get_calendar(*, actor, window_start, window_end, owner_ids=None, project_ids=None):
    _require_actor(actor)
    _validate_window(window_start, window_end)

    # Événements : les miens + ceux où je suis participant actif.
    events = list(
        CalendarEvent.objects.filter(
            Q(owner=actor) | Q(participants__user=actor, participants__status="active")
        )
        .distinct()
        .select_related("owner")
        .prefetch_related("participants__user")
    )
    event_occs = expand_occurrences(events, window_start, window_end)

    # Créneaux tâches/incidents (non récurrents).
    blocks = (
        ScheduledBlock.objects.filter(owner=actor)
        .select_related("task", "task__project", "incident", "incident__project")
    )
    block_dicts = [
        _block_dict(b)
        for b in blocks
        if _overlaps(b.start, b.end, window_start, window_end)
    ]

    # Planning des projets dont je suis membre.
    member_project_ids = _member_project_ids(actor)
    if project_ids:
        wanted = {str(pid) for pid in project_ids}
        member_project_ids = [pid for pid in member_project_ids if str(pid) in wanted]
    entries = list(
        ProjectPlanningEntry.objects.filter(project_id__in=member_project_ids).select_related("project", "assignee")
    )
    entry_occs = expand_occurrences(entries, window_start, window_end)

    # Calendriers partagés avec moi (lecture seule).
    shares = CalendarShare.objects.filter(grantee=actor).select_related("owner")
    if owner_ids:
        wanted_owners = {str(oid) for oid in owner_ids}
        shares = [s for s in shares if str(s.owner_id) in wanted_owners]
    shared = []
    for share in shares:
        shared_events = list(
            CalendarEvent.objects.filter(owner=share.owner).prefetch_related("participants__user")
        )
        shared_occs = expand_occurrences(shared_events, window_start, window_end)
        shared.append(
            {
                "owner": _user_dict(share.owner),
                "share_id": str(share.id),
                "occurrences": [
                    _event_occurrence_dict(occ, actor=actor, read_only=True) for occ in shared_occs
                ],
            }
        )

    return {
        "window_start": _iso(window_start),
        "window_end": _iso(window_end),
        "events": [_event_occurrence_dict(occ, actor=actor) for occ in event_occs],
        "blocks": block_dicts,
        "project_entries": [_project_entry_occurrence_dict(occ, actor=actor) for occ in entry_occs],
        "shared": shared,
    }


# --- Événements personnels ----------------------------------------------


def _ensure_can_edit_event(actor, event):
    _require_actor(actor)
    if event.owner_id != actor.id:
        raise PlanningPermissionError("Seul l'organisateur peut modifier cet événement.")


def get_calendar_event_permissions(user, event):
    can_edit = _check(_ensure_can_edit_event, user, event)
    return {"can_edit": can_edit, "can_manage_participants": can_edit}


def _event_detail_dict(event, *, actor):
    from apps.common.audit import get_audit_log

    return {
        "id": str(event.id),
        "title": event.title,
        "description": event.description,
        "location": event.location,
        "start": _iso(event.start),
        "end": _iso(event.end),
        "all_day": event.all_day,
        "recurrence_rule": event.recurrence_rule,
        "is_recurring": bool(event.recurrence_rule),
        "status": event.status,
        "status_display": event.get_status_display(),
        "owner": _user_dict(event.owner),
        "is_owner": event.owner_id == actor.id,
        "participants": _participants_payload(event),
        "permissions": get_calendar_event_permissions(actor, event),
        "audit_log": [
            {
                "field_name": e.field_name,
                "old_value": e.old_value,
                "new_value": e.new_value,
                "actor": _user_dict(e.actor),
                "created_at": _iso(e.created_at),
            }
            for e in get_audit_log(event)
        ],
    }


def create_event(*, actor, title, start, end, all_day=False, description="", location="", recurrence_rule=""):
    _require_actor(actor)
    if not title or not title.strip():
        raise PlanningValidationError("Le titre est obligatoire.")
    _validate_window(start, end)
    rule = _validate_recurrence_rule(recurrence_rule, start)
    return CalendarEvent.objects.create(
        owner=actor,
        title=title.strip()[:255],
        description=description or "",
        location=(location or "").strip()[:255],
        start=start,
        end=end,
        all_day=all_day,
        recurrence_rule=rule,
    )


_UNSET = object()


def update_event(
    *,
    actor,
    event,
    title=_UNSET,
    description=_UNSET,
    location=_UNSET,
    start=_UNSET,
    end=_UNSET,
    all_day=_UNSET,
    recurrence_rule=_UNSET,
):
    _ensure_can_edit_event(actor, event)
    new_start = event.start if start is _UNSET else start
    new_end = event.end if end is _UNSET else end
    _validate_window(new_start, new_end)
    with record_changes(event, actor=actor):
        if title is not _UNSET:
            if not title or not title.strip():
                raise PlanningValidationError("Le titre est obligatoire.")
            event.title = title.strip()[:255]
        if description is not _UNSET:
            event.description = description or ""
        if location is not _UNSET:
            event.location = (location or "").strip()[:255]
        if start is not _UNSET:
            event.start = start
        if end is not _UNSET:
            event.end = end
        if all_day is not _UNSET:
            event.all_day = all_day
        if recurrence_rule is not _UNSET:
            event.recurrence_rule = _validate_recurrence_rule(recurrence_rule, new_start)
        event.save()
    return event


def cancel_event(*, actor, event):
    _ensure_can_edit_event(actor, event)
    event.status = "annule"
    event.save(update_fields=["status", "updated_at"])
    return event


def add_participant(*, actor, event, user):
    _ensure_can_edit_event(actor, event)
    if user.id == event.owner_id:
        raise PlanningValidationError("L'organisateur est déjà sur l'événement.")
    participant, created = EventParticipant.objects.get_or_create(
        event=event, user=user, status="active", defaults={"response": "invite"}
    )
    if created:
        event_participant_invited.send(
            sender=CalendarEvent, event=event, participant=participant, actor=actor
        )
    return participant


def remove_participant(*, actor, participant):
    _ensure_can_edit_event(actor, participant.event)
    participant.status = "removed"
    participant.save(update_fields=["status", "updated_at"])
    return participant


def respond_to_event(*, actor, event, response):
    _require_actor(actor)
    if response not in {"accepte", "refuse"}:
        raise PlanningValidationError("Réponse invalide.")
    try:
        participant = EventParticipant.objects.get(event=event, user=actor, status="active")
    except EventParticipant.DoesNotExist:
        raise PlanningPermissionError("Vous n'êtes pas invité à cet événement.")
    participant.response = response
    participant.save(update_fields=["response", "updated_at"])
    return participant


# --- Créneaux tâches/incidents ----------------------------------------


def _target_project(task, incident):
    if task is not None:
        return task.project
    return incident.project if incident.project_id else None


def _ensure_can_schedule(actor, *, task, incident):
    _require_actor(actor)
    if task is not None:
        if task.assignee_id != actor.id:
            raise PlanningPermissionError("Vous ne pouvez planifier qu'une tâche qui vous est assignée.")
        if not is_project_member(actor, task.project):
            raise PlanningPermissionError("Vous n'êtes pas membre du projet de cette tâche.")
    if incident is not None:
        if incident.assigned_to_id != actor.id:
            raise PlanningPermissionError("Vous ne pouvez planifier qu'un incident qui vous est assigné.")
        project = incident.project if incident.project_id else None
        if project is not None and not is_project_member(actor, project):
            raise PlanningPermissionError("Vous n'êtes pas membre du projet de cet incident.")


def _ensure_can_edit_block(actor, block):
    _require_actor(actor)
    if block.owner_id != actor.id:
        raise PlanningPermissionError("Ce créneau ne vous appartient pas.")


def create_block(*, actor, task=None, incident=None, start, end):
    if (task is None) == (incident is None):
        raise PlanningValidationError("Un créneau porte sur exactement une tâche ou un incident.")
    _validate_window(start, end)
    _ensure_can_schedule(actor, task=task, incident=incident)
    return ScheduledBlock.objects.create(owner=actor, task=task, incident=incident, start=start, end=end)


def update_block(*, actor, block, start=None, end=None):
    _ensure_can_edit_block(actor, block)
    new_start = start if start is not None else block.start
    new_end = end if end is not None else block.end
    _validate_window(new_start, new_end)
    with record_changes(block, actor=actor):
        block.start = new_start
        block.end = new_end
        block.save()
    return block


def cancel_block(*, actor, block):
    _ensure_can_edit_block(actor, block)
    block.status = "annule"
    block.save(update_fields=["status", "updated_at"])
    return block


# --- Planning projet -------------------------------------------------


def _ensure_can_manage_project_planning(actor, project):
    _require_actor(actor)
    if not is_project_manager(actor, project):
        raise PlanningPermissionError("Seul un chef de projet peut modifier le planning du projet.")


def _ensure_can_view_project_planning(actor, project):
    _require_actor(actor)
    if not is_project_member(actor, project):
        raise PlanningPermissionError("Seul un membre du projet peut consulter son planning.")


def list_project_entries(*, actor, project, window_start, window_end):
    _ensure_can_view_project_planning(actor, project)
    _validate_window(window_start, window_end)
    entries = list(
        ProjectPlanningEntry.objects.filter(project=project).select_related("project", "assignee")
    )
    occs = expand_occurrences(entries, window_start, window_end)
    return {
        "can_manage": is_project_manager(actor, project),
        "entries": [_project_entry_occurrence_dict(occ, actor=actor) for occ in occs],
    }


def create_project_entry(
    *,
    actor,
    project,
    title,
    start,
    end,
    kind="autre",
    all_day=False,
    description="",
    assignee=None,
    recurrence_rule="",
):
    _ensure_can_manage_project_planning(actor, project)
    if not title or not title.strip():
        raise PlanningValidationError("Le titre est obligatoire.")
    _validate_window(start, end)
    if kind not in dict(ProjectPlanningEntry.KIND_CHOICES):
        raise PlanningValidationError("Type d'entrée invalide.")
    if assignee is not None and not is_project_member(assignee, project):
        raise PlanningValidationError("La personne assignée doit être membre du projet.")
    rule = _validate_recurrence_rule(recurrence_rule, start)
    return ProjectPlanningEntry.objects.create(
        project=project,
        title=title.strip()[:255],
        description=description or "",
        kind=kind,
        all_day=all_day,
        assignee=assignee,
        start=start,
        end=end,
        recurrence_rule=rule,
    )


def update_project_entry(
    *,
    actor,
    entry,
    title=_UNSET,
    description=_UNSET,
    kind=_UNSET,
    all_day=_UNSET,
    assignee=_UNSET,
    start=_UNSET,
    end=_UNSET,
    recurrence_rule=_UNSET,
):
    _ensure_can_manage_project_planning(actor, entry.project)
    new_start = entry.start if start is _UNSET else start
    new_end = entry.end if end is _UNSET else end
    _validate_window(new_start, new_end)
    with record_changes(entry, actor=actor):
        if title is not _UNSET:
            if not title or not title.strip():
                raise PlanningValidationError("Le titre est obligatoire.")
            entry.title = title.strip()[:255]
        if description is not _UNSET:
            entry.description = description or ""
        if kind is not _UNSET:
            if kind not in dict(ProjectPlanningEntry.KIND_CHOICES):
                raise PlanningValidationError("Type d'entrée invalide.")
            entry.kind = kind
        if all_day is not _UNSET:
            entry.all_day = all_day
        if assignee is not _UNSET:
            if assignee is not None and not is_project_member(assignee, entry.project):
                raise PlanningValidationError("La personne assignée doit être membre du projet.")
            entry.assignee = assignee
        if start is not _UNSET:
            entry.start = start
        if end is not _UNSET:
            entry.end = end
        if recurrence_rule is not _UNSET:
            entry.recurrence_rule = _validate_recurrence_rule(recurrence_rule, new_start)
        entry.save()
    return entry


def cancel_project_entry(*, actor, entry):
    _ensure_can_manage_project_planning(actor, entry.project)
    entry.status = "annule"
    entry.save(update_fields=["status", "updated_at"])
    return entry


# --- Partage de calendrier ------------------------------------------


def create_share(*, actor, grantee):
    _require_actor(actor)
    if grantee.id == actor.id:
        raise PlanningValidationError("Vous ne pouvez pas partager votre calendrier avec vous-même.")
    share, _ = CalendarShare.objects.get_or_create(owner=actor, grantee=grantee, status="active")
    return share


def revoke_share(*, actor, share):
    _require_actor(actor)
    if actor.id not in {share.owner_id, share.grantee_id}:
        raise PlanningPermissionError("Ce partage ne vous concerne pas.")
    share.status = "revoked"
    share.save(update_fields=["status", "updated_at"])
    return share


def _share_dict(share):
    return {
        "id": str(share.id),
        "owner": _user_dict(share.owner),
        "grantee": _user_dict(share.grantee),
        "created_at": _iso(share.created_at),
    }


def list_shares(*, actor):
    _require_actor(actor)
    return {
        "granted": [
            _share_dict(s)
            for s in CalendarShare.objects.filter(owner=actor).select_related("owner", "grantee")
        ],
        "received": [
            _share_dict(s)
            for s in CalendarShare.objects.filter(grantee=actor).select_related("owner", "grantee")
        ],
    }
