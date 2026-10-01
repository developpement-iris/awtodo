from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncWeek

from apps.accounts.services import is_organisation_admin
from apps.budgeting.models import BudgetLine
from apps.budgeting.services import get_budget_summary_for_manager
from apps.documentation.services import get_pending_doc_count
from apps.incidents.models import Incident
from apps.incidents.services import (
    get_global_incident_stats,
    get_incident_insights_for_projects,
    get_project_incident_insights,
)
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import (
    contributor_projects,
    get_project_history,
    get_scoped_history,
    is_project_manager,
    prefetched_project_roles,
)
from apps.tasks.models import Task
from apps.tasks.services import (
    get_global_task_stats,
    get_project_task_insights,
    get_project_user_stats,
    get_task_insights_for_projects,
)

from .catalog import AGGREGATIONS, CUSTOM_SOURCES, DEFAULT_METRICS
from .models import DashboardWidget


class DashboardPermissionError(Exception):
    """L'acteur n'a pas le droit de poser/consulter ce widget."""


class DashboardValidationError(Exception):
    """Les données fournies ne décrivent pas un widget valide."""


_ACTIVITY_FEED_LIMIT = 20


# --- Portée "groupe" ---------------------------------------------------------


def _group_scope_project_ids(actor):
    """Portée d'un widget "groupe" à l'échelle **globale** — il n'existe pas
    de "chef de projet" unique à cette échelle. Règle retenue (alignée sur
    `apps.budgeting.services.get_budget_summary_for_manager`, qui filtre déjà
    automatiquement plutôt que de refuser tout-ou-rien) : un admin
    d'organisation/plateforme voit tous les projets de l'organisation ;
    sinon, seulement les projets que l'acteur dirige réellement
    (`role="chef_de_projet"`) — jamais ses projets "contributeur" au sens
    large. Pas d'extension aux admins de groupe (décision explicite,
    confirmée via AskUserQuestion : on reste strictement aligné sur le
    précédent budget, pas sur la cascade plus large de
    `apps.projects.services.get_scoped_history`)."""
    if is_organisation_admin(actor, actor.organisation):
        return list(Project.all_objects.filter(organisation=actor.organisation).values_list("id", flat=True))
    return list(
        ProjectMembership.objects.filter(
            user=actor, role="chef_de_projet", status="active"
        ).values_list("project_id", flat=True)
    )


def _ensure_widget_allowed(*, actor, scope, project, visibility, group_ids_hint=None):
    """Vérifie qu'`actor` a le droit de poser (ou de voir calculé) un widget
    de cette `visibility` sur cette portée — appelée à la fois à la création
    (`create_widget`) et à chaque recalcul (`compute_widget_data`, défense en
    profondeur si le rôle de l'acteur a changé depuis). Renvoie la liste des
    `project_ids` sur laquelle les données "groupe" globales doivent être
    bornées (`None` si non applicable / portée projet).

    `group_ids_hint` : résultat déjà calculé de `_group_scope_project_ids`,
    fourni par `get_dashboard` pour éviter de relancer la même requête pour
    chaque widget "groupe" d'un dashboard global (équivalent, pour cette
    portée, du cache `prefetched_project_roles` déjà utilisé pour la portée
    projet via `is_project_manager`)."""
    if visibility != "groupe":
        return None
    if scope == "projet":
        if not is_project_manager(actor, project):
            raise DashboardPermissionError("Seul un chef de projet peut poser un widget « groupe » sur ce projet.")
        return None
    project_ids = group_ids_hint if group_ids_hint is not None else _group_scope_project_ids(actor)
    if not project_ids:
        raise DashboardPermissionError(
            "Seul un chef de projet (d'au moins un projet) ou un administrateur d'organisation "
            "peut poser un widget « groupe » à l'échelle globale."
        )
    return project_ids


# --- CRUD ---------------------------------------------------------------


def _ensure_scope_project_consistency(scope, project):
    if scope == "projet" and project is None:
        raise DashboardValidationError("Un widget à portée projet doit être rattaché à un projet.")
    if scope == "global" and project is not None:
        raise DashboardValidationError("Un widget à portée globale ne peut pas être rattaché à un projet.")


