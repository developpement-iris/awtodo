from contextlib import contextmanager

from django.contrib.contenttypes.models import ContentType

from .models import AuditLogEntry

# Jamais pertinents à journaliser : la PK ne change jamais, les deux
# horodatages changent à *chaque* sauvegarde (bruit garanti, pas un vrai
# changement métier).
EXCLUDED_FIELDS = {"id", "created_at", "updated_at"}


def _display_value(field, raw_value):
    """Résout une valeur brute de champ en libellé lisible — générique à
    n'importe quel champ `choices=` (statut, priorité, type...), sans code
    spécifique par modèle : Django expose déjà `field.choices`."""
    if raw_value is None:
        return ""
    if field.choices:
        return str(dict(field.choices).get(raw_value, raw_value))
    return str(raw_value)


def _resolve_organisation(actor, organisation):
    if organisation is not None:
        return organisation
    if actor is not None:
        return actor.organisation
    raise ValueError("organisation doit être fourni explicitement quand actor est None.")


@contextmanager
def record_changes(instance, *, actor, project=None, team=None, organisation=None):
    """Capture l'état de chaque champ de `instance` avant le bloc, puis
    journalise dans `AuditLogEntry` tout champ qui a changé après le bloc
    (typiquement une mutation suivie d'un `.save()`). Usage :

        with record_changes(task, actor=actor, project=task.project):
            task.status = "en_cours"
            task.save()

    `project`/`team` : contexte de scoping (session du 2026-09-29, voir
    docs/modeles-et-api.md > "Historique d'activité") — dénormalisé sur
    chaque ligne créée pour que l'historique d'un projet/groupe soit une
    requête indexée, pas un recoupement à la lecture. `organisation` est
    déduit de `actor.organisation` si non fourni — obligatoire à préciser
    explicitement quand `actor=None` (action système).

    Comparaison sur `field.attname` (ex. `assignee_id`), pas `field.name` :
    évite de déclencher une requête pour résoudre l'objet lié juste pour le
    comparer — seul l'identifiant compte pour détecter un changement."""
    fields = [f for f in instance._meta.fields if f.attname not in EXCLUDED_FIELDS]
    before = {f.attname: getattr(instance, f.attname) for f in fields}

    yield

    resolved_organisation = _resolve_organisation(actor, organisation)
    content_type = ContentType.objects.get_for_model(type(instance))
    for field in fields:
        old_raw = before[field.attname]
        new_raw = getattr(instance, field.attname)
        if old_raw == new_raw:
            continue
        AuditLogEntry.objects.create(
            content_type=content_type,
            object_id=instance.id,
            actor=actor,
            organisation=resolved_organisation,
            project=project,
            team=team,
            verb="field_changed",
            field_name=field.name,
            old_value=_display_value(field, old_raw),
            new_value=_display_value(field, new_raw),
        )


def record_event(instance, *, actor, verb, description, project=None, team=None, organisation=None):
    """Journalise un événement discret qui n'est pas un diff de champ —
    création, commentaire, ajout/retrait de membre, ligne de budget...
    Mêmes règles de scoping que `record_changes`."""
    content_type = ContentType.objects.get_for_model(type(instance))
    return AuditLogEntry.objects.create(
        content_type=content_type,
        object_id=instance.id,
        actor=actor,
        organisation=_resolve_organisation(actor, organisation),
        project=project,
        team=team,
        verb=verb,
        field_name="",
        old_value="",
        new_value=description,
    )


def get_audit_log(instance):
    content_type = ContentType.objects.get_for_model(type(instance))
    return AuditLogEntry.objects.filter(content_type=content_type, object_id=instance.id).select_related("actor")


def get_project_audit_log(project):
    """Historique complet d'un projet (session du 2026-09-29) — réservé au
    chef de projet côté vue, voir apps.projects.views. Une seule requête
    indexée sur `project`, quel que soit le type d'entité d'origine."""
    return AuditLogEntry.objects.filter(project=project).select_related("actor")


# La logique d'accès à l'historique global scopé (organisation/groupe/soi,
# `get_scoped_audit_log`) vit dans `apps.projects.services`, pas ici —
# `apps/common` ne doit AUCUNE dépendance vers les autres apps (CLAUDE.md),
# et cette logique a besoin de `Team`/`ProjectMembership`/`is_organisation_admin`.
