import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class StatusQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status__in=self.model.ACTIVE_STATUSES)


class ActiveManager(models.Manager.from_queryset(StatusQuerySet)):
    def get_queryset(self):
        return super().get_queryset().active()


class StatusLifecycleModel(models.Model):
    """
    Contrat pour les sous-classes : définir un champ `status` (CharField avec
    ses propres choices) et un `ACTIVE_STATUSES` (frozenset des valeurs de
    statut considérées comme actives). `objects` (manager par défaut) ne
    retourne que les objets actifs ; `all_objects` donne accès à
    l'historique complet, y compris les statuts terminaux — conformément à
    la règle projet interdisant toute suppression physique.

    ⚠️ Chaque sous-classe concrète DOIT déclarer sa propre :
        class Meta:
            default_manager_name = "all_objects"
            base_manager_name = "all_objects"
    Ça ne s'hérite PAS automatiquement ici : avec plusieurs bases abstraites
    (`UUIDModel, TimeStampedModel, StatusLifecycleModel`), Django ne reprend
    le Meta que de la première base de la liste qui en déclare un —
    `UUIDModel`, qui n'a que `abstract = True` — et ignore silencieusement
    celui des bases suivantes, y compris celui-ci.
    `default_manager_name` gouverne les relations inverses
    (`project.tasks.all()`) — sans lui, elles passent silencieusement par
    `objects` (filtré) et masquent les objets archivés/rejetés.
    `base_manager_name` gouverne le collecteur de suppression en cascade
    (ex. `on_delete=PROTECT`) — sans lui, une contrainte PROTECT pourrait ne
    pas voir les lignes historiques. Les deux doivent être définis, ce sont
    deux mécanismes Django distincts. Vérifié par
    `apps/common/tests/test_models.py`.
    """

    ACTIVE_STATUSES: frozenset = frozenset()

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True


class AuditLogEntry(UUIDModel, TimeStampedModel):
    """Historique champ par champ, générique à n'importe quel modèle métier
    (Task, Incident, plus tard Project si le besoin se confirme) — une seule
    table plutôt qu'un modèle dupliqué par entité, via les content types
    Django. Alimentée exclusivement par `apps.common.audit.record_changes`,
    jamais créée à la main dans un serializer/une vue (CLAUDE.md règle n°1).
    Pas de StatusLifecycleModel : une entrée d'audit est un fait immuable une
    fois écrite, jamais éditée ni "archivée" — pas d'état terminal à
    distinguer d'un état actif."""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="audit_entries")
    field_name = models.CharField(max_length=100)
    # Valeurs déjà mises en forme lisible (résolution des `choices` faite à
    # l'écriture par `record_changes`, voir apps/common/audit.py) — chaînes
    # vides plutôt que `None`, jamais littéralement "None" affiché.
    old_value = models.TextField(blank=True, default="")
    new_value = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"{self.field_name}: {self.old_value!r} → {self.new_value!r} ({self.actor})"
