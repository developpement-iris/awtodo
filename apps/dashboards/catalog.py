"""Catalogue du Dashboard personnalisable (session du 2026-10-01) — deux
registres de données pures, jamais de code exécuté dynamiquement à partir
d'une chaîne utilisateur (même doctrine de sécurité que
`apps.communication.payload.AVAILABLE_FIELDS`).

- `DEFAULT_METRICS` : la bibliothèque de widgets "par défaut", chacun pointant
  vers une fonction de service déjà existante (ou nouvellement écrite, voir
  docs/modeles-et-api.md > "Statistiques/Dashboard personnalisable").
- `CUSTOM_SOURCES`/`AGGREGATIONS` : les choix contraints du constructeur de
  widget personnalisé — un petit moteur X/Y générique (source, champ,
  agrégation, regroupement), jamais une formule libre.

Chaque `loader` ci-dessous est une **clé logique**, résolue contre un
dictionnaire fixe `_LOADERS` dans `apps.dashboards.services` — jamais un
`getattr`/import dynamique construit depuis une chaîne non vérifiée.
"""

# --- Widgets par défaut -----------------------------------------------------
# `scope` : ensembles de portées où ce widget peut être posé ("projet"/"global").
# `visibility` : "individuel" (tout membre) ou "groupe" (chef de projet pour la
# portée projet ; chef de projet d'au moins un projet/admin d'organisation
# pour la portée globale — voir apps.dashboards.services._group_scope_project_ids).
# `render_hint` : indique au frontend (WidgetRenderer) quel composant de
# graphique monter ("stat_card"/"donut"/"bar"/"area"/"table"/"feed").

DEFAULT_METRICS = {
    "task_hours_total": {
        "label": "Heures passées (tâches)",
        "loader": "project_task_insights",
        "data_key": "hours_total",
        "scope": {"projet", "global"},
        "visibility": "individuel",
        "render_hint": "stat_card",
    },
    "task_priority_breakdown": {
        "label": "Tâches par priorité",
        "loader": "project_task_insights",
        "data_key": "priority_breakdown",
        "scope": {"projet", "global"},
        "visibility": "individuel",
        "render_hint": "donut",
    },
    "task_type_breakdown": {
        "label": "Tâches par type",
        "loader": "project_task_insights",
        "data_key": "type_breakdown",
        "scope": {"projet", "global"},
        "visibility": "individuel",
        "render_hint": "donut",
    },
    "task_completion_trend": {
        "label": "Tendance de complétion (8 semaines)",
        "loader": "project_task_insights",
        "data_key": "completion_trend",
        "scope": {"projet", "global"},
        "visibility": "individuel",
        "render_hint": "area",
    },
    "task_deadline_compliance": {
        "label": "Respect des échéances",
        "loader": "project_task_insights",
        "data_key": ("tasks_on_time", "tasks_late"),
        "scope": {"projet", "global"},
        "visibility": "individuel",
        "render_hint": "donut",
    },
    "task_cancellation_rate": {
        "label": "Taux d'annulation / rejet (tâches)",
        "loader": "project_task_insights",
        "data_key": "cancellation_rate",
        "scope": {"projet", "global"},
        "visibility": "individuel",
        "render_hint": "stat_card",
    },
    "task_backlog_age": {
        "label": "Âge du backlog",
        "loader": "project_task_insights",
        "data_key": "backlog_age_buckets",
        "scope": {"projet", "global"},
        "visibility": "individuel",
        "render_hint": "bar",
    },
    "current_workload_by_user": {
        "label": "Charge actuelle par personne",
        "loader": "project_task_insights",
        "data_key": "active_tasks_by_assignee",
        "scope": {"projet", "global"},
        # Porte sur les autres membres — voir la règle de portée globale dans
        # apps.dashboards.services._group_scope_project_ids.
        "visibility": "groupe",
        "render_hint": "bar",
    },
    "project_user_stats": {
        "label": "Statistiques par membre",
        "loader": "project_user_stats",
        "data_key": None,
        "scope": {"projet"},
        "visibility": "groupe",
        "render_hint": "table",
    },
    "incident_mttr": {
        "label": "Temps moyen de résolution (incidents)",
        "loader": "incident_insights",
        "data_key": "mttr_hours",
        "scope": {"projet", "global"},
        "visibility": "individuel",
        "render_hint": "stat_card",
    },
    "incident_status_breakdown": {
        "label": "Incidents par statut",
        "loader": "incident_insights",
        "data_key": "status_breakdown",
        "scope": {"projet", "global"},
        "visibility": "individuel",
        "render_hint": "donut",
    },
    "incident_priority_breakdown": {
        "label": "Incidents par priorité",
        "loader": "incident_insights",
        "data_key": "priority_breakdown",
        "scope": {"projet", "global"},
        "visibility": "individuel",
        "render_hint": "donut",
    },
    "incident_cancellation_rate": {
        "label": "Taux d'annulation (incidents)",
        "loader": "incident_insights",
        "data_key": "cancellation_rate",
        "scope": {"projet", "global"},
        "visibility": "individuel",
        "render_hint": "stat_card",
    },
    "pending_doc_backlog": {
        "label": "Dette documentaire (file « à documenter »)",
        "loader": "pending_doc_count",
        "data_key": None,
        "scope": {"projet", "global"},
        "visibility": "individuel",
        "render_hint": "stat_card",
    },
    "recent_activity_feed": {
        "label": "Flux d'activité récente",
        "loader": "activity_feed",
        "data_key": None,
        "scope": {"projet", "global"},
        # Réutilise get_project_history/get_scoped_history, déjà réservés au
        # chef de projet / à la cascade de rang — voir apps.projects.services.
        "visibility": "groupe",
        "render_hint": "feed",
    },
    "budget_summary": {
        "label": "Budget OPEX/CAPEX",
        "loader": "budget_summary",
        "data_key": None,
        "scope": {"projet", "global"},
        "visibility": "groupe",
        "render_hint": "table",
    },
}


