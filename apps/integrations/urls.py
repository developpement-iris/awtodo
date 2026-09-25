from django.urls import path

from .views import ApiKeyListView, ApiKeyRevokeView

urlpatterns = [
    path("api-keys/", ApiKeyListView.as_view(), name="api-key-list"),
    path("api-keys/<uuid:api_key_id>/revoke/", ApiKeyRevokeView.as_view(), name="api-key-revoke"),
]
