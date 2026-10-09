"""Crée les 4 types historiques (mêmes clés que les anciennes `choices`) pour
chaque groupe et chaque projet sans groupe existants — les tâches déjà en
base gardent leur `task_type` tel quel, il est simplement résolu."""

from django.db import migrations

DEFAULTS = [
    ("correction", "Correction", "wrench"),
    ("ajout", "Ajout", "circle_plus"),
    ("evolution", "Évolution", "trending_up"),
    ("test", "Test", "flask"),
]


def seed(apps, schema_editor):
    TaskType = apps.get_model("tasks", "TaskType")
    Team = apps.get_model("accounts", "Team")
    Project = apps.get_model("projects", "Project")

    def create_for(**scope):
        if TaskType._default_manager.filter(**scope).exists():
            return
        TaskType._default_manager.bulk_create(
            TaskType(key=key, label=label, icon=icon, position=index, **scope)
            for index, (key, label, icon) in enumerate(DEFAULTS)
        )

    for team in Team._default_manager.all():
        create_for(team=team)
    for project in Project._default_manager.filter(team__isnull=True):
        create_for(project=project)


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0010_task_type_customisable"),
    ]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
