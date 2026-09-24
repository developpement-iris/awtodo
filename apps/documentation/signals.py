"""Récepteurs des signaux `tasks`/`incidents` qui alimentent la file
« À documenter » (`PendingDocEntry`). Voir CLAUDE.md > règle de dépendances :
`apps.tasks`/`apps.incidents` n'importent jamais `apps.documentation`, le lien
se fait uniquement par signal, dans ce sens. `apps.notifications` est plus
bas dans la hiérarchie (voir Structure du projet) — import direct autorisé
dans ce sens, pas besoin de passer par un signal supplémentaire."""

from django.dispatch import receiver

from apps.incidents.signals import incident_resolved
from apps.notifications.services import notify_doc_entry_pending
from apps.projects.models import ProjectMembership
from apps.tasks.signals import task_completed

from .models import DocSpace, PendingDocEntry

# Seules les tâches qui apportent quelque chose de visible pour l'utilisateur
# final alimentent l'onglet Fonctionnalités. Une `correction` ne documente pas
# une fonctionnalité (décision session 2026-09-03) — les incidents résolus
# couvrent le versant « ce qui a été réparé ».
_DOCUMENTABLE_TASK_TYPES = {"ajout", "evolution"}


def _notify_project_managers(project, **kwargs):
    # Retour direct (session du 2026-09-23) : "envoie des notifs au chef de
    # projet" — un projet collaboratif peut avoir plusieurs chefs de projet
    # simultanément (CLAUDE.md règle n°3), tous notifiés, pas un seul.
    managers = ProjectMembership.objects.filter(project=project, role="chef_de_projet").select_related("user")
    for membership in managers:
        notify_doc_entry_pending(recipient=membership.user, **kwargs)


@receiver(task_completed)
def _on_task_completed(sender, task, actor, **kwargs):
    if task.task_type not in _DOCUMENTABLE_TASK_TYPES:
        return
    space = DocSpace.objects.filter(project=task.project).first()
    if space is None:
        return
    _, created = PendingDocEntry.objects.get_or_create(
        task=task, defaults={"space": space, "kind": "fonctionnalite"}
    )
    if created:
        _notify_project_managers(task.project, task=task)


@receiver(incident_resolved)
def _on_incident_resolved(sender, incident, actor, **kwargs):
    # Un incident rattaché à une Team sans projet n'a pas d'espace de doc :
    # il n'entre pas dans la file.
    if not incident.project_id:
        return
    space = DocSpace.objects.filter(project_id=incident.project_id).first()
    if space is None:
        return
    _, created = PendingDocEntry.objects.get_or_create(
        incident=incident, defaults={"space": space, "kind": "resolution"}
    )
    if created:
        _notify_project_managers(incident.project, incident=incident)
