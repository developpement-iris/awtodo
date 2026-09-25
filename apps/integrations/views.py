from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import ApiKey
from .serializers import ApiKeyCreatedSerializer, ApiKeyCreateSerializer, ApiKeySerializer


class _IntegrationExceptionMixin:
    """Traduit les exceptions de service en codes HTTP (comme
    apps.communication / apps.planning / apps.documentation)."""

    def handle_exception(self, exc):
        if isinstance(exc, services.IntegrationPermissionError):
            return Response({"detail": str(exc)}, status=403)
        if isinstance(exc, services.IntegrationValidationError):
            return Response({"detail": str(exc)}, status=400)
        return super().handle_exception(exc)


class ApiKeyListView(_IntegrationExceptionMixin, APIView):
    """Clés API de l'organisation de l'utilisateur courant. Lecture et
    création réservées à un admin d'organisation (garde dans le service)."""

    @extend_schema(responses=ApiKeySerializer(many=True))
    def get(self, request):
        keys = services.list_api_keys(actor=request.user, organisation=request.user.organisation)
        return Response(ApiKeySerializer(keys, many=True).data)

    @extend_schema(request=ApiKeyCreateSerializer, responses=ApiKeyCreatedSerializer)
    def post(self, request):
        serializer = ApiKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        api_key, raw_key = services.generate_api_key(
            actor=request.user, organisation=request.user.organisation, **serializer.validated_data
        )
        # `key` en clair : présente uniquement dans cette réponse, jamais
        # relisible ensuite (voir ApiKey.key_hash).
        return Response({**ApiKeySerializer(api_key).data, "key": raw_key}, status=201)


class ApiKeyRevokeView(_IntegrationExceptionMixin, APIView):
    @extend_schema(request=None, responses=ApiKeySerializer)
    def post(self, request, api_key_id):
        api_key = get_object_or_404(ApiKey, id=api_key_id, organisation=request.user.organisation)
        api_key = services.revoke_api_key(actor=request.user, api_key=api_key)
        return Response(ApiKeySerializer(api_key).data)
