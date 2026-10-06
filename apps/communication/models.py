from django.conf import settings
from django.db import models

from apps.common.models import StatusLifecycleModel, TimeStampedModel, UUIDModel

# Câblage réel : canaux Teams via Power Automate uniquement (session du
# 2026-09-28). Le canal email a été abandonné — envoyer un mail "au nom" d'une
# boîte via Microsoft Graph app-only nécessiterait une ApplicationAccessPolicy
# Exchange dédiée pour ne pas exposer tout le tenant à l'envoi ; pas de
# plus-value suffisante face à ce risque (Outlook natif suffit). Voir
# docs/modeles-et-api.md > "Module Communication".


class O365Connection(UUIDModel, TimeStampedModel):
    """Connexion Office 365 au niveau **organisation** — un seul jeu
    d'identifiants Graph par tenant. Utilisée exclusivement par la
    synchronisation Outlook du planning (`apps.planning`) depuis
    l'abandon du canal email de ce module."""

    organisation = models.OneToOneField(
        "accounts.Organisation", on_delete=models.CASCADE, related_name="o365_connection"
    )
    tenant_id = models.CharField(max_length=100, blank=True, default="")
    client_id = models.CharField(max_length=100, blank=True, default="")
    # Stocké tel quel pour l'instant (scaffolding). Au câblage réel : chiffrer
    # au repos / déléguer à un secret manager AWS, ne jamais renvoyer en clair.
    client_secret = models.CharField(max_length=255, blank=True, default="")
    is_enabled = models.BooleanField(default=False)

    def __str__(self):
        return f"Connexion O365 — {self.organisation}"

    @property
    def is_configured(self):
        return bool(self.tenant_id and self.client_id and self.client_secret)


class CommunicationChannel(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    """Un canal Teams configuré sur un projet, relié à un flow Power
    Automate ("Quand une requête HTTP est reçue" → poste dans le canal).
    `teams_channel_id`/`teams_channel_name` sont transmis dans le payload
    envoyé au flow pour qu'il route vers le bon canal Teams avec certitude,
    même si plusieurs canaux Awtodo partagent le même flow/URL de
    déclenchement."""

    STATUS_CHOICES = [
        ("active", "Actif"),
        ("archived", "Archivé"),
    ]
    ACTIVE_STATUSES = frozenset({"active"})

    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="communication_channels"
    )
    label = models.CharField(max_length=150)
    # Identifiant et nom du canal Teams cible côté Microsoft — transmis au
    # flow PA dans le payload d'envoi (voir apps.communication.tasks), pour
    # router avec certitude même si l'URL de déclenchement est partagée.
    teams_channel_id = models.CharField(max_length=255, blank=True, default="")
    teams_channel_name = models.CharField(max_length=150, blank=True, default="")
    # URL du flow Power Automate "Quand une requête HTTP est reçue" qui
    # publie ensuite dans le canal Teams. `max_length` relevé explicitement
    # (bug corrigé le 2026-10-06) : le défaut Django (200) est trop court
    # pour une URL de déclenchement Power Platform signée (SAS), qui dépasse
    # couramment 300-400 caractères — provoquait un 500 non géré à l'INSERT
    # sur Postgres (silencieux sur SQLite en dev, qui n'impose pas la
    # longueur de colonne).
    teams_webhook_url = models.URLField(blank=True, default="", max_length=1000)
    # Gabarit de payload personnalisable (session du 2026-09-28) — objet JSON
    # plat `{clé: "{{espace.champ}}" | valeur littérale}`, résolu par
    # apps.communication.payload.render_payload_for_channel. Vide = payload
    # par défaut (apps.communication.payload.DEFAULT_TEMPLATE).
    payload_template = models.JSONField(blank=True, default=dict)
    # Notifie ce canal automatiquement à la création d'un incident du projet
    # (câblage reporté — voir apps.communication.signals).
    notify_incident_created = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["label"]

    def __str__(self):
        return f"Canal Teams — {self.label}"


class CommunicationMessage(UUIDModel, TimeStampedModel):
    """Journal / boîte d'envoi des communications d'un projet. Append-only
    (pas de `StatusLifecycleModel` : jamais édité ni archivé). `status`
    résume l'envoi (tous les canaux ont réussi ou non) — le détail par canal
    vit dans `CommunicationDelivery`."""

    TRIGGER_CHOICES = [
        ("manuel", "Manuel"),
        ("incident_cree", "Création d'incident"),
    ]
    STATUS_CHOICES = [
        ("en_attente", "En attente d'envoi"),
        ("envoye", "Envoyé"),
        ("echec", "Échec"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="communication_messages"
    )
    subject = models.CharField(max_length=255)
    body = models.TextField()
    trigger = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default="manuel")
    incident = models.ForeignKey(
        "incidents.Incident", null=True, blank=True, on_delete=models.PROTECT, related_name="communications"
    )
    # Tâche jointe à la rédaction manuelle (session du 2026-09-28) — rend ses
    # champs disponibles au gabarit de payload (`{{task.*}}`), au même titre
    # qu'un incident déjà rattachable. Optionnel, aucune contrainte XOR avec
    # `incident` (rien n'empêche techniquement les deux, juste rarement
    # pertinent en pratique).
    task = models.ForeignKey(
        "tasks.Task", null=True, blank=True, on_delete=models.PROTECT, related_name="communications"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sent_communications",
    )
    channels = models.ManyToManyField(CommunicationChannel, through="CommunicationDelivery", related_name="messages")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="en_attente")
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} ({self.get_status_display()})"


class CommunicationDelivery(UUIDModel, TimeStampedModel):
    """Résultat d'envoi d'un `CommunicationMessage` vers un
    `CommunicationChannel` précis — un message envoyé à plusieurs canaux
    peut réussir sur l'un et échouer sur l'autre, d'où une ligne par paire
    plutôt qu'un statut unique sur le message. `response_detail` porte la
    réponse brute (tronquée) renvoyée par le flow Power Automate, affichée
    telle quelle dans l'historique."""

    STATUS_CHOICES = CommunicationMessage.STATUS_CHOICES

    message = models.ForeignKey(CommunicationMessage, on_delete=models.CASCADE, related_name="deliveries")
    channel = models.ForeignKey(CommunicationChannel, on_delete=models.PROTECT, related_name="deliveries")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="en_attente")
    response_detail = models.TextField(blank=True, default="")
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["message", "channel"], name="unique_delivery_per_message_channel")
        ]

    def __str__(self):
        return f"{self.channel.label} — {self.get_status_display()}"
