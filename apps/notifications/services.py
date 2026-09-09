from django.core.mail import send_mail

from .models import Notification


class NotificationPermissionError(Exception):
    """L'acteur n'a pas le droit d'effectuer cette action."""


def _display_name(user):
    return f"{user.first_name} {user.last_name}".strip() or user.username


def create_notification(*, recipient, verb, message, task=None, incident=None, event=None):
    return Notification.objects.create(
        recipient=recipient, verb=verb, message=message, task=task, incident=incident, event=event
    )


def send_notification_email(notification):
    # Synchrone, backend console en dev — voir "Global Constraints" en tête
    # de ce plan pour la justification (même précédent que les emails
    # d'invitation).
    if not notification.recipient.email:
        return
    send_mail(
        subject="Awtodo — nouvelle notification",
        message=notification.message,
        from_email=None,
        recipient_list=[notification.recipient.email],
        fail_silently=True,
    )


def notify_task_assigned(*, task, actor):
    if task.assignee_id is None or task.assignee_id == actor.id:
        return None
    notification = create_notification(
        recipient=task.assignee,
        verb="task_assigned",
        message=f"{_display_name(actor)} vous a assigné la tâche « {task.title} ».",
        task=task,
    )
    send_notification_email(notification)
    return notification


def notify_task_commented(*, task, comment, actor):
    if task.assignee_id is None or task.assignee_id == actor.id:
        return None
    notification = create_notification(
        recipient=task.assignee,
        verb="task_commented",
        message=f"{_display_name(actor)} a commenté la tâche « {task.title} ».",
        task=task,
    )
    send_notification_email(notification)
    return notification


def notify_incident_commented(*, incident, comment, actor):
    if incident.assigned_to_id is None or incident.assigned_to_id == actor.id:
        return None
    notification = create_notification(
        recipient=incident.assigned_to,
        verb="incident_commented",
        message=f"{_display_name(actor)} a commenté l'incident « {incident.title} ».",
        incident=incident,
    )
    send_notification_email(notification)
    return notification


def notify_event_invited(*, event, participant, actor):
    if participant.user_id == actor.id:
        return None
    notification = create_notification(
        recipient=participant.user,
        verb="event_invited",
        message=f"{_display_name(actor)} vous a invité à l'événement « {event.title} ».",
        event=event,
    )
    send_notification_email(notification)
    return notification


def mark_notification_read(*, actor, notification):
    # Garde en défense en profondeur : `NotificationViewSet.get_queryset()`
    # (Task 4) scope déjà `self.get_object()` à `recipient=request.user`, donc
    # ce cas n'est normalement jamais atteint via l'API (404 avant, même
    # principe que le scoping par appartenance déjà en place ailleurs dans le
    # projet) — reste utile pour un appel direct au service, hors HTTP.
    if notification.recipient_id != actor.id:
        raise NotificationPermissionError("Cette notification ne vous appartient pas.")
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])
    return notification


def mark_all_read(*, actor):
    Notification.objects.filter(recipient=actor, is_read=False).update(is_read=True)


def get_unread_count(*, actor):
    return Notification.objects.filter(recipient=actor, is_read=False).count()
