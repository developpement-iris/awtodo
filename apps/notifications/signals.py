from django.dispatch import receiver

from apps.incidents.signals import incident_commented
from apps.planning.signals import event_participant_invited
from apps.tasks.signals import task_assigned, task_commented

from .services import (
    notify_event_invited,
    notify_incident_commented,
    notify_task_assigned,
    notify_task_commented,
)


@receiver(task_assigned)
def handle_task_assigned(sender, task, actor, **kwargs):
    notify_task_assigned(task=task, actor=actor)


@receiver(task_commented)
def handle_task_commented(sender, task, comment, actor, **kwargs):
    notify_task_commented(task=task, comment=comment, actor=actor)


@receiver(incident_commented)
def handle_incident_commented(sender, incident, comment, actor, **kwargs):
    notify_incident_commented(incident=incident, comment=comment, actor=actor)


@receiver(event_participant_invited)
def handle_event_participant_invited(sender, event, participant, actor, **kwargs):
    notify_event_invited(event=event, participant=participant, actor=actor)
