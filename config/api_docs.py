from drf_spectacular.utils import extend_schema
from drf_spectacular.views import SpectacularSwaggerSplitView
from rest_framework.permissions import AllowAny

_SWAGGER_CDN = "https://cdn.jsdelivr.net"


class ApiDocsView(SpectacularSwaggerSplitView):
    """Page Swagger de l'API. Seule page autorisée à charger le CDN de Swagger UI :
    le CSP global (`apps.common.middleware`) laisse en place un en-tête déjà posé.
    Variante « split » : son script est servi par Awtodo, donc pas d'`unsafe-inline`."""

    permission_classes = [AllowAny]
    url_name = "api-schema"

    CSP = (
        "default-src 'self'; "
        f"script-src 'self' {_SWAGGER_CDN}; "
        f"style-src 'self' 'unsafe-inline' {_SWAGGER_CDN}; "
        f"img-src 'self' data: {_SWAGGER_CDN}; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    @extend_schema(exclude=True)
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response["Content-Security-Policy"] = self.CSP
        return response
