from django.conf import settings
from django.db import models

from apps.common.models import StatusLifecycleModel, TimeStampedModel, UUIDModel


class BudgetLine(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    """Onglet "Budgétisation" du hub projet (voir docs/modeles-et-api.md) —
    ligne de budget simple (libellé × quantité × prix unitaire), distincte de
    `BudgetEntry` ci-dessous (temps passé × coût horaire, toujours hors
    périmètre v1). Deux tableaux (`category`), sommes calculées côté API
    (`amount`) plutôt que stockées — jamais désynchronisées d'une édition de
    `quantity`/`unit_price`."""

    CATEGORY_CHOICES = [
        ("opex", "OPEX"),
        ("capex", "CAPEX"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("removed", "Retirée"),
    ]
    ACTIVE_STATUSES = frozenset({"active"})

    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="budget_lines")
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    label = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_budget_lines",
    )

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"

    @property
    def amount(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.project} — {self.label} ({self.get_category_display()})"


class BudgetEntry(UUIDModel, TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="budget_entries")
    task = models.ForeignKey(
        "tasks.Task",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="budget_entries",
    )
    hours = models.DecimalField(max_digits=6, decimal_places=2)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f"{self.project} — {self.hours}h"