def create_widget(
    *,
    actor,
    scope,
    project=None,
    widget_type,
    metric_key="",
    config=None,
    visibility="individuel",
    title="",
    x=0,
    y=0,
    w=4,
    h=3,
):
    _ensure_scope_project_consistency(scope, project)

    if widget_type == "defaut":
        metric = DEFAULT_METRICS.get(metric_key)
        if metric is None:
            raise DashboardValidationError("Métrique par défaut inconnue.")
        if scope not in metric["scope"]:
            raise DashboardValidationError("Cette métrique n'est pas disponible sur cette portée.")
        visibility = metric["visibility"]
        config = {}
    elif widget_type == "personnalise":
        config = validate_custom_config(config or {})
        if scope not in CUSTOM_SOURCES[config["source"]]["scope"]:
            raise DashboardValidationError("Cette source n'est pas disponible sur cette portée.")
        if visibility not in {"individuel", "groupe"}:
            raise DashboardValidationError("Visibilité invalide.")
        # Un regroupement par assigné révèle une répartition par personne —
        # toujours "groupe", quelle que soit la valeur demandée par
        # l'appelant (pas une option laissée au créateur du widget, sinon un
        # simple membre pourrait contourner la restriction en déclarant son
        # propre widget "individuel" malgré un `group_by="assignee"`).
        if config["group_by"] == "assignee":
            visibility = "groupe"
        metric_key = ""
    else:
        raise DashboardValidationError("Type de widget invalide.")

    _ensure_widget_allowed(actor=actor, scope=scope, project=project, visibility=visibility)

    return DashboardWidget.objects.create(
        owner=actor,
        scope=scope,
        project=project,
        widget_type=widget_type,
        metric_key=metric_key,
        config=config,
        visibility=visibility,
        title=title,
        x=x,
        y=y,
        w=w,
        h=h,
    )


def update_widget_position(*, actor, widget, x, y, w, h):
    if widget.owner_id != actor.id:
        raise DashboardPermissionError("Ce widget appartient à un autre utilisateur.")
    widget.x, widget.y, widget.w, widget.h = x, y, w, h
    widget.save(update_fields=["x", "y", "w", "h"])
    return widget


def remove_widget(*, actor, widget):
    if widget.owner_id != actor.id:
        raise DashboardPermissionError("Ce widget appartient à un autre utilisateur.")
    widget.status = "removed"
    widget.save(update_fields=["status"])
    return widget


# --- Moteur générique pour widgets personnalisés (X/Y) -----------------------
# Dictionnaires fixes indexés par une valeur déjà validée contre le catalogue
# — jamais un `getattr(Model, config["field"])` construit depuis une chaîne
# brute non vérifiée.

_SOURCE_BASE_QS = {
    "tasks": lambda project_ids: Task.all_objects.filter(project_id__in=project_ids),
    "incidents": lambda project_ids: Incident.all_objects.filter(project_id__in=project_ids),
    "budget": lambda project_ids: BudgetLine.all_objects.filter(project_id__in=project_ids).annotate(
        amount=ExpressionWrapper(F("quantity") * F("unit_price"), output_field=DecimalField())
    ),
}

# Regroupement -> nom du champ ORM, par source (certaines dimensions n'ont pas
# le même nom de champ final selon la source, ex. "assignee" sur Task vs
# "assigned_to" sur Incident).
_GROUP_BY_FIELD_PER_SOURCE = {
    "tasks": {
        "status": "status",
        "priority": "priority",
        "type": "task_type",
        "assignee": "assignee__username",
    },
    "incidents": {
        "status": "status",
        "priority": "priority",
        "assignee": "assigned_to__username",
    },
    "budget": {
        "category": "category",
    },
}
_WEEK_SOURCE_FIELD = {"tasks": "created_at", "incidents": "created_at", "budget": "created_at"}

_AGG_FUNCS = {"count": Count, "sum": Sum, "avg": Avg}


