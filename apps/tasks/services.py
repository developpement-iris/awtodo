from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Count, F, Sum
from django.db.models.functions import TruncWeek
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.common.audit import record_changes, record_event
from apps.common.choices import PRIORITY_CHOICES
from apps.common.permissions import check_permission
from apps.projects.models import ProjectMembership
from apps.projects.services import (
    contributor_projects,
    get_current_version,
    is_project_contributor,
    is_project_manager,
)

from .models import Task, TaskComment
from .signals import task_assigned, task_commented, task_completed

COMPLETION_TREND_WEEKS = 8


class TaskPermissionError(Exception):
    """L'acteur n'a pas le rôle requis pour effectuer cette action."""


class InvalidTransitionError(Exception):
    """Le statut de départ ou les données fournies ne permettent pas cette transition."""


_TASK_EXCEPTIONS = (TaskPermissionError, InvalidTransitionError)


def _check(fn, *args):
    return check_permission(fn, *args, catch=_TASK_EXCEPTIONS)


def _require_actor(actor):
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise TaskPermissionError("Utilisateur non identifié.")


# Délèguent à `apps.projects.services` (import autorisé, `tasks` est plus bas
# dans la hiérarchie) plutôt que de requêter `ProjectMembership` en direct —
# une seule définition de "peut contribuer" (exclut `lecteur`, filtre
# `status="active"`) et "est chef de projet", partagée avec `apps.projects`.
def _is_member(user, project):
    return is_project_contributor(user, project)


def _is_manager(user, project):
    return is_project_manager(user, project)


def _require_member(actor, project):
    _require_actor(actor)
    if not _is_member(actor, project):
        raise TaskPermissionError("Seul un membre du projet (hors lecture seule) peut effectuer cette action.")


def _require_manager(actor, project):
    _require_actor(actor)
    if not _is_manager(actor, project):
        raise TaskPermissionError("Seul un chef de projet du projet peut effectuer cette action.")


# --- Fonctions de garde ---------------------------------------------------
# Chacune lève TaskPermissionError/InvalidTransitionError si l'action n'est
# pas possible pour cet acteur sur cette tâche dans son état actuel. Seule
# source de vérité pour chaque règle : utilisée à la fois par la transition
# réelle (laisse l'exception remonter en 403/400) et par le flag `can_*`
# correspondant exposé côté API (voir `get_task_permissions` plus bas), via
# `_check` ci-dessus — pas de logique dupliquée entre les deux usages.


def _ensure_can_rename(actor, task):
    _require_member(actor, task.project)


def _ensure_can_comment(actor, task):
    # Même règle que renommer/éditer la description : tout membre du
    # projet, pas réservé à l'assigné (_ensure_can_rename, ligne 67).
    _require_member(actor, task.project)


def can_comment_task(user, task):
    return _check(_ensure_can_comment, user, task)


def _ensure_can_validate(actor, task):
    _require_manager(actor, task.project)
    if task.status != "en_attente_validation":
        raise InvalidTransitionError("Seule une tâche en attente de validation peut être validée.")


def _ensure_can_reject(actor, task):
    _require_manager(actor, task.project)
    if task.status != "en_attente_validation":
        raise InvalidTransitionError("Seule une tâche en attente de validation peut être rejetée.")


def _ensure_can_cancel(actor, task):
    # Même autorité que le rejet (`_ensure_can_reject`, chef de projet) —
    # l'annulation est la même décision de gestion, prise plus tard dans le
    # cycle de vie. `en_attente_validation` est délibérément exclue : c'est
    # le rejet qui couvre ce cas-là, pas d'annulation avant même validation.
    _require_manager(actor, task.project)
    if task.status not in {"disponible", "assignee", "en_cours"}:
        raise InvalidTransitionError(
            "Seule une tâche disponible, assignée ou en cours peut être annulée."
        )


