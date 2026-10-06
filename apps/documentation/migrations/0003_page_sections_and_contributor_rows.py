# Généré par Django, complété à la main (session du 2026-10-06) : les
# incidents résolus remontent désormais directement en fiche brouillon (voir
# apps.documentation.services.create_resolution_entry_from_incident), sans
# plus passer par la file "à documenter" — cette étape de données convertit
# les `PendingDocEntry(kind="resolution")` encore en attente au moment de la
# migration, pour ne pas laisser d'incidents déjà résolus sans fiche.

from django.db import migrations, models


def _convert_pending_resolutions(apps, schema_editor):
    # `_default_manager`, pas `.objects` : le modèle historique des
    # migrations ne reconstitue pas les managers custom (`StatusLifecycleModel`
    # définit `objects`/`all_objects` sur le modèle réel, pas sur l'état figé
    # que les migrations connaissent).
    PendingDocEntry = apps.get_model("documentation", "PendingDocEntry")
    DocEntry = apps.get_model("documentation", "DocEntry")
    pending_qs = PendingDocEntry._default_manager.filter(
        status="en_attente", kind="resolution", incident__isnull=False
    )
    for pending in pending_qs:
        incident = pending.incident
        if DocEntry._default_manager.filter(space=pending.space, kind="resolution", source_incident=incident).exists():
            continue
        max_order = (
            DocEntry._default_manager.filter(space=pending.space, kind="resolution")
            .order_by("-order").values_list("order", flat=True).first()
        )
        entry = DocEntry._default_manager.create(
            space=pending.space, kind="resolution", title=incident.title[:200],
            description=(getattr(incident, "resolution_comment", "") or incident.description or ""),
            source="incident", source_incident=incident, status="brouillon",
            order=(max_order or 0) + 1,
        )
        pending.status = "traitee"
        pending.entry = entry
        pending.save(update_fields=["status", "entry", "updated_at"])


def _noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('documentation', '0002_docentry_version_docspace_accent_color_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='docentry',
            name='contributor_rows',
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='docpage',
            name='section',
            field=models.CharField(choices=[('documentation', 'Documentation'), ('support', "Support d'utilisation")], default='documentation', max_length=20),
        ),
        migrations.RunPython(_convert_pending_resolutions, _noop_reverse),
    ]
