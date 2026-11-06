from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.common.schema import no_body

from .serializers import (
    CommunicationChannelCreateSerializer,
    CommunicationChannelSerializer,
    CommunicationChannelUpdateSerializer,
    CommunicationComposeSerializer,
    CommunicationMessageSerializer,
    O365ConnectionSerializer,
)

o365_schema = extend_schema_view(
    get=extend_schema(responses=O365ConnectionSerializer),
    put=extend_schema(request=O365ConnectionSerializer, responses=O365ConnectionSerializer),
)

communication_schema = extend_schema_view(
    channels=[
        extend_schema(methods=["GET"], responses=CommunicationChannelSerializer(many=True)),
        extend_schema(
            methods=["POST"],
            request=CommunicationChannelCreateSerializer,
            responses={201: CommunicationChannelSerializer},
        ),
    ],
    channel_detail=[
        extend_schema(
            methods=["PATCH"], request=CommunicationChannelUpdateSerializer, responses=CommunicationChannelSerializer
        ),
        no_body(methods=["DELETE"]),
    ],
    messages=[
        extend_schema(methods=["GET"], responses=CommunicationMessageSerializer(many=True)),
        extend_schema(
            methods=["POST"], request=CommunicationComposeSerializer, responses={201: CommunicationMessageSerializer}
        ),
    ],
)