def _ensure_can_reactivate(actor, task):
    # Même autorité que l'annulation (chef de projet, `_ensure_can_cancel`) —
    # revenir sur une décision de gestion reste une décision de gestion.
    _require_manager(actor, task.project)
    if task.status != "annulee":
        raise InvalidTransitionError("Seule une tâche annulée peut être réactivée.")


def _ensure_can_claim(actor, task):
    _require_member(actor, task.project)
    if task.status != "disponible":
        raise InvalidTransitionError("Seule une tâche disponible peut être auto-attribuée.")


def _ensure_can_assign(actor, task):
    _require_manager(actor, task.project)
    if task.status not in {"disponible", "assignee"}:
        raise InvalidTransitionError(
            "L'attribution manuelle n'est possible que depuis « disponible », ou pour réassigner "
            "une tâche déjà « assignée »."
        )


def _ensure_can_start(actor, task):
    # `_require_member` (= contributeur) en plus du contrôle d'assigné : ferme
    # le cas d'un assigné rétrogradé en `lecteur` après coup, qui resterait
    # sinon `task.assignee_id == actor.id`.
    _require_member(actor, task.project)
    if task.assignee_id != getattr(actor, "id", None):
        raise TaskPermissionError("Seul l'assigné actuel peut démarrer cette tâche.")
    if task.status != "assignee":
        raise InvalidTransitionError("Seule une tâche assignée peut être démarrée.")


def _ensure_can_complete(actor, task):
    _require_member(actor, task.project)
    is_assignee = task.assignee_id == getattr(actor, "id", None)
    if not is_assignee and not _is_manager(actor, task.project):
        raise TaskPermissionError("Seul l'assigné actuel ou un chef de projet peut clôturer cette tâche.")
    if task.status != "en_cours":
        raise InvalidTransitionError("Seule une tâche en cours peut être clôturée.")


def can_rename_task(user, task):
    return _check(_ensure_can_rename, user, task)


def can_validate_task(user, task):
    return _check(_ensure_can_validate, user, task)


def can_reject_task(user, task):
    return _check(_ensure_can_reject, user, task)


def can_cancel_task(user, task):
    return _check(_ensure_can_cancel, user, task)


def can_reactivate_task(user, task):
    return _check(_ensure_can_reactivate, user, task)


def can_claim_task(user, task):
    return _check(_ensure_can_claim, user, task)


def can_assign_task(user, task):
    return _check(_ensure_can_assign, user, task)


def can_start_task(user, task):
    return _check(_ensure_can_start, user, task)


def can_complete_task(user, task):
    return _check(_ensure_can_complete, user, task)


def get_assigned_tasks_for_admin(*, actor, target_user):
    """Fiche utilisateur de l'écran Administration > Membres (voir
    docs/organisation-et-comptes.md) — exception assumée au scoping par
    appartenance : un `organisation_role=admin` peut consulter la charge de
    travail complète d'un membre de sa propre organisation, y compris sur des
    projets dont l'admin consultant n'est lui-même pas membre. Ne remonte que
    la liste des tâches assignées, jamais le détail des projets en question."""
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise TaskPermissionError("Utilisateur non identifié.")
    if getattr(actor, "organisation_role", None) != "admin":
        raise TaskPermissionError("Seul un administrateur de l'organisation peut consulter la charge de travail d'un membre.")
    if target_user.organisation_id != actor.organisation_id:
        raise TaskPermissionError("Cet utilisateur n'appartient pas à votre organisation.")

    return Task.objects.active().filter(assignee=target_user).select_related("project")


