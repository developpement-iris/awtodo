"""Amorce le catalogue par défaut à la naissance d'une portée (groupe, ou
projet sans groupe). Même schéma que `apps.tasks.receivers` : `evaluations`
dépend déjà d'`accounts`/`projects`, qui n'ont jamais à l'importer."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import Team
from apps.projects.models import Project

from .catalog import seed_default_catalog


@receiver(post_save, sender=Team)
def _seed_team_catalog(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        seed_default_catalog(instance)


@receiver(post_save, sender=Project)
def _seed_project_catalog(sender, instance, created, raw=False, **kwargs):
    if created and not raw and instance.team_id is None:
        seed_default_catalog(instance)
