import hashlib
import secrets

from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.services import is_organisation_admin

from .models import ApiKey


class IntegrationPermissionError(Exception):
    pass


class IntegrationValidationError(Exception):
    pass


def _ensure_can_manage_api_keys(actor, organisation):
    if not is_organisation_admin(actor, organisation):
        raise IntegrationPermissionError("Seul un administrateur de l'organisation peut gérer les clés API.")


def _service_account_for(organisation):
    """Un seul compte de service par organisation, réutilisé par toutes ses
    clés API (créer une clé de plus ne crée pas un nouvel utilisateur — la
    rotation d'une clé compromise ne doit pas non plus changer l'identité
    "au nom de qui" les appels sont faits). Nom technique, jamais affiché
    à l'utilisateur — même famille que `api.ticketing` (seed de démo),
    mais un par organisation plutôt qu'un seul compte partagé global."""
    username = f"api-service-account-{organisation.id}"
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={
            "first_name": "Intégration",
            "last_name": "API",
            "organisation": organisation,
            "is_service_account": True,
        },
    )
    return user


def generate_api_key(*, actor, organisation, name):
    """Retourne `(api_key, raw_key)` — `raw_key` est la seule et unique
    occasion de voir la clé en clair, à ne jamais journaliser/stocker."""
    _ensure_can_manage_api_keys(actor, organisation)
    if not name or not name.strip():
        raise IntegrationValidationError("Un nom est obligatoire pour identifier la clé.")

    raw_key = f"awt_{secrets.token_urlsafe(32)}"
    api_key = ApiKey.objects.create(
        organisation=organisation,
        service_account=_service_account_for(organisation),
        name=name.strip(),
        key_prefix=raw_key[:12],
        key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
        created_by=actor,
    )
    return api_key, raw_key


def list_api_keys(*, actor, organisation):
    _ensure_can_manage_api_keys(actor, organisation)
    return ApiKey.objects.filter(organisation=organisation)


def revoke_api_key(*, actor, api_key):
    _ensure_can_manage_api_keys(actor, api_key.organisation)
    if not api_key.is_active:
        raise IntegrationValidationError("Cette clé est déjà révoquée.")
    api_key.is_active = False
    api_key.revoked_at = timezone.now()
    api_key.save(update_fields=["is_active", "revoked_at"])
    return api_key


def resolve_api_key(raw_key):
    """Utilisé par `ApiKeyAuthentication` — ne lève jamais, renvoie `None` si
    la clé est invalide/révoquée. Met à jour `last_used_at` en aparté (pas
    critique, un échec silencieux de cette mise à jour ne doit pas faire
    échouer l'authentification elle-même)."""
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    try:
        api_key = ApiKey.objects.select_related("service_account").get(key_hash=key_hash, is_active=True)
    except ApiKey.DoesNotExist:
        return None
    ApiKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())
    return api_key