def get_project_user_stats(*, actor, project):
    """Onglet Statistiques du hub projet (voir docs/modeles-et-api.md) —
    statistiques par utilisateur : tâches réalisées (`archivee`), tâches en
    cours (`en_cours`), heures passées (somme de `time_spent`, uniquement
    renseigné à la clôture). Un chef de projet voit tous les membres actifs
    du projet ; un simple membre ne voit que sa propre ligne. `Task.all_objects`
    (pas le manager `.active()` par défaut) : `archivee` est un statut
    terminal, exclu de `Task.ACTIVE_STATUSES`, mais c'est justement le
    statut qui compte comme "tâche réalisée" ici."""
    _require_member(actor, project)

    if _is_manager(actor, project):
        users = [
            membership.user
            for membership in ProjectMembership.objects.filter(
                project=project, status="active", role__in=ProjectMembership.CONTRIBUTOR_ROLES
            ).select_related("user")
        ]
    else:
        users = [actor]

    stats = []
    for user in users:
        done_qs = Task.all_objects.filter(project=project, assignee=user, status="archivee")
        stats.append(
            {
                "user": user,
                "tasks_done": done_qs.count(),
                "tasks_in_progress": Task.all_objects.filter(
                    project=project, assignee=user, status="en_cours"
                ).count(),
                "hours_spent": done_qs.aggregate(total=Sum("time_spent"))["total"] or Decimal("0"),
            }
        )
    return stats


def _completion_trend(done_qs, weeks=COMPLETION_TREND_WEEKS):
    """Nombre de tâches terminées par semaine sur une fenêtre glissante de
    `weeks` semaines (dont la semaine en cours) — graphique en barres de
    l'écran Statistiques (voir docs/modeles-et-api.md). Les semaines sans
    tâche terminée sont incluses à 0 : l'axe temporel doit rester continu,
    pas seulement les semaines où il s'est passé quelque chose."""
    since = timezone.now() - timedelta(weeks=weeks - 1)
    counts_by_week = {
        row["week"].date(): row["count"]
        for row in (
            done_qs.filter(updated_at__gte=since)
            .annotate(week=TruncWeek("updated_at"))
            .values("week")
            .annotate(count=Count("id"))
        )
    }

    today = timezone.localdate()
    current_week_start = today - timedelta(days=today.weekday())
    return [
        {
            "week_start": current_week_start - timedelta(weeks=offset),
            "count": counts_by_week.get(current_week_start - timedelta(weeks=offset), 0),
        }
        for offset in range(weeks - 1, -1, -1)
    ]


