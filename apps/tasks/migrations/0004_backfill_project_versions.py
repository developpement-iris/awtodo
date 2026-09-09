from django.db import migrations


def backfill_versions(apps, schema_editor):
    # Voir docs/modeles-et-api.md > "ProjectVersion" : chaque Project existant
    # reçoit une version initiale "v1" marquée courante, et toutes ses Task
    # existantes y sont rattachées rétroactivement. `_base_manager` (pas
    # `objects`) : les managers personnalisés ne sont pas garantis sur les
    # modèles historiques reconstruits par les migrations.
    Project = apps.get_model("projects", "Project")
    ProjectVersion = apps.get_model("projects", "ProjectVersion")
    Task = apps.get_model("tasks", "Task")

    for project in Project._base_manager.all():
        version = ProjectVersion._base_manager.create(project=project, label="v1", is_current=True, created_by=None)
        Task._base_manager.filter(project=project).update(version=version)


def reverse(apps, schema_editor):
    # Pas de suppression de version (règle transverse "aucune suppression
    # physique") — la réversion se contente de détacher les tâches, la
    # version "v1" créée par cette migration reste en base.
    Task = apps.get_model("tasks", "Task")
    Task._base_manager.update(version=None)


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0003_task_version"),
        ("projects", "0010_rename_archive_to_cloture"),
    ]

    operations = [
        migrations.RunPython(backfill_versions, reverse),
    ]
