"""Catalogue des endpoints de l'API, dérivé du schéma OpenAPI (drf-spectacular).

Sert l'outil `awtodo_list_endpoints` : Claude découvre ce qui existe (chemin,
paramètres, champs du corps) plutôt que de deviner — source unique de vérité,
toujours à jour avec le code, sans liste maintenue à la main.
"""

import functools
import re

from drf_spectacular.generators import SchemaGenerator

from .dispatch import API_PREFIX, is_denied

_HTTP_METHODS = ("get", "post", "put", "patch", "delete")
_SUMMARY_MAX = 180


@functools.lru_cache(maxsize=1)
def get_operations():
    """Liste d'opérations `{method, path, area, summary, params, body}`.

    Calculée une seule fois par processus (la génération du schéma prend
    quelques secondes et ne change qu'avec le code)."""
    schema = SchemaGenerator().get_schema(request=None, public=True)
    components = schema.get("components", {}).get("schemas", {})
    operations = []
    for raw_path, item in schema.get("paths", {}).items():
        if not raw_path.startswith(API_PREFIX):
            continue
        path = raw_path[len(API_PREFIX) :]
        if is_denied(path):
            continue
        shared_params = item.get("parameters", [])
        for method in _HTTP_METHODS:
            op = item.get(method)
            if op is None:
                continue
            operations.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "area": path.split("/", 1)[0],
                    "summary": _summary(op),
                    "params": _params(shared_params + op.get("parameters", [])),
                    "body": _body_fields(op, components),
                }
            )
    return operations


def _summary(op):
    text = (op.get("summary") or op.get("description") or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text if len(text) <= _SUMMARY_MAX else text[: _SUMMARY_MAX - 1] + "…"


def _params(parameters):
    result = []
    for param in parameters:
        name = param.get("name")
        if not name:
            continue
        kind = param.get("in", "query")
        if kind not in ("path", "query"):
            continue
        type_ = param.get("schema", {}).get("type", "")
        enum = param.get("schema", {}).get("enum")
        label = f"{name}:{type_}" if type_ else name
        if enum:
            label += "[" + "|".join(str(v) for v in enum) + "]"
        if param.get("required"):
            label += "*"
        result.append({"in": kind, "label": label})
    return result


def _body_fields(op, components):
    content = op.get("requestBody", {}).get("content", {})
    schema = (content.get("application/json") or next(iter(content.values()), {})).get("schema", {})
    schema = _resolve(schema, components)
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields = []
    for name, prop in properties.items():
        prop = _resolve(prop, components)
        if prop.get("readOnly"):
            continue
        type_ = prop.get("type") or ("enum" if "enum" in prop else "")
        label = f"{name}:{type_}" if type_ else name
        if prop.get("enum"):
            label += "[" + "|".join(str(v) for v in prop["enum"] if v not in (None, "")) + "]"
        if name in required:
            label += "*"
        fields.append(label)
    return fields


def _resolve(schema, components):
    ref = schema.get("$ref", "")
    if ref.startswith("#/components/schemas/"):
        return components.get(ref.rsplit("/", 1)[1], {})
    if "allOf" in schema and len(schema["allOf"]) == 1:
        return _resolve(schema["allOf"][0], components)
    return schema


def format_catalog(*, area=None, search=None):
    """Texte compact pour Claude. Sans `area` ni `search` : sommaire par domaine."""
    operations = get_operations()
    if not area and not search:
        counts = {}
        for op in operations:
            counts[op["area"]] = counts.get(op["area"], 0) + 1
        lines = ["Domaines de l'API Awtodo (nombre d'endpoints) :"]
        lines += [f"- {name} ({count})" for name, count in sorted(counts.items())]
        lines.append("Rappeler cet outil avec `area` (ex. \"tasks\") ou `search` pour le détail.")
        return "\n".join(lines)

    selected = operations
    if area:
        selected = [op for op in selected if op["area"] == area.strip("/")]
    if search:
        needle = search.lower()
        selected = [op for op in selected if needle in f"{op['path']} {op['summary']}".lower()]
    if not selected:
        return "Aucun endpoint ne correspond. Appeler sans argument pour la liste des domaines."

    lines = []
    for op in selected:
        lines.append(f"{op['method']} {op['path']}" + (f" — {op['summary']}" if op["summary"] else ""))
        query = [p["label"] for p in op["params"] if p["in"] == "query"]
        if query:
            lines.append(f"    query: {', '.join(query)}")
        if op["body"]:
            lines.append(f"    body: {', '.join(op['body'])}")
    lines.append(
        "(* = obligatoire ; les {segments} du chemin sont des UUID à remplacer. Les champs `body` des "
        "actions (…/start/, …/cancel/…) sont indicatifs : en cas de 400, le message d'erreur précise "
        "les champs réellement attendus.)"
    )
    return "\n".join(lines)
