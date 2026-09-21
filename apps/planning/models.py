from datetime import time

from django.conf import settings
from django.db import models

from apps.common.models import StatusLifecycleModel, TimeStampedModel, UUIDModel

KIND_CHOICES = [
    ("jalon", "Jalon"),
    ("phase", "Phase"),
    ("reunion", "Réunion"),
    ("autre", "Autre"),
]

WEEKDAY_CHOICES = [
    (0, "Lundi"),
    (1, "Mardi"),
    (2, "Mercredi"),
    (3, "Jeudi"),
    (4, "Vendredi"),
    (5, "Samedi"),
    (6, "Dimanche"),
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
    # Droit additionnel, optionnel (session du 2026-09-18) : au-delà de la
    # simple superposition en lecture, `grantee` peut modifier les horaires
    # de travail de `owner` (base hebdomadaire + exceptions par semaine, voir
    # `WorkingHoursDay`/`WorkingHoursWeekOverride`) — utile pour un·e
    # assistant·e qui tient l'agenda de quelqu'un d'autre. Toujours `False`
    # par défaut : ne change rien au comportement d'un partage existant.
    can_manage_work_hours = models.BooleanField(default=False)

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


class WorkingHoursDay(UUIDModel, TimeStampedModel):
    """Une ligne par jour de semaine (0=lundi..6=dimanche) : horaires de
    travail récurrents d'un utilisateur, affichés dans son planning (grise le
    reste de la grille Semaine). Remplace `User.work_hours_start/end` (passe
    précédente, un seul horaire pour toute la semaine — trop rigide, retour
    direct : "on doit pouvoir modifier jour par jour").

    Pas de `StatusLifecycleModel` ici : les 7 lignes existent toujours pour
    un utilisateur donné (créées à la demande, `get_or_create`), on les met à
    jour en place — ce n'est pas une entité métier avec un historique à
    conserver, au même titre que `User.planning_color` (simple champ
    overwritable, pas de cycle de vie)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="working_hours_days"
    )
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES)
    # Jour non travaillé (grisé entièrement) plutôt que start==end : plus
    # explicite pour le calcul de grisage et pour l'UI (case à cocher, pas
    # une plage vide à interpréter).
    enabled = models.BooleanField(default=True)
    start = models.TimeField(default=time(9, 0))
    end = models.TimeField(default=time(18, 0))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "weekday"], name="uniq_working_hours_day"),
        ]
        ordering = ["weekday"]

    def __str__(self):
        return f"{self.user} — {self.get_weekday_display()}"


class WorkingHoursWeekOverride(UUIDModel, TimeStampedModel):
    """Exception ponctuelle au modèle hebdomadaire récurrent, pour une
    semaine calendaire précise (`week_start` = lundi de cette semaine) —
    retour direct : "on doit pouvoir le faire semaine par semaine" (congé,
    semaine chargée...). Supprimée (vraie suppression, pas un statut) quand
    l'utilisateur retire l'exception : même raisonnement que `WorkingHoursDay`
    ci-dessus, c'est un réglage d'affichage, pas une donnée métier à tracer."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="working_hours_overrides"
    )
    week_start = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "week_start"], name="uniq_working_hours_week_override"),
        ]
        ordering = ["week_start"]

    def __str__(self):
        return f"{self.user} — semaine du {self.week_start}"


class WorkingHoursOverrideDay(UUIDModel, TimeStampedModel):
    """Un jour de l'exception `WorkingHoursWeekOverride` — même forme que
    `WorkingHoursDay`, portée à la semaine plutôt qu'au modèle de base."""

    override = models.ForeignKey(WorkingHoursWeekOverride, on_delete=models.CASCADE, related_name="days")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES)
    enabled = models.BooleanField(default=True)
    start = models.TimeField(default=time(9, 0))
    end = models.TimeField(default=time(18, 0))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["override", "weekday"], name="uniq_working_hours_override_day"),
        ]
        ordering = ["weekday"]

    def __str__(self):
        return f"{self.override} — {self.get_weekday_display()}"