def _task_insights(tasks_qs):
    """Widgets "délais / heures passées / respect des échéances / personnes
    sollicitées" (voir docs/modeles-et-api.md > "Statistiques") — factorisé
    car utilisé à l'identique par l'onglet Statistiques d'un projet
    (`get_project_task_insights`) et par l'écran Statistiques global
    (`get_global_task_stats`), seule la portée de `tasks_qs` change.

    Pas de champ `completed_at` dédié sur `Task` : `updated_at` (auto_now)
    au moment où `complete_task` passe le statut à `archivee` sert de date
    de complétion — une tâche archivée n'est plus modifiée ensuite dans les
    flux existants, donc `updated_at` reste fiable comme proxy, sans
    migration supplémentaire."""
    done = tasks_qs.filter(status="archivee")
    hours_total = done.aggregate(total=Sum("time_spent"))["total"] or Decimal("0")

    lead_times_days = [
        (task.updated_at.date() - task.created_at.date()).days
        for task in done.only("created_at", "updated_at")
    ]
    avg_lead_time_days = round(sum(lead_times_days) / len(lead_times_days), 1) if lead_times_days else None

    done_with_deadline = done.exclude(deadline__isnull=True)
    tasks_on_time = done_with_deadline.filter(updated_at__date__lte=F("deadline")).count()
    tasks_late = done_with_deadline.count() - tasks_on_time

    contributors_count = tasks_qs.exclude(assignee__isnull=True).values("assignee").distinct().count()

    priority_breakdown = {choice: tasks_qs.filter(priority=choice).count() for choice, _ in PRIORITY_CHOICES}

    estimated_hours_total = tasks_qs.aggregate(total=Sum("estimated_hours"))["total"] or Decimal("0")

    done_with_estimate = done.exclude(estimated_hours__isnull=True)
    tasks_over_estimate = done_with_estimate.filter(time_spent__gt=F("estimated_hours")).count()
    tasks_under_estimate = done_with_estimate.count() - tasks_over_estimate

    # --- Ajouts session du 2026-10-01 (module Dashboard) -------------------
    total_count = tasks_qs.count()
    cancelled_or_rejected = tasks_qs.filter(status__in=("rejetee", "annulee")).count()
    cancellation_rate = round(cancelled_or_rejected / total_count, 3) if total_count else None

    # Âge du backlog : tâches encore actives, par ancienneté depuis la
    # création — buckets fixes, pas paramétrables par widget en v1 (pas
    # demandé).
    active_qs = tasks_qs.filter(status__in=Task.ACTIVE_STATUSES)
    now = timezone.now()
    backlog_age_buckets = {
        "0_7j": active_qs.filter(created_at__gte=now - timedelta(days=7)).count(),
        "8_14j": active_qs.filter(
            created_at__lt=now - timedelta(days=7), created_at__gte=now - timedelta(days=14)
        ).count(),
        "plus_14j": active_qs.filter(created_at__lt=now - timedelta(days=14)).count(),
    }

    # Charge actuelle par personne : tâches ACTIVES (pas seulement terminées,
    # contrairement à `get_project_user_stats`) — "qui est surchargé en ce
    # moment", pas un historique.
    active_tasks_by_assignee = dict(
        active_qs.exclude(assignee__isnull=True)
        .values("assignee__username")
        .annotate(count=Count("id"))
        .values_list("assignee__username", "count")
    )

    type_breakdown = {choice: tasks_qs.filter(task_type=choice).count() for choice, _ in Task.TASK_TYPE_CHOICES}

    return {
        "hours_total": hours_total,
        "avg_lead_time_days": avg_lead_time_days,
        "tasks_on_time": tasks_on_time,
        "tasks_late": tasks_late,
        "contributors_count": contributors_count,
        "priority_breakdown": priority_breakdown,
        "completion_trend": _completion_trend(done),
        "estimated_hours_total": estimated_hours_total,
        "tasks_over_estimate": tasks_over_estimate,
        "tasks_under_estimate": tasks_under_estimate,
        "cancellation_rate": cancellation_rate,
        "backlog_age_buckets": backlog_age_buckets,
        "active_tasks_by_assignee": active_tasks_by_assignee,
        "type_breakdown": type_breakdown,
    }


def get_project_task_insights(*, actor, project):
    """Widgets étendus de l'onglet Statistiques d'un projet (voir
    docs/modeles-et-api.md) — complète `get_project_user_stats` (tableau par
    membre) avec des agrégats projet entiers. Même visibilité que le reste
    de l'onglet : tout membre du projet, pas réservé au chef de projet."""
    _require_member(actor, project)
    return _task_insights(Task.all_objects.filter(project=project))


def get_global_task_stats(*, actor):
    """Écran Statistiques globales (sidebar, voir docs/modeles-et-api.md) —
    vision macroscopique sur les projets où l'utilisateur *contribue*
    (`contributor_projects`, pas `accessible_projects`) : un projet où il n'a
    qu'un droit de lecture n'entre pas dans ses statistiques globales, comme
    l'onglet Statistiques d'un projet lui est masqué."""
    _require_actor(actor)

    projects = contributor_projects(actor)
    tasks_qs = Task.all_objects.filter(project__in=projects)

    return {
        "projects_total": projects.count(),
        "projects_active": projects.filter(status="actif").count(),
        "projects_closed": projects.filter(status="cloture").count(),
        "tasks_done": tasks_qs.filter(status="archivee").count(),
        "tasks_in_progress": tasks_qs.filter(status="en_cours").count(),
        **_task_insights(tasks_qs),
    }


