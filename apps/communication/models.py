from django.conf import settings
from django.db import models

from apps.common.models import StatusLifecycleModel, TimeStampedModel, UUIDModel

# ⚠️ Câblage d'envoi non branché dans cette passe (scaffolding). Toute la
# connexion réelle (Microsoft Graph pour les mails, webhook Power Automate
# pour les canaux Teams) est reportée au déploiement AWS, en même temps que
# le SSO. Voir docs/modeles-et-api.md > "Module Communication".


class O365Connection(UUIDModel, TimeStampedModel):
    """Connexion Office 365 au niveau **organisation** — un seul jeu
    d'identifiants Graph par tenant (les dupliquer par projet serait un
    non-sens de sécurité). Le choix des destinataires, lui, est par projet
    (`CommunicationChannel`).

    Champs inertes pour l'instant : renseignables via l'onglet Communication
    (bloc réservé à un admin d'organisation), mais aucun appel n'est encore
    émis."""

    organisation = models.OneToOneField(
        "accounts.Organisation", on_delete=models.CASCADE, related_name="o365_connection"
    )
    tenant_id = models.CharField(max_length=100, blank=True, default="")
    client_id = models.CharField(max_length=100, blank=True, default="")
    # Stocké tel quel pour l'instant (scaffolding). Au câblage réel : chiffrer
    # au repos / déléguer à un secret manager AWS, ne jamais renvoyer en clair.
    client_secret = models.CharField(max_length=255, blank=True, default="")
    # Boîte aux lettres expéditrice par défaut (From:) pour les envois Graph.
    sender_mailbox = models.EmailField(blank=True, default="")
    is_enabled = models.BooleanField(default=False)

    def __str__(self):
        return f"Connexion O365 — {self.organisation}"

    @property
    def is_configured(self):
        return bool(self.tenant_id and self.client_id and self.client_secret and self.sender_mailbox)


class CommunicationChannel(UUIDModel, TimeStampedModel, StatusLifecycleModel):
    """Un destinataire de communication configuré sur un projet : soit une
    adresse mail, soit un canal Teams (via l'URL d'un flow Power Automate —
    voir la note de transport dans docs)."""

    STATUS_CHOICES = [
        ("active", "Actif"),
        ("archived", "Archivé"),
    ]
    ACTIVE_STATUSES = frozenset({"active"})

    TYPE_CHOICES = [
        ("email", "Adresse mail"),
        ("teams", "Canal Teams"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="communication_channels"
    )
    channel_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    label = models.CharField(max_length=150)
    email = models.EmailField(blank=True, default="")
    # URL du flow Power Automate "Quand une requête HTTP est reçue" qui publie
    # ensuite dans le canal Teams. Inerte pour l'instant.
    teams_webhook_url = models.URLField(blank=True, default="")
    # Notifie ce canal automatiquement à la création d'un incident du projet
    # (câblage reporté — voir apps.communication.signals).
    notify_incident_created = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        default_manager_name = "all_objects"
        base_manager_name = "all_objects"
        ordering = ["channel_type", "label"]

    def __str__(self):
        return f"{self.get_channel_type_display()} — {self.label}"


class CommunicationMessage(UUIDModel, TimeStampedModel):
    """Journal / boîte d'envoi des communications d'un projet. Append-only
    (pas de `StatusLifecycleModel` : jamais édité ni archivé). Dans cette
    passe, un message reste au statut `en_attente` — rien ne l'envoie."""

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
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sent_communications",
    )
    channels = models.ManyToManyField(CommunicationChannel, related_name="messages")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="en_attente")
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} ({self.get_status_display()})"
