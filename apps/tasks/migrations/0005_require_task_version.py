import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    # Dernière étape du pattern "safe 3-step" (voir CLAUDE.md) : le champ a
    # été ajouté nullable (0003), backfillé (0004), et devient ici requis —
    # écrit à la main plutôt que via `makemigrations` (le prompt interactif
    # "provide a default" ne fonctionne pas en exécution non-interactive).

    dependencies = [
        ("tasks", "0004_backfill_project_versions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="task",
            name="version",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="tasks", to="projects.projectversion"
            ),
        ),
    ]