def get_task_insights_for_projects(project_ids):
    """Cœur de `_task_insights` directement paramétré par un ensemble de
    projets explicite — utilisé par `apps.dashboards` pour les widgets
    "groupe" à portée globale, scopés aux projets effectivement gérés par
    l'acteur (pas une délégation à `get_global_task_stats`, qui est codée en
    dur sur `contributor_projects(actor)`). Pas de garde de permission ici :
    l'appelant (`apps.dashboards.services`) a déjà résolu `project_ids` selon
    les droits de l'acteur avant d'appeler cette fonction."""
    return _task_insights(Task.all_objects.filter(project_id__in=project_ids))


def get_task_permissions(user, task):
    """Objet `permissions` exposé par `TaskSerializer` (voir CLAUDE.md >
    "Permissions API — flags calculés") — le frontend lit ces booléens au
    lieu de recalculer une règle de rôle/statut lui-même."""
    return {
        "can_rename": can_rename_task(user, task),
        "can_edit_description": can_rename_task(user, task),
        "can_edit_deadline": can_edit_deadline_task(user, task),
        # Classification (type/priorité) — même garde que titre/description,
        # ouverte à tout membre du projet (retour direct, session du
        # 2026-10-08 : pouvoir "changer le type de tâche ainsi que sa
        # priorité").
        "can_edit_type": can_rename_task(user, task),
        "can_edit_priority": can_rename_task(user, task),
        "can_comment": can_comment_task(user, task),
        "can_validate": can_validate_task(user, task),
        "can_reject": can_reject_task(user, task),
        "can_cancel": can_cancel_task(user, task),
        "can_reactivate": can_reactivate_task(user, task),
        "can_claim": can_claim_task(user, task),
        "can_assign": can_assign_task(user, task),
        "can_start": can_start_task(user, task),
        "can_complete": can_complete_task(user, task),
    }


def create_task(
    *,
    actor,
    project,
    title,
    task_type,
    description="",
    priority="moyenne",
    deadline=None,
    external_reference_id=None,
    assignee=None,
    estimated_hours=None,
):
    _require_member(actor, project)

    # Projet individuel : une seule personne travaille dessus, toute tâche lui
    # revient — auto-assignée au créateur (session du 2026-09-10). `actor` EST
    # le créateur ici : depuis le 2026-09-11, un projet individuel ne peut
    # accueillir personne d'autre que son chef de projet (le créateur) et des
    # lecteurs (`_ensure_role_allowed_for_project_type`, apps.projects) — un
    # lecteur n'étant pas contributeur, `_require_member` ci-dessus a déjà
    # écarté quiconque d'autre. Un assigné explicitement fourni (cas rare,
    # mais possible via l'API) reste respecté.
    if project.project_type == "individuel" and assignee is None:
        assignee = actor

    if _is_manager(actor, project):
        status = "assignee" if assignee else "disponible"
    else:
        status = "en_attente_validation"
        assignee = None

    if estimated_hours is not None:
        # Task.objects.create() ne convertit pas la valeur passée en Decimal
        # sur l'instance en mémoire (contrairement à ce qui se passe lors
        # d'un rechargement depuis la base) — sans cette conversion,
        # `task.estimated_hours` resterait la chaîne brute reçue en entrée.
        # Même conversion que `complete_task` pour `time_spent`.
        estimated_hours = Decimal(str(estimated_hours))

    task = Task.objects.create(
        project=project,
        # Toujours la version courante du projet au moment de la création,
        # jamais choisie manuellement (voir docs/modeles-et-api.md >
        # "ProjectVersion") — même si l'utilisateur consulte une version
        # passée au moment de créer la tâche.
        version=get_current_version(project),
        title=title,
        description=description,
        task_type=task_type,
        priority=priority,
        deadline=deadline,
        external_reference_id=external_reference_id,
        assignee=assignee,
        status=status,
        estimated_hours=estimated_hours,
    )
    # Bug remonté (session du 2026-09-16) : contrairement à `assign_task`/
    # `validate_task`, cette fonction n'a jamais émis `task_assigned` — une
    # tâche créée avec un assigné explicite différent du créateur (chef de
    # projet qui l'attribue directement dans le formulaire de création)
    # n'avertissait donc jamais la personne assignée. `notify_task_assigned`
    # (apps.notifications) ignore déjà le cas où l'assigné EST le créateur
    # (auto-assignation sur un projet individuel), pas la peine de le
    # reconditionner ici.
    if task.assignee_id:
        task_assigned.send(sender=Task, task=task, actor=actor)
    record_event(task, actor=actor, verb="created", description=f"Tâche créée : « {task.title} »", project=project)
    return task


