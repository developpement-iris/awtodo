from django.conf import settings
from django.db import models

from apps.common.models import StatusLifecycleModel, TimeStampedModel, UUIDModel

KIND_CHOICES = [
    ("jalon", "Jalon"),
    ("phase", "Phase"),
    ("reunion", "Réunion"),
    ("autre", "Autre"),
]


class RecurringEventModel(models.Model):
    """Mixin abstrait pour les objets d'agenda récurrents (CalendarEvent,
    ProjectPlanningEntry).

    Un événement ponctuel a `recurrence_rule` vide. Sinon, une chaîne RRULE
    iCal, valeur seule (sans le préfixe « RRULE: »), par ex.
    ``FREQ=WEEKLY;BYDAY=TU;INTERVAL=2;UNTIL=20261231T235959Z``.

    Décision cadrée (voir CLAUDE.md > Roadmap) : l'édition ne porte JAMAIS sur
    une occurrence isolée — modifier ou annuler agit sur toute la série. Pas
    d'EXDATE, pas de RECURRENCE-ID. L'expansion en occurrences concrètes se
    fait à la lecture, dans une fenêtre bornée (voir
    ``apps.planning.services.expand_occurrences``)."""

    start = models.DateTimeField()
    end = models.DateTimeField()
    all_day = models.BooleanField(default=False)
    recurrence_rule = models.TextField(blank=True, default="")

    class Meta:
        abstract = True


class CalendarEvent(UUIDModel, TimeStampedModel, StatusLifecycleModel, RecurringEventModel):
    """Événement du calendrier personnel d'un utilisateur (`owner` = organisateur).
    Peut avoir des participants (voir `EventParticipant`) : une seule ligne,
    vue par tout le monde, éditée par le seul organisateur."""

    STATUS_CHOICES = [
        ("confirme", "Confirmé"),
        ("annule", "Annulé"),
    ]
    ACTIVE_STATUSES = frozenset({"confirme"})

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calendar_events"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    location = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="confirme")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["start"]

    def __str__(self):
        return f"{self.title} — {self.owner}"


class EventParticipant(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    """Invitation d'un utilisateur à un `CalendarEvent`. L'organisateur ajoute
    et retire ; le participant ne peut que répondre (`response`)."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("removed", "Retirée"),
    ]
    ACTIVE_STATUSES = frozenset({"active"})
    RESPONSE_CHOICES = [
        ("invite", "Invité"),
        ("accepte", "Accepté"),
        ("refuse", "Refusé"),
    ]

    event = models.ForeignKey(CalendarEvent, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_participations"
    )
    response = models.CharField(max_length=20, choices=RESPONSE_CHOICES, default="invite")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        constraints = [
            models.UniqueConstraint(
                fields=["event", "user"],
                condition=models.Q(status="active"),
                name="uniq_active_event_participant",
            ),
        ]

    def __str__(self):
        return f"{self.user} — {self.event.title}"


class ScheduledBlock(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    """Créneau posé sur une tâche ou un incident assigné à `owner` (glisser-
    déposer du calendrier personnel). Pas de récurrence. Planifier un créneau
    ne change JAMAIS le statut de la tâche/incident (découplage acté)."""

    STATUS_CHOICES = [
        ("planifie", "Planifié"),
        ("annule", "Annulé"),
    ]
    ACTIVE_STATUSES = frozenset({"planifie"})

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scheduled_blocks"
    )
    task = models.ForeignKey(
        "tasks.Task", null=True, blank=True, on_delete=models.SET_NULL, related_name="scheduled_blocks"
    )
    incident = models.ForeignKey(
        "incidents.Incident", null=True, blank=True, on_delete=models.SET_NULL, related_name="scheduled_blocks"
    )
    start = models.DateTimeField()
    end = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planifie")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["start"]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(task__isnull=False, incident__isnull=True)
                    | models.Q(task__isnull=True, incident__isnull=False)
                ),
                name="scheduledblock_exactly_one_target",
            ),
        ]

    def __str__(self):
        return f"Créneau {self.task or self.incident} — {self.owner}"


class ProjectPlanningEntry(UUIDModel, TimeStampedModel, StatusLifecycleModel, RecurringEventModel):
    """Entrée du planning partagé d'un projet. Visible par tous les membres,
    éditable par les chefs de projet uniquement."""

    STATUS_CHOICES = [
        ("confirme", "Confirmé"),
        ("annule", "Annulé"),
    ]
    ACTIVE_STATUSES = frozenset({"confirme"})
    KIND_CHOICES = KIND_CHOICES

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="planning_entries"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="autre")
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="project_planning_entries",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="confirme")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["start"]

    def __str__(self):
        return f"{self.project.name} — {self.title}"


class CalendarShare(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    """Partage en lecture seule du calendrier personnel de `owner` vers
    `grantee` (superposition). Révocable par l'un ou l'autre."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("revoked", "Révoquée"),
    ]
    ACTIVE_STATUSES = frozenset({"active"})

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calendar_shares_granted"
    )
    grantee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calendar_shares_received"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "grantee"],
                condition=models.Q(status="active"),
                name="uniq_active_calendar_share",
            ),
            models.CheckConstraint(
                check=~models.Q(owner=models.F("grantee")),
                name="calendarshare_owner_not_grantee",
            ),
        ]

    def __str__(self):
        return f"{self.owner} → {self.grantee}"
