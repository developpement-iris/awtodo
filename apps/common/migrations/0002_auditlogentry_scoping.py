import django.db.models.deletion
from django.db import migrations, models


def clear_existing_entries(apps, schema_editor):
    """Entrées d'audit de dev antérieures à l'ajout de `organisation` (champ
    obligatoire, pas de moyen fiable de le rétro-résoudre depuis
    `content_object` sur un modèle générique) — données de développement
    sans valeur, jamais déployées, pas les données métier visées par la
    règle "aucune suppression physique" (qui protège les entités métier,
    pas les lignes d'audit techniques elles-mêmes)."""
    AuditLogEntry = apps.get_model("common", "AuditLogEntry")
    AuditLogEntry.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0020_permissionprofile_user_permission_profiles"),
        ("projects", "0001_initial"),
        ("common", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(clear_existing_entries, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="auditlogentry",
            name="actor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="audit_entries",
                to="accounts.user",
            ),
        ),
        migrations.AlterField(
            model_name="auditlogentry",
            name="field_name",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="auditlogentry",
            name="verb",
            field=models.CharField(default="field_changed", max_length=30),
        ),
        migrations.AddField(
            model_name="auditlogentry",
            name="organisation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="audit_entries",
                to="accounts.organisation",
                default=None,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="auditlogentry",
            name="project",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="audit_entries",
                to="projects.project",
            ),
        ),
        migrations.AddField(
            model_name="auditlogentry",
            name="team",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="audit_entries",
                to="accounts.team",
            ),
        ),
        migrations.AddIndex(
            model_name="auditlogentry",
            index=models.Index(fields=["project", "created_at"], name="common_audi_project_6da23a_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlogentry",
            index=models.Index(fields=["team", "created_at"], name="common_audi_team_id_3424c2_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlogentry",
            index=models.Index(fields=["organisation", "created_at"], name="common_audi_organis_530937_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlogentry",
            index=models.Index(fields=["actor", "created_at"], name="common_audi_actor_i_b31395_idx"),
        ),
    ]
