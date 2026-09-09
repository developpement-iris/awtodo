"""Récepteurs des signaux `tasks`/`incidents` qui alimentent la file
« À documenter » (`PendingDocEntry`). Voir CLAUDE.md > règle de dépendances :
`apps.tasks`/`apps.incidents` n'importent jamais `apps.documentation`, le lien
se fait uniquement par signal, dans ce sens."""

from django.dispatch import receiver

from apps.incidents.signals import incident_resolved
from apps.tasks.signals import task_completed

from .models import DocSpace, PendingDocEntry

# Seules les tâches qui apportent quelque chose de visible pour l'utilisateur
# final alimentent l'onglet Fonctionnalités. Une `correction` ne documente pas
# une fonctionnalité (décision session 2026-09-03) — les incidents résolus
# couvrent le versant « ce qui a été réparé ».
_DOCUMENTABLE_TASK_TYPES = {"ajout", "evolution"}


@receiver(task_completed)
def _on_task_completed(sender, task, actor, **kwargs):
    if task.task_type not in _DOCUMENTABLE_TASK_TYPES:
        return
    space = DocSpace.objects.filter(project=task.project).first()
    if space is None:
        return
    PendingDocEntry.objects.get_or_create(
        task=task, defaults={"space": space, "kind": "fonctionnalite"}
    )


@receiver(incident_resolved)
def _on_incident_resolved(sender, incident, actor, **kwargs):
    # Un incident rattaché à une Team sans projet n'a pas d'espace de doc :
    # il n'entre pas dans la file.
    if not incident.project_id:
        return
    space = DocSpace.objects.filter(project_id=incident.project_id).first()
    if space is None:
        return
    PendingDocEntry.objects.get_or_create(
        incident=incident, defaults={"space": space, "kind": "resolution"}
    )