def rename_task(*, actor, task, title):
    _ensure_can_rename(actor, task)
    if not title or not title.strip():
        raise InvalidTransitionError("Le titre ne peut pas être vide.")

    with record_changes(task, actor=actor, project=task.project):
        task.title = title.strip()
        task.save()
    return task


def update_task_description(*, actor, task, description):
    # Même règle que le renommage (_ensure_can_rename) : n'importe quel
    # membre du projet peut éditer les champs texte d'une tâche, pas
    # seulement l'assigné — cohérent avec le reste du cycle de vie.
    _ensure_can_rename(actor, task)

    with record_changes(task, actor=actor, project=task.project):
        task.description = description.strip()
        task.save()
    return task


def _ensure_can_edit_deadline(actor, task):
    """Réservé au chef de projet — à la différence du titre/description/temps
    estimé (n'importe quel membre), une échéance engage la planification du
    projet, retour direct : "droit sur la fonction propre au rôle chef de
    projet"."""
    _require_manager(actor, task.project)


def can_edit_deadline_task(user, task):
    return _check(_ensure_can_edit_deadline, user, task)


def update_task_deadline(*, actor, task, deadline):
    """`deadline` accepte une chaîne "YYYY-MM-DD", un objet `date`, ou une
    valeur vide/`None` pour supprimer l'échéance — même tolérance d'entrée
    que `update_task_estimated_hours` (conversion faite ici, pas dans la vue,
    pas de serializer dédié pour ces petites mises à jour de champ)."""
    _ensure_can_edit_deadline(actor, task)

    if deadline in (None, ""):
        deadline = None
    elif isinstance(deadline, str):
        parsed = parse_date(deadline)
        if parsed is None:
            raise InvalidTransitionError("Date d'échéance invalide (format AAAA-MM-JJ attendu).")
        deadline = parsed

    with record_changes(task, actor=actor, project=task.project):
        task.deadline = deadline
        task.save()
    return task


def update_task_estimated_hours(*, actor, task, estimated_hours):
    # Même garde que le titre/la description : tout membre du projet, pas
    # réservé à l'assigné (_ensure_can_rename).
    _ensure_can_rename(actor, task)

    if estimated_hours is not None:
        # Même piège que dans `create_task` : sans cette conversion,
        # `task.estimated_hours` resterait la chaîne brute reçue en entrée
        # sur l'instance en mémoire (le champ n'est converti en Decimal
        # qu'au rechargement depuis la base), ce qui fausserait toute
        # comparaison faite juste après l'appel sans recharger depuis la DB.
        estimated_hours = Decimal(str(estimated_hours))

    with record_changes(task, actor=actor, project=task.project):
        task.estimated_hours = estimated_hours
        task.save()
    return task


def update_task_type(*, actor, task, task_type):
    # Même garde que le titre/la description : tout membre du projet
    # (_ensure_can_rename), pas réservé au chef de projet.
    _ensure_can_rename(actor, task)
    if task_type not in dict(Task.TASK_TYPE_CHOICES):
        raise InvalidTransitionError("Type de tâche invalide.")

    with record_changes(task, actor=actor, project=task.project):
        task.task_type = task_type
        task.save()
    return task