def validate_custom_config(config: dict) -> dict:
    """Revalide TOUJOURS côté serveur, jamais confiance au payload client
    (même doctrine que `apps.communication.payload.validate_payload_template`)
    — appelée à la fois à la création (`create_widget`) et à chaque recalcul
    (`compute_custom_widget`), au cas où le catalogue aurait changé entre les
    deux (ex. un champ retiré après la création du widget)."""
    if not isinstance(config, dict):
        raise DashboardValidationError("Configuration de widget invalide.")

    source = config.get("source")
    if source not in CUSTOM_SOURCES:
        raise DashboardValidationError("Source invalide.")
    source_def = CUSTOM_SOURCES[source]

    aggregation = config.get("aggregation")
    if aggregation not in AGGREGATIONS:
        raise DashboardValidationError("Agrégation invalide.")

    field = config.get("field")
    if aggregation == "count":
        if field is not None:
            raise DashboardValidationError("« Nombre » ne prend pas de champ à agréger.")
    else:
        if field not in source_def["aggregatable_fields"]:
            raise DashboardValidationError("Champ agrégeable invalide pour cette source.")

    group_by = config.get("group_by", "none")
    if group_by not in source_def["group_by"]:
        raise DashboardValidationError("Regroupement invalide pour cette source.")

    return {"source": source, "aggregation": aggregation, "field": field, "group_by": group_by}


def compute_custom_widget(*, config: dict, project_ids: list) -> dict:
    """`project_ids` est déjà résolu et borné par l'appelant
    (`compute_widget_data`) selon la visibilité du widget — jamais une valeur
    venant directement du client."""
    config = validate_custom_config(config)
    source = config["source"]
    base_qs = _SOURCE_BASE_QS[source](project_ids)
    agg_fn = _AGG_FUNCS[config["aggregation"]]
    agg_expr = agg_fn("id") if config["field"] is None else agg_fn(config["field"])

    group_by = config["group_by"]
    if group_by == "none":
        value = base_qs.aggregate(result=agg_expr)["result"]
        return {"type": "scalar", "value": value or 0}

    if group_by == "week":
        qs = base_qs.annotate(_group=TruncWeek(_WEEK_SOURCE_FIELD[source]))
    else:
        field_path = _GROUP_BY_FIELD_PER_SOURCE.get(source, {}).get(group_by)
        if field_path is None:
            raise DashboardValidationError("Regroupement invalide pour cette source.")
        qs = base_qs.annotate(_group=F(field_path))

    rows = qs.values("_group").annotate(result=agg_expr).order_by("-result")
    return {
        "type": "series",
        "data": [
            {"label": str(row["_group"]) if row["_group"] is not None else "—", "value": row["result"] or 0}
            for row in rows
        ],
    }


# --- Chargement des métriques par défaut -------------------------------------
# Chaque loader a la signature `(actor, project, project_ids) -> raw`, où
# exactement un de `project`/`project_ids` est renseigné selon la portée.
# `raw` est ensuite normalisé par `_normalize_default_data` vers la même forme
# que `compute_custom_widget` (scalar/series/table/feed) — contrat unique pour
# le frontend, qu'un widget soit "par défaut" ou "personnalisé".


def _load_project_task_insights(actor, project, project_ids):
    if project is not None:
        return get_project_task_insights(actor=actor, project=project)
    if project_ids is not None:
        return get_task_insights_for_projects(project_ids)
    # Portée globale, visibilité "individuel" : scopé à contributor_projects
    # (cohérent avec l'écran Statistiques global existant).
    return get_global_task_stats(actor=actor)


def _load_incident_insights(actor, project, project_ids):
    if project is not None:
        return get_project_incident_insights(actor=actor, project=project)
    if project_ids is not None:
        return get_incident_insights_for_projects(project_ids)
    return get_global_incident_stats(actor=actor)


def _load_project_user_stats(actor, project, project_ids):
    # Catalogué `scope={"projet"}` uniquement — `project` est toujours fourni.
    return get_project_user_stats(actor=actor, project=project)


