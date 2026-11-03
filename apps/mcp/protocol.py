"""Cœur JSON-RPC du protocole MCP (transport « Streamable HTTP », mode sans état).

Écrit à la main plutôt qu'avec le SDK Python `mcp` : ce SDK est bâti sur
ASGI/Starlette, alors qu'Awtodo tourne en WSGI (gunicorn). Le sous-ensemble
nécessaire à un serveur d'outils — initialize, ping, tools/list, tools/call —
tient en quelques dizaines de lignes, réponses JSON directes, sans flux SSE ni
session (autorisé par la spécification).
"""

import logging

from .tools import INSTRUCTIONS, TOOLS, ToolError, call_tool

logger = logging.getLogger(__name__)

SUPPORTED_PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "awtodo", "title": "Awtodo", "version": "1.0.0"}

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def error_response(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_message(message, *, user, request):
    """Traite un message JSON-RPC. Renvoie la réponse, ou `None` pour une notification."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or "method" not in message:
        return error_response(message.get("id") if isinstance(message, dict) else None, INVALID_REQUEST, "Requête JSON-RPC invalide.")

    is_notification = "id" not in message
    request_id = message.get("id")
    method = message["method"]
    params = message.get("params") or {}

    if is_notification:
        # notifications/initialized, notifications/cancelled… : rien à faire en mode sans état.
        return None

    try:
        result = _dispatch(method, params, user=user, request=request)
    except _MethodNotFound:
        return error_response(request_id, METHOD_NOT_FOUND, f"Méthode inconnue : {method}.")
    except _InvalidParams as exc:
        return error_response(request_id, INVALID_PARAMS, str(exc))
    except Exception:
        logger.exception("Erreur MCP sur %s", method)
        return error_response(request_id, INTERNAL_ERROR, "Erreur interne.")
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


class _MethodNotFound(Exception):
    pass


class _InvalidParams(Exception):
    pass


def _dispatch(method, params, *, user, request):
    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else SUPPORTED_PROTOCOL_VERSIONS[0]
        return {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": INSTRUCTIONS,
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str):
            raise _InvalidParams("`name` manquant.")
        if name not in {tool["name"] for tool in TOOLS}:
            raise _InvalidParams(f"Outil inconnu : {name}.")
        try:
            text = call_tool(name, params.get("arguments"), user=user, request=request)
            return {"content": [{"type": "text", "text": text}], "isError": False}
        except ToolError as exc:
            return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    raise _MethodNotFound()
