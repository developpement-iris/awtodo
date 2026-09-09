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


@contextmanager
def record_changes(instance, *, actor):
    """Capture l'état de chaque champ de `instance` avant le bloc, puis
    journalise dans `AuditLogEntry` tout champ qui a changé après le bloc
    (typiquement une mutation suivie d'un `.save()`). Usage :

        with record_changes(task, actor=actor):
            task.status = "en_cours"
            task.save()

    Comparaison sur `field.attname` (ex. `assignee_id`), pas `field.name` :
    évite de déclencher une requête pour résoudre l'objet lié juste pour le
    comparer — seul l'identifiant compte pour détecter un changement."""
    fields = [f for f in instance._meta.fields if f.attname not in EXCLUDED_FIELDS]
    before = {f.attname: getattr(instance, f.attname) for f in fields}

    yield

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
            field_name=field.name,
            old_value=_display_value(field, old_raw),
            new_value=_display_value(field, new_raw),
        )


def get_audit_log(instance):
    content_type = ContentType.objects.get_for_model(type(instance))
    return AuditLogEntry.objects.filter(content_type=content_type, object_id=instance.id).select_related("actor")
