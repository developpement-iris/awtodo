from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view

from apps.common.schema import no_body

from .serializers import DashboardWidgetCreateSerializer, DashboardWidgetPositionSerializer

dashboard_schema = extend_schema_view(
    get=extend_schema(responses=OpenApiTypes.OBJECT),
    post=extend_schema(request=DashboardWidgetCreateSerializer, responses={201: OpenApiTypes.OBJECT}),
)
widget_detail_schema = extend_schema_view(
    patch=extend_schema(request=DashboardWidgetPositionSerializer, responses=OpenApiTypes.OBJECT),
    delete=no_body(),
)
catalog_schema = extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter("scope", OpenApiTypes.STR, enum=["projet", "global"], required=True),
            OpenApiParameter("project_id", OpenApiTypes.UUID, description="Requis si `scope=projet`."),
        ],
        responses=OpenApiTypes.OBJECT,
    )
)
