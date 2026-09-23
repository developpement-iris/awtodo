"""Client Microsoft Graph minimal pour la synchronisation Outlook (session du
2026-09-22, sens unique Awtodo → Outlook). Permission d'application
`Calendars.ReadWrite` (flux client credentials, `msal`), même modèle que
`Mail.Send` pour `apps.communication` — un seul jeu d'identifiants par
organisation (`O365Connection`), pas de consentement par utilisateur."""

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

import requests
from msal import ConfidentialClientApplication

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]
_REQUEST_TIMEOUT = 10


class GraphSyncError(Exception):
    """Config manquante, échec d'authentification, ou appel Graph en échec."""


# --- Récurrence : RRULE (sous-ensemble produit par l'éditeur, voir
# frontend/src/features/planning/recurrence.ts) → motif Graph -------------
#
# Graph n'accepte pas une chaîne RRULE : il attend un objet structuré
# {pattern, range}. `build_graph_recurrence` ne traduit que le sous-ensemble
# que l'éditeur front peut réellement produire (FREQ daily/weekly/monthly/
# yearly, INTERVAL, BYDAY sur weekly uniquement, fin par UNTIL ou COUNT) —
# une RRULE plus riche passée directement par l'API (le backend l'accepte,
# voir _validate_recurrence_rule) renvoie `None`, et l'appelant doit alors
# ignorer la synchro de cet événement plutôt que d'envoyer un motif
# approximatif à Outlook.

_BYDAY_TO_GRAPH = {
    "MO": "monday",
    "TU": "tuesday",
    "WE": "wednesday",
    "TH": "thursday",
    "FR": "friday",
    "SA": "saturday",
    "SU": "sunday",
}
_WEEKDAY_INDEX_TO_GRAPH = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_FREQ_TO_GRAPH_TYPE = {
    "DAILY": "daily",
    "WEEKLY": "weekly",
    "MONTHLY": "absoluteMonthly",
    "YEARLY": "absoluteYearly",
}
_SUPPORTED_RRULE_KEYS = {"FREQ", "INTERVAL", "BYDAY", "UNTIL", "COUNT"}


def _parse_rrule_params(rule):
    params = {}
    for part in rule.split(";"):
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        params[key.strip().upper()] = value.strip()
    return params


def build_graph_recurrence(event):
    """Renvoie le `{pattern, range}` Graph pour `event.recurrence_rule`, ou
    `None` si la règle n'est pas dans le sous-ensemble traduit (voir
    ci-dessus)."""
    params = _parse_rrule_params(event.recurrence_rule)
    if not params or not set(params).issubset(_SUPPORTED_RRULE_KEYS):
        return None

    graph_type = _FREQ_TO_GRAPH_TYPE.get(params.get("FREQ", ""))
    if graph_type is None:
        return None

    try:
        interval = int(params.get("INTERVAL", 1) or 1)
    except ValueError:
        return None
    pattern = {"type": graph_type, "interval": interval}

    if graph_type == "weekly":
        byday = params.get("BYDAY")
        if byday:
            days = [_BYDAY_TO_GRAPH.get(code) for code in byday.split(",")]
            if None in days:
                return None
        else:
            days = [_WEEKDAY_INDEX_TO_GRAPH[event.start.weekday()]]
        pattern["daysOfWeek"] = days
    elif graph_type in ("absoluteMonthly", "absoluteYearly"):
        pattern["dayOfMonth"] = event.start.day
        if graph_type == "absoluteYearly":
            pattern["month"] = event.start.month

    start_date = event.start.date().isoformat()
    until = params.get("UNTIL")
    count = params.get("COUNT")
    if until:
        try:
            end_date = datetime.strptime(until[:8], "%Y%m%d").date().isoformat()
        except ValueError:
            return None
        range_ = {"type": "endDate", "startDate": start_date, "endDate": end_date}
    elif count:
        try:
            range_ = {"type": "numbered", "startDate": start_date, "numberOfOccurrences": int(count)}
        except ValueError:
            return None
    else:
        range_ = {"type": "noEnd", "startDate": start_date}

    return {"pattern": pattern, "range": range_}


