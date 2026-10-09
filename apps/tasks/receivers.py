"""Crée les types de tâche par défaut à la naissance d'une portée (groupe, ou
projet sans groupe) — voir `seed_default_task_types`. Écoute `post_save` de
`accounts.Team`/`projects.Project` : `tasks` dépend déjà de ces deux apps, et
elles n'ont jamais à importer `tasks` pour ça."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import Team
from apps.projects.models import Project

from .services import seed_default_task_types


@receiver(post_save, sender=Team)
def _seed_team_task_types(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        seed_default_task_types(instance)


@receiver(post_save, sender=Project)
def _seed_project_task_types(sender, instance, created, raw=False, **kwargs):
    if created and not raw and instance.team_id is None:
        seed_default_task_types(instance)
