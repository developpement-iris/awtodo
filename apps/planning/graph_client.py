"""Client Microsoft Graph minimal pour la synchronisation Outlook (session du
2026-09-22, sens unique Awtodo → Outlook). Permission d'application
`Calendars.ReadWrite` (flux client credentials, `msal`), même modèle que
`Mail.Send` pour `apps.communication` — un seul jeu d'identifiants par
organisation (`O365Connection`), pas de consentement par utilisateur."""

import requests
from msal import ConfidentialClientApplication

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]
_REQUEST_TIMEOUT = 10


class GraphSyncError(Exception):
    """Config manquante, échec d'authentification, ou appel Graph en échec."""


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
    return payload


def create_graph_event(connection, upn, event):
    """Crée l'événement côté Outlook, renvoie son id Graph."""
    response = requests.post(
        f"{GRAPH_BASE_URL}/users/{upn}/events",
        headers=_headers(connection),
        json=_event_payload(event),
        timeout=_REQUEST_TIMEOUT,
    )
    if response.status_code >= 400:
        raise GraphSyncError(f"Création Outlook échouée ({response.status_code}) : {response.text[:300]}")
    return response.json()["id"]


def update_graph_event(connection, upn, outlook_event_id, event):
    response = requests.patch(
        f"{GRAPH_BASE_URL}/users/{upn}/events/{outlook_event_id}",
        headers=_headers(connection),
        json=_event_payload(event),
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