def _acquire_token(connection):
    app = ConfidentialClientApplication(
        client_id=connection.client_id,
        client_credential=connection.client_secret,
        authority=f"https://login.microsoftonline.com/{connection.tenant_id}",
    )
    result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)
    if "access_token" not in result:
        raise GraphSyncError(result.get("error_description", "Authentification Microsoft Graph impossible."))
    return result["access_token"]


def _headers(connection):
    return {
        "Authorization": f"Bearer {_acquire_token(connection)}",
        "Content-Type": "application/json",
    }


def _event_payload(event):
    payload = {
        "subject": event.title,
        "body": {"contentType": "text", "content": event.description or ""},
        "start": {"dateTime": event.start.isoformat(), "timeZone": "Europe/Paris"},
        "end": {"dateTime": event.end.isoformat(), "timeZone": "Europe/Paris"},
        "isAllDay": event.all_day,
    }
    if event.location:
        payload["location"] = {"displayName": event.location}
    if event.recurrence_rule:
        recurrence = build_graph_recurrence(event)
        if recurrence:
            payload["recurrence"] = recurrence
    return payload


# --- Appels HTTP génériques, partagés entre événements libres et créneaux
# de tâche/incident (session du 2026-09-23) — seule la construction du
# payload diffère entre les deux. ------------------------------------------


def _post_event(connection, upn, payload):
    response = requests.post(
        f"{GRAPH_BASE_URL}/users/{upn}/events",
        headers=_headers(connection),
        json=payload,
        timeout=_REQUEST_TIMEOUT,
    )
    if response.status_code >= 400:
        raise GraphSyncError(f"Création Outlook échouée ({response.status_code}) : {response.text[:300]}")
    return response.json()["id"]


def _patch_event(connection, upn, outlook_event_id, payload):
    response = requests.patch(
        f"{GRAPH_BASE_URL}/users/{upn}/events/{outlook_event_id}",
        headers=_headers(connection),
        json=payload,
        timeout=_REQUEST_TIMEOUT,
    )
    if response.status_code >= 400:
        raise GraphSyncError(f"Modification Outlook échouée ({response.status_code}) : {response.text[:300]}")


def delete_graph_event(connection, upn, outlook_event_id):
    response = requests.delete(
        f"{GRAPH_BASE_URL}/users/{upn}/events/{outlook_event_id}",
        headers=_headers(connection),
        timeout=_REQUEST_TIMEOUT,
    )
    # 404 = déjà supprimé côté Outlook (main ou synchro précédente) : pas une
    # erreur pour nous, l'état cible (pas d'événement côté Outlook) est atteint.
    if response.status_code >= 400 and response.status_code != 404:
        raise GraphSyncError(f"Suppression Outlook échouée ({response.status_code}) : {response.text[:300]}")


def create_graph_event(connection, upn, event):
    """Crée l'événement côté Outlook, renvoie son id Graph."""
    return _post_event(connection, upn, _event_payload(event))


def update_graph_event(connection, upn, outlook_event_id, event):
    _patch_event(connection, upn, outlook_event_id, _event_payload(event))


# --- Créneaux de tâche/incident (`ScheduledBlock`) -------------------------
#
# Pas de récurrence ni de description/lieu sur un créneau (le modèle n'en a
# pas) — payload volontairement plus simple que `_event_payload`. Le titre
# Outlook reprend celui de la tâche ou de l'incident planifié.


def _block_payload(block):
    title = block.task.title if block.task_id else block.incident.title
    return {
        "subject": title,
        "start": {"dateTime": block.start.isoformat(), "timeZone": "Europe/Paris"},
        "end": {"dateTime": block.end.isoformat(), "timeZone": "Europe/Paris"},
    }


def create_graph_block_event(connection, upn, block):
    """Crée le créneau côté Outlook (pour un destinataire donné — voir
    `apps.planning.tasks.sync_scheduled_block_to_outlook`), renvoie son id
    Graph."""
    return _post_event(connection, upn, _block_payload(block))


