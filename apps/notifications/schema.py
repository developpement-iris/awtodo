from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers

from apps.common.schema import body, no_body

from .serializers import NotificationSerializer

notification_schema = extend_schema_view(
    mark_read=no_body(NotificationSerializer),
    mark_all_read_action=no_body(),
    unread_count=extend_schema(responses=body("UnreadNotificationCount", count=serializers.IntegerField())),
)
