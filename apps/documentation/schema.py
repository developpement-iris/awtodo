"""Les réponses de la documentation sont des dicts assemblés par `services` :
décrites comme des objets génériques, seuls les corps de requête sont détaillés."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.common.schema import FILE_UPLOAD, file_response, no_body

from .serializers import (
    ContributorsUpdateSerializer,
    DocEntryCreateSerializer,
    DocEntryUpdateSerializer,
    DocPageCreateSerializer,
    DocPageUpdateSerializer,
    DocSpaceAppearanceSerializer,
    DocSpaceSlugSerializer,
)

_OBJECT = OpenApiTypes.OBJECT
_API_KEY = "Accessible aussi avec une clé API de l'organisation du projet."


def _update(request, **kwargs):
    return extend_schema(request=request, responses=_OBJECT, **kwargs)


def _create(request, **kwargs):
    return extend_schema(request=request, responses={201: _OBJECT}, **kwargs)


doc_space_schema = extend_schema_view(
    create_page=_create(DocPageCreateSerializer),
    page_detail=[_update(DocPageUpdateSerializer, methods=["PATCH"]), no_body(methods=["DELETE"])],
    publish_page=no_body(_OBJECT),
    unpublish_page=no_body(_OBJECT),
    support_pages=extend_schema(description=_API_KEY, responses={200: {"type": "array", "items": {"type": "object"}}}),
    page_attachments=extend_schema(description=_API_KEY, request=FILE_UPLOAD, responses={201: _OBJECT}),
    page_attachment_detail=[
        extend_schema(methods=["GET"], description=_API_KEY, responses=file_response()),
        no_body(methods=["DELETE"], description=_API_KEY),
    ],
    create_entry=_create(DocEntryCreateSerializer),
    entry_detail=[
        _update(DocEntryUpdateSerializer, methods=["PATCH"]),
        extend_schema(methods=["DELETE"], request=None, responses=_OBJECT),
    ],
    publish_entry=no_body(_OBJECT),
    unpublish_entry=no_body(_OBJECT),
    seed_from_spec=no_body({201: _OBJECT}),
    pending_create_entry=no_body({201: _OBJECT}),
    pending_ignore=no_body(),
    generate_contributors=no_body({201: _OBJECT}),
    update_contributors=_update(ContributorsUpdateSerializer),
    public_link=[no_body(_OBJECT, methods=["POST"]), no_body(_OBJECT, methods=["DELETE"])],
    public_link_rotate=no_body(_OBJECT),
    public_link_slug=_update(DocSpaceSlugSerializer),
    appearance=[
        extend_schema(methods=["GET"], description=_API_KEY, responses=_OBJECT),
        _update(DocSpaceAppearanceSerializer, methods=["PATCH"], description=_API_KEY),
    ],
)
