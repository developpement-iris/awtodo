from django.db import models

from apps.common.models import TimeStampedModel, UUIDModel


class ApiKey(UUIDModel, TimeStampedModel):
    """Clé API machine-à-machine, générée par un administrateur d'organisation
    (voir `apps.integrations.services.generate_api_key`) — destinée aux
    systèmes externes (ticketing, Power Automate) qui n'ont pas de compte
    Awtodo humain. Authentifiée via `apps.integrations.authentication.
    ApiKeyAuthentication`, qui résout la clé vers `service_account`, un
    utilisateur `is_service_account=True` dédié à l'organisation (même
    principe que `User.is_service_account` déjà utilisé par
    `IncidentViewSet.create` pour contourner la contrainte de groupe — aucun
    changement nécessaire côté tâches/incidents, une clé API rejoue
    exactement le même contournement qu'un appel `X-Debug-User-Id` marqué
    service account, mais valable en production).

    La valeur en clair n'est **jamais stockée** : seul son empreinte SHA-256
    (`key_hash`) l'est, comparée à chaque requête. `key_prefix` (les 12
    premiers caractères, non secrets) permet d'identifier une clé dans
    l'interface sans avoir à la reconnaître en clair — la valeur complète
    n'est renvoyée qu'une seule fois, à la génération (voir le service)."""

    organisation = models.ForeignKey(
        "accounts.Organisation", on_delete=models.CASCADE, related_name="api_keys"
    )
    service_account = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="api_keys"
    )
    name = models.CharField(max_length=150)
    key_prefix = models.CharField(max_length=12, db_index=True)
    key_hash = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="+"
    )
    # Pas de suppression physique (règle transverse, voir CLAUDE.md) : une clé
    # compromise/obsolète est révoquée, jamais retirée de la base — reste
    # visible dans l'historique de l'organisation.
    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.key_prefix}…)"