# --- Constructeur de widget personnalisé (X/Y générique) --------------------
# Toute combinaison source+agrégation+champ+regroupement y est une métrique
# valide — aucun cas spécial "ratio" à coder, le choix de la combinaison fait
# le travail (ex. "moyenne" + "temps passé" + regroupement "assigné" = temps
# moyen par utilisateur ; "compte" + regroupement "assigné" = nb de tâches par
# utilisateur).

AGGREGATIONS = {
    "count": "Nombre",
    "sum": "Somme",
    "avg": "Moyenne",
}

CUSTOM_SOURCES = {
    "tasks": {
        "label": "Tâches",
        "scope": {"projet", "global"},
        "aggregatable_fields": {
            "time_spent": "Temps passé (h)",
            "estimated_hours": "Temps estimé (h)",
        },
        "group_by": {
            "none": "Aucun (valeur unique)",
            "week": "Semaine de création",
            "status": "Statut",
            "priority": "Priorité",
            "type": "Type de tâche",
            "assignee": "Assigné",
        },
    },
    "incidents": {
        "label": "Incidents",
        "scope": {"projet", "global"},
        "aggregatable_fields": {
            "time_spent": "Temps de résolution (h)",
        },
        "group_by": {
            "none": "Aucun (valeur unique)",
            "week": "Semaine de création",
            "status": "Statut",
            "priority": "Priorité",
            "assignee": "Assigné",
        },
    },
    "budget": {
        "label": "Budget",
        "scope": {"projet", "global"},
        # "amount" n'est PAS un champ DB (BudgetLine.amount est une @property
        # Python, quantity * unit_price) — le moteur l'annote via une
        # expression ORM dédiée avant d'agréger, voir
        # apps.dashboards.services._SOURCE_BASE_QS.
        "aggregatable_fields": {
            "amount": "Montant",
        },
        "group_by": {
            "none": "Aucun (valeur unique)",
            "week": "Semaine de création",
            "category": "Catégorie (OPEX/CAPEX)",
        },
    },
}

# Dimensions de regroupement dont le champ ORM réel diffère du nom affiché
# dans le catalogue, et/ou diffère d'une source à l'autre (ex. "assignee" sur
# Task vs "assigned_to" sur Incident) — résolu par
# apps.dashboards.services._GROUP_BY_FIELD_PER_SOURCE, jamais construit depuis
# la chaîne brute du catalogue.
