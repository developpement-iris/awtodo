from django.db import migrations


def rename_archive_to_cloture(apps, schema_editor):
    # Défensif : `archive` n'a jamais été construit côté UI (voir
    # docs/modeles-et-api.md > Project), donc aucune ligne réelle n'est
    # attendue ici — mais si une ligne de test/seed l'utilisait, elle doit
    # suivre le renommage plutôt que de rester sur une valeur hors `choices`.
    Project = apps.get_model("projects", "Project")
    Project._base_manager.filter(status="archive").update(status="cloture")


def reverse(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    Project._base_manager.filter(status="cloture").update(status="archive")


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0009_alter_project_status_projectversion"),
    ]

    operations = [
        migrations.RunPython(rename_archive_to_cloture, reverse),
    ]