def update_graph_block_event(connection, upn, outlook_event_id, block):
    _patch_event(connection, upn, outlook_event_id, _block_payload(block))


# --- Occurrence unique d'une série récurrente (session du 2026-09-23) -----
#
# ⚠️ Non vérifié contre un vrai tenant Outlook — best-effort, à confirmer au
# premier usage réel (voir docs/modeles-et-api.md > "Synchronisation
# Outlook"). Graph modélise nativement une occurrence isolée : chaque
# instance d'une série a son propre id, distinct de celui du modèle
# (`master_event_id`), résolu via `GET /events/{master}/instances`. PATCHer
# ou DELETEer cet id-là (plutôt que celui du modèle) ne touche que cette
# occurrence — exactement le comportement demandé côté Awtodo.


def _occurrence_payload(override):
    payload = {
        "subject": override.title,
        "body": {"contentType": "text", "content": override.description or ""},
        "start": {"dateTime": override.start.isoformat(), "timeZone": "Europe/Paris"},
        "end": {"dateTime": override.end.isoformat(), "timeZone": "Europe/Paris"},
        "isAllDay": override.all_day,
    }
    if override.location:
        payload["location"] = {"displayName": override.location}
    return payload


def _resolve_instance_id(connection, upn, master_event_id, occurrence_start):
    """Renvoie l'id Graph de l'instance la plus proche de `occurrence_start`
    dans la série `master_event_id`, ou `None` si Graph n'en renvoie aucune
    dans la fenêtre (série pas encore répliquée côté Graph, par exemple).
    Comparaison par instance la plus proche plutôt qu'une correspondance
    exacte de chaîne — Graph renvoie ses horodatages dans le fuseau demandé
    par l'en-tête `Prefer`, non envoyé ici (donc UTC), ce qui rend une
    correspondance exacte fragile."""
    window_start = occurrence_start - timedelta(hours=2)
    window_end = occurrence_start + timedelta(hours=2)
    response = requests.get(
        f"{GRAPH_BASE_URL}/users/{upn}/events/{master_event_id}/instances",
        headers=_headers(connection),
        params={
            "startDateTime": window_start.astimezone(dt_timezone.utc).isoformat(),
            "endDateTime": window_end.astimezone(dt_timezone.utc).isoformat(),
        },
        timeout=_REQUEST_TIMEOUT,
    )
    if response.status_code >= 400:
        raise GraphSyncError(f"Résolution d'occurrence Outlook échouée ({response.status_code}) : {response.text[:300]}")
    instances = response.json().get("value", [])
    if not instances:
        return None

    target = occurrence_start.astimezone(dt_timezone.utc)

    def _distance(item):
        try:
            raw = item["start"]["dateTime"].split(".")[0]
            dt = datetime.fromisoformat(raw).replace(tzinfo=dt_timezone.utc)
        except (KeyError, ValueError):
            return timedelta.max
        return abs(dt - target)

    return min(instances, key=_distance)["id"]


def upsert_graph_occurrence(connection, upn, master_event_id, occurrence_start, override):
    """PATCH l'instance Graph correspondant à `occurrence_start`. Renvoie
    l'id Graph de l'instance (à mettre en cache pour éviter de la
    re-résoudre à chaque appel)."""
    instance_id = _resolve_instance_id(connection, upn, master_event_id, occurrence_start)
    if instance_id is None:
        raise GraphSyncError(
            "Instance Outlook introuvable pour cette occurrence (série pas encore répliquée côté Graph ?)."
        )
    _patch_event(connection, upn, instance_id, _occurrence_payload(override))
    return instance_id


def delete_graph_occurrence(connection, upn, master_event_id, occurrence_start, cached_instance_id=None):
    instance_id = cached_instance_id or _resolve_instance_id(connection, upn, master_event_id, occurrence_start)
    if instance_id is None:
        return  # déjà absent côté Outlook, rien à faire
    delete_graph_event(connection, upn, instance_id)
