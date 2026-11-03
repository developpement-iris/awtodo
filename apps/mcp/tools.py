"""Outils MCP exposés à Claude.

Quatre outils génériques plutôt qu'un outil par endpoint (~170) : la liste
d'outils reste lisible pour Claude, et `awtodo_list_endpoints` lui donne le
détail à la demande. Lecture et écriture sont deux outils distincts pour que
claude.ai puisse laisser passer les lectures et demander confirmation des
écritures (annotations `readOnlyHint` / `destructiveHint`).
"""

from .catalog import format_catalog
from .dispatch import ApiCallError, call_api

_PATH_DESCRIPTION = (
    "Chemin relatif à /api/v1/, ex. \"tasks/\" ou \"tasks/<uuid>/start/\". "
    "Voir awtodo_list_endpoints pour les chemins disponibles."
)
_QUERY_SCHEMA = {
    "type": "object",
    "description": "Paramètres de requête (filtres), ex. {\"status\": [\"assignée\", \"en_cours\"], \"project\": \"<uuid>\"}.",
    "additionalProperties": True,
}

TOOLS = [
    {
        "name": "awtodo_whoami",
        "title": "Qui suis-je dans Awtodo",
        "description": "Renvoie le compte Awtodo connecté (identité, organisation, rôles, capacités).",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "awtodo_list_endpoints",
        "title": "Lister les endpoints Awtodo",
        "description": (
            "Catalogue de l'API Awtodo. Sans argument : liste des domaines (tasks, incidents, projects, "
            "planning…). Avec `area` et/ou `search` : méthodes, chemins, filtres et champs attendus. "
            "À appeler avant awtodo_api_read / awtodo_api_write en cas de doute sur un chemin."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "area": {"type": "string", "description": "Domaine, ex. \"tasks\", \"incidents\", \"planning\"."},
                "search": {"type": "string", "description": "Mot-clé recherché dans le chemin ou la description."},
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "awtodo_api_read",
        "title": "Lire des données Awtodo",
        "description": (
            "Requête GET sur l'API Awtodo, avec les droits de l'utilisateur connecté. "
            "Renvoie le code HTTP et le JSON de la réponse."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": _PATH_DESCRIPTION}, "query": _QUERY_SCHEMA},
            "required": ["path"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "awtodo_api_write",
        "title": "Modifier des données Awtodo",
        "description": (
            "Requête POST/PUT/PATCH/DELETE sur l'API Awtodo (créer une tâche, démarrer un incident, "
            "commenter, changer un statut…), avec les droits de l'utilisateur connecté. Les règles "
            "métier et permissions d'Awtodo s'appliquent : une action interdite renvoie 403, une "
            "saisie invalide 400 avec le détail. Rien n'est jamais supprimé physiquement (DELETE archive)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "method": {"type": "string", "enum": ["POST", "PUT", "PATCH", "DELETE"]},
                "path": {"type": "string", "description": _PATH_DESCRIPTION},
                "body": {"type": "object", "description": "Corps JSON de la requête.", "additionalProperties": True},
                "query": _QUERY_SCHEMA,
            },
            "required": ["method", "path"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
    },
]

INSTRUCTIONS = (
    "Awtodo est l'outil interne de gestion de projets, tâches, incidents et planning. Chaque appel "
    "s'exécute avec les droits de la personne connectée : elle ne voit que ses projets/groupes. "
    "Méthode : awtodo_list_endpoints pour découvrir les chemins, puis awtodo_api_read pour lire et "
    "awtodo_api_write pour agir. Les identifiants sont des UUID. Les listes de tâches/incidents ne "
    "renvoient par défaut que les éléments actifs (filtrer `status` pour l'historique). Les "
    "transitions de statut passent par des actions dédiées (ex. POST tasks/<id>/start/, "
    "POST incidents/<id>/resolve/), jamais par un PATCH du champ status. Confirmer avec "
    "l'utilisateur avant toute modification qu'il n'a pas explicitement demandée."
)


class ToolError(Exception):
    """Erreur renvoyée à Claude comme résultat d'outil (`isError: true`)."""


def call_tool(name, arguments, *, user, request):
    """Renvoie le texte du résultat ; lève `ToolError` pour une erreur à montrer à Claude."""
    arguments = arguments or {}
    if not isinstance(arguments, dict):
        raise ToolError("Les arguments doivent être un objet JSON.")

    if name == "awtodo_whoami":
        return _api(user, request, "GET", "accounts/me/")
    if name == "awtodo_list_endpoints":
        return format_catalog(area=arguments.get("area"), search=arguments.get("search"))
    if name == "awtodo_api_read":
        return _api(user, request, "GET", arguments.get("path"), query=arguments.get("query"))
    if name == "awtodo_api_write":
        method = str(arguments.get("method", "")).upper()
        if method not in ("POST", "PUT", "PATCH", "DELETE"):
            raise ToolError("`method` doit valoir POST, PUT, PATCH ou DELETE.")
        return _api(user, request, method, arguments.get("path"), query=arguments.get("query"), body=arguments.get("body"))
    raise ToolError(f"Outil inconnu : {name}.")


def _api(user, request, method, path, *, query=None, body=None):
    if query is not None and not isinstance(query, dict):
        raise ToolError("`query` doit être un objet JSON.")
    if body is not None and not isinstance(body, (dict, list)):
        raise ToolError("`body` doit être un objet JSON.")
    try:
        status, text = call_api(user=user, method=method, path=path, query=query, body=body, outer_request=request)
    except ApiCallError as exc:
        raise ToolError(str(exc))
    result = f"HTTP {status}\n{text}"
    if status >= 400:
        raise ToolError(result)
    return result
