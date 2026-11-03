"""Routes OAuth montées à la racine du site (namespace `oauth2_provider`,
attendu par les vues de métadonnées de django-oauth-toolkit pour construire
les URL des endpoints).

Sous-ensemble volontaire des routes du toolkit : ni gestion d'applications
par l'utilisateur, ni flux device ; gestion RFC 7592 d'un client enregistré
en lecture/désinscription seulement (voir `ReadOnlyClientManagementView`).
"""

from django.urls import path
from oauth2_provider import views as oauth_views

from .oauth import McpAuthorizationView, ReadOnlyClientManagementView
from .views import McpLoginView

app_name = "oauth2_provider"

urlpatterns = [
    path(".well-known/oauth-authorization-server", oauth_views.OAuthServerMetadataView.as_view(), name="oauth-server-metadata"),
    path(".well-known/oauth-protected-resource", oauth_views.OAuthProtectedResourceMetadataView.as_view(), name="oauth-resource-metadata"),
    path(
        ".well-known/oauth-protected-resource/<path:resource_path>",
        oauth_views.OAuthProtectedResourceMetadataView.as_view(),
        name="oauth-resource-metadata-path",
    ),
    path("o/login/", McpLoginView.as_view(), name="mcp-login"),
    path("o/authorize/", McpAuthorizationView.as_view(), name="authorize"),
    path("o/token/", oauth_views.TokenView.as_view(), name="token"),
    path("o/revoke_token/", oauth_views.RevokeTokenView.as_view(), name="revoke-token"),
    path("o/register/", oauth_views.DynamicClientRegistrationView.as_view(), name="dcr-register"),
    path("o/register/<str:client_id>/", ReadOnlyClientManagementView.as_view(), name="dcr-register-management"),
]