def update_task_priority(*, actor, task, priority):
    _ensure_can_rename(actor, task)
    if priority not in dict(PRIORITY_CHOICES):
        raise InvalidTransitionError("Priorité invalide.")

    with record_changes(task, actor=actor, project=task.project):
        task.priority = priority
        task.save()
    return task


def validate_task(*, actor, task, assignee=None):
    _ensure_can_validate(actor, task)

    with record_changes(task, actor=actor, project=task.project):
        task.status = "assignee" if assignee else "disponible"
        task.assignee = assignee
        task.save()
    if assignee:
        task_assigned.send(sender=Task, task=task, actor=actor)
    return task


def reject_task(*, actor, task, rejection_reason):
    _ensure_can_reject(actor, task)
    if not rejection_reason:
        raise InvalidTransitionError("Un motif de rejet est obligatoire.")

    with record_changes(task, actor=actor, project=task.project):
        task.status = "rejetee"
        task.rejection_reason = rejection_reason
        task.save()
    return task


def cancel_task(*, actor, task, cancellation_reason):
    _ensure_can_cancel(actor, task)
    if not cancellation_reason:
        raise InvalidTransitionError("Un motif d'annulation est obligatoire.")

    with record_changes(task, actor=actor, project=task.project):
        task.status = "annulee"
        task.cancellation_reason = cancellation_reason
        task.save()
    return task


def reactivate_task(*, actor, task):
    """Fait revenir une tâche annulée dans le cycle de vie actif — même
    logique de statut de départ que `create_task` (assignée si un assigné
    est déjà renseigné, sinon disponible). `cancellation_reason` n'est pas
    effacé : il reste l'historique de la précédente annulation, cohérent
    avec le fait que `rejection_reason` n'est jamais nettoyé non plus."""
    _ensure_can_reactivate(actor, task)

    with record_changes(task, actor=actor, project=task.project):
        task.status = "assignee" if task.assignee_id else "disponible"
        task.save()
    return task


def claim_task(*, actor, task):
    _ensure_can_claim(actor, task)

    with record_changes(task, actor=actor, project=task.project):
        task.status = "assignee"
        task.assignee = actor
        task.save()
    return task


def assign_task(*, actor, task, assignee):
    _ensure_can_assign(actor, task)
    if assignee is None:
        raise InvalidTransitionError("Un assigné est requis.")
    if not _is_member(assignee, task.project):
        raise InvalidTransitionError("L'assigné doit être membre du projet.")

    with record_changes(task, actor=actor, project=task.project):
        task.status = "assignee"
        task.assignee = assignee
        task.save()
    task_assigned.send(sender=Task, task=task, actor=actor)
    return task


def start_task(*, actor, task):
    _ensure_can_start(actor, task)

    with record_changes(task, actor=actor, project=task.project):
        task.status = "en_cours"
        task.save()
    return task


def complete_task(*, actor, task, time_spent):
    _ensure_can_complete(actor, task)
    if time_spent is None or time_spent == "":
        raise InvalidTransitionError("Le temps passé est obligatoire pour clôturer une tâche.")

    try:
        time_spent = Decimal(str(time_spent))
    except InvalidOperation:
        raise InvalidTransitionError("Le temps passé doit être un nombre.")
    if time_spent <= 0:
        raise InvalidTransitionError("Le temps passé doit être un nombre positif.")

    with record_changes(task, actor=actor, project=task.project):
        task.status = "archivee"
        task.time_spent = time_spent
        task.save()
    task_completed.send(sender=Task, task=task, actor=actor)
    return task


def add_comment(*, actor, task, content):
    _ensure_can_comment(actor, task)
    if not content or not content.strip():
        raise InvalidTransitionError("Le commentaire ne peut pas être vide.")

    comment = TaskComment.objects.create(task=task, author=actor, content=content.strip())
    task_commented.send(sender=Task, task=task, comment=comment, actor=actor)
    record_event(task, actor=actor, verb="commented", description="Commentaire ajouté", project=task.project)
    return comment
