"""Briques de la documentation OpenAPI (session du 2026-11-05).

Chaque app décrit ses opérations dans son `schema.py`, appliqué aux vues par
décorateur : sans ça, drf-spectacular prête à toute action le serializer de
l'entité (`tasks/{id}/start/` « attendait » une tâche complète). Le contrat est
vérifié par `apps/integrations/tests/test_openapi.py`.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers

DetailMessage = inline_serializer(name="DetailMessage", fields={"detail": serializers.CharField()})

FILE_UPLOAD = {
    "multipart/form-data": {
        "type": "object",
        "properties": {"file": {"type": "string", "format": "binary"}},
        "required": ["file"],
    }
}


def body(schema_name, /, **fields):
    """Corps ad hoc d'une action qui lit `request.data` sans serializer dédié."""
    return inline_serializer(name=schema_name, fields=fields)


def no_body(response=None, **kwargs):
    """Action sans corps. `response=None` : réponse 204."""
    return extend_schema(request=None, responses=response if response is not None else {204: None}, **kwargs)


def file_response(content_type="application/octet-stream"):
    return {(200, content_type): OpenApiTypes.BINARY}


def type_identifiers_as_uuid(result, **kwargs):
    """Hook de post-traitement : les routes d'action déclarent leurs identifiants
    par une regex (`(?P<page_id>[^/.]+)`), que drf-spectacular ne sait pas typer."""
    for path in result.get("paths", {}).values():
        for operation in path.values():
            for parameter in operation.get("parameters", []):
                if parameter["in"] != "path" or not (parameter["name"] == "id" or parameter["name"].endswith("_id")):
                    continue
                if parameter["schema"].get("type") == "string":
                    parameter["schema"]["format"] = "uuid"
    return result