def _load_pending_doc_count(actor, project, project_ids):
    # "individuel" : pas de variante `project_ids` (portée globale = toujours
    # contributor_projects, pas de notion de "groupe" ici).
    return get_pending_doc_count(actor=actor, project=project)


def _load_activity_feed(actor, project, project_ids):
    if project is not None:
        return list(get_project_history(actor=actor, project=project)[:_ACTIVITY_FEED_LIMIT])
    # Portée globale : `get_scoped_history` a sa propre cascade de rang déjà
    # établie (admin d'organisation -> admin de groupe -> chef de
    # projet/soi-même), plus permissive que la règle générique "groupe" de ce
    # module sur certains cas (admin de groupe) — delibérément conservée
    # telle quelle, c'est une fonctionnalité d'historique déjà livrée avec ses
    # propres règles, pas la peine de la restreindre pour cette seule vitrine.
    return list(get_scoped_history(actor=actor)[:_ACTIVITY_FEED_LIMIT])


def _load_budget_summary(actor, project, project_ids):
    if project is not None:
        lines = BudgetLine.objects.filter(project=project)
        opex_total = sum((line.amount for line in lines if line.category == "opex"), Decimal("0"))
        capex_total = sum((line.amount for line in lines if line.category == "capex"), Decimal("0"))
        return [{"project": project, "opex_total": opex_total, "capex_total": capex_total}]
    # Portée globale : réutilise tel quel `get_budget_summary_for_manager`
    # (déjà scopé aux projets dirigés par l'acteur) — un admin d'organisation
    # sans rôle de chef de projet explicite n'y voit rien, comportement
    # préexistant à ce chantier, pas élargi ici.
    return get_budget_summary_for_manager(actor=actor)


_LOADERS = {
    "project_task_insights": _load_project_task_insights,
    "incident_insights": _load_incident_insights,
    "project_user_stats": _load_project_user_stats,
    "pending_doc_count": _load_pending_doc_count,
    "activity_feed": _load_activity_feed,
    "budget_summary": _load_budget_summary,
}


def _normalize_default_data(metric, raw):
    data_key = metric["data_key"]
    render_hint = metric["render_hint"]

    if render_hint == "table" and metric_is_user_stats_table(metric):
        return {
            "type": "table",
            "rows": [
                {
                    "label": str(row["user"]),
                    "tasks_done": row["tasks_done"],
                    "tasks_in_progress": row["tasks_in_progress"],
                    "hours_spent": float(row["hours_spent"]),
                }
                for row in raw
            ],
        }
    if render_hint == "table" and metric["loader"] == "budget_summary":
        return {
            "type": "table",
            "rows": [
                {
                    "label": row["project"].name,
                    "opex_total": float(row["opex_total"]),
                    "capex_total": float(row["capex_total"]),
                }
                for row in raw
            ],
        }
    if render_hint == "feed":
        return {
            "type": "feed",
            "items": [
                {
                    "created_at": entry.created_at.isoformat(),
                    "actor": str(entry.actor) if entry.actor else "Système",
                    "verb": entry.verb,
                    "description": entry.new_value or entry.field_name,
                }
                for entry in raw
            ],
        }

    value = raw if data_key is None else (raw[data_key] if not isinstance(data_key, tuple) else None)

    if isinstance(data_key, tuple):
        # Ex. ("tasks_on_time", "tasks_late") -> deux points nommés.
        labels = {"tasks_on_time": "À temps", "tasks_late": "En retard"}
        return {
            "type": "series",
            "data": [{"label": labels.get(key, key), "value": raw[key]} for key in data_key],
        }

    if isinstance(value, dict):
        return {"type": "series", "data": [{"label": k, "value": v} for k, v in value.items()]}

    if isinstance(value, Decimal):
        value = float(value)
    return {"type": "scalar", "value": value}


def metric_is_user_stats_table(metric):
    return metric["loader"] == "project_user_stats"


