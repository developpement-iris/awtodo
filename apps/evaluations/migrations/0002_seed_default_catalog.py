from django.db import migrations


def seed(apps, schema_editor):
    """Catalogue par défaut pour les groupes et projets sans groupe existants
    (les nouveaux sont amorcés par `apps.evaluations.receivers`)."""
    from apps.evaluations.catalog import seed_default_catalog

    CatalogQuestion = apps.get_model("evaluations", "CatalogQuestion")
    Team = apps.get_model("accounts", "Team")
    Project = apps.get_model("projects", "Project")
    for team in Team._default_manager.all():
        seed_default_catalog(team, question_model=CatalogQuestion)
    for project in Project._default_manager.filter(team__isnull=True):
        seed_default_catalog(project, question_model=CatalogQuestion)


class Migration(migrations.Migration):
    dependencies = [("evaluations", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
