import logging

import requests
from celery import shared_task
from django.utils import timezone

from .models import CommunicationMessage
from .payload import build_message_context, render_payload_for_channel

logger = logging.getLogger(__name__)
_REQUEST_TIMEOUT = 10


@shared_task
def send_communication_message(message_id):
    """Envoie un `CommunicationMessage` vers chacun de ses canaux Teams (POST
    du payload au flow Power Automate `teams_webhook_url`, gabarit propre à
    chaque canal — voir `apps.communication.payload`). Un canal en échec
    n'empêche pas l'envoi aux autres — le résultat est enregistré par canal
    sur la `CommunicationDelivery` correspondante, jamais un simple booléen
    global. Déclenchée après commit par `apps.communication.services.compose_message`
    (jamais synchrone dans le flux HTTP)."""
    try:
        message = CommunicationMessage.objects.select_related(
            "project", "created_by", "task", "task__assignee", "incident", "incident__assigned_to"
        ).get(id=message_id)
    except CommunicationMessage.DoesNotExist:
        return

    base_context = build_message_context(message)
    # `sent_at` toujours ajouté au moment de l'envoi réel, indépendamment du
    # gabarit — l'heure de composition (`message.created_at`) n'est pas la
    # même chose, et un canal ne devrait pas pouvoir désactiver cette info.
    base_context["message"]["sent_at"] = timezone.now().isoformat()

    overall_ok = True
    for delivery in message.deliveries.select_related("channel"):
        channel = delivery.channel
        payload = render_payload_for_channel(channel, base_context)
        try:
            response = requests.post(channel.teams_webhook_url, json=payload, timeout=_REQUEST_TIMEOUT)
            if 200 <= response.status_code < 300:
                delivery.status = "envoye"
                delivery.response_detail = response.text[:2000]
            else:
                delivery.status = "echec"
                delivery.response_detail = f"HTTP {response.status_code} — {response.text[:2000]}"
                overall_ok = False
        except requests.RequestException as exc:
            delivery.status = "echec"
            delivery.response_detail = str(exc)[:2000]
            overall_ok = False
            logger.exception(
                "Envoi Power Automate échoué pour le message %s → canal %s.", message_id, channel.id
            )
        delivery.responded_at = timezone.now()
        delivery.save(update_fields=["status", "response_detail", "responded_at", "updated_at"])

    message.status = "envoye" if overall_ok else "echec"
    message.sent_at = timezone.now()
    message.save(update_fields=["status", "sent_at"])