def compute_widget_data(*, actor, widget, group_ids_hint=None):
    """Calcule les données d'un widget pour l'affichage — re-vérifie TOUJOURS
    la visibilité (défense en profondeur, voir `_ensure_widget_allowed`) au
    cas où le rôle de l'acteur aurait changé depuis la création du widget :
    renvoie `{"restricted": True}` plutôt qu'une exception, pour ne pas casser
    le chargement du reste du dashboard."""
    try:
        project_ids = _ensure_widget_allowed(
            actor=actor,
            scope=widget.scope,
            project=widget.project,
            visibility=widget.visibility,
            group_ids_hint=group_ids_hint,
        )
    except DashboardPermissionError:
        return {"restricted": True}

    if widget.widget_type == "personnalise":
        if widget.scope == "projet":
            ids = [widget.project_id]
        else:
            ids = project_ids  # None si "individuel" -> on retombe sur contributor_projects
            if ids is None:
                ids = list(contributor_projects(actor).values_list("id", flat=True))
        try:
            return compute_custom_widget(config=widget.config, project_ids=ids)
        except DashboardValidationError:
            # Le catalogue a changé depuis la création du widget (ex. champ
            # retiré) — pas une exception qui casserait le dashboard.
            return {"restricted": True, "reason": "config_invalide"}

    metric = DEFAULT_METRICS.get(widget.metric_key)
    if metric is None:
        return {"restricted": True, "reason": "metrique_inconnue"}
    loader = _LOADERS[metric["loader"]]
    raw = loader(actor, widget.project, project_ids)
    return _normalize_default_data(metric, raw)


def get_dashboard(*, actor, scope, project=None):
    """Disposition + données calculées de tous les widgets d'un dashboard —
    un seul appel ORM pour les widgets, enveloppé dans
    `prefetched_project_roles` pour que chaque vérification de rôle "groupe"
    pendant le calcul tape le cache plutôt qu'une requête par widget."""
    widgets = list(
        DashboardWidget.objects.filter(owner=actor, scope=scope, project=project).order_by("y", "x")
    )
    project_ids_for_cache = [project.id] if project is not None else [w.project_id for w in widgets if w.project_id]
    # Portée globale : calculé une seule fois pour tout le dashboard plutôt
    # qu'une fois par widget "groupe" — équivalent, pour cette règle, du cache
    # `prefetched_project_roles` déjà utilisé pour la portée projet.
    group_ids_hint = _group_scope_project_ids(actor) if scope == "global" else None
    with prefetched_project_roles(actor, project_ids_for_cache):
        return [
            {
                "widget": widget,
                "data": compute_widget_data(actor=actor, widget=widget, group_ids_hint=group_ids_hint),
            }
            for widget in widgets
        ]


def get_catalog(*, actor, scope, project=None):
    """Catalogue filtré selon ce que l'acteur a le droit d'ajouter sur cette
    portée — pour que la bibliothèque frontend n'affiche jamais une option que
    `create_widget` rejetterait de toute façon."""
    can_group_project = project is not None and is_project_manager(actor, project)
    can_group_global = scope == "global" and bool(_group_scope_project_ids(actor))

    default_metrics = {}
    for key, metric in DEFAULT_METRICS.items():
        if scope not in metric["scope"]:
            continue
        if metric["visibility"] == "groupe":
            if scope == "projet" and not can_group_project:
                continue
            if scope == "global" and not can_group_global:
                continue
        default_metrics[key] = {"label": metric["label"], "visibility": metric["visibility"], "render_hint": metric["render_hint"]}

    # `value["scope"]` est un `set` en interne (voir catalog.py) — jamais
    # renvoyé tel quel : un `set` n'est pas sérialisable en JSON par DRF.
    custom_sources = {
        key: {
            "label": value["label"],
            "scope": sorted(value["scope"]),
            "aggregatable_fields": value["aggregatable_fields"],
            "group_by": value["group_by"],
        }
        for key, value in CUSTOM_SOURCES.items()
        if scope in value["scope"]
    }

    return {
        "default_metrics": default_metrics,
        "custom_sources": custom_sources,
        "aggregations": AGGREGATIONS,
        "can_add_group_widgets": can_group_project if scope == "projet" else can_group_global,
    }
