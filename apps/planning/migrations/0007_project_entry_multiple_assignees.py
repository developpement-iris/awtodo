# Session du 2026-10-05 — plusieurs assignés possibles sur une entrée de
# planning projet (M2M) + synchro Outlook par assigné. Réordonné par rapport
# à l'autogénération : `assignees` ajouté AVANT que `assignee` disparaisse,
# avec une étape de migration de données entre les deux pour ne pas perdre
# l'assignation déjà existante sur les entrées en base.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


def _copy_assignee_to_assignees(apps, schema_editor):
    # `_default_manager`, pas `.objects` : le modèle historique des
    # migrations ne reconstitue pas les managers custom (`StatusLifecycleModel`
    # définit `objects`/`all_objects` sur le modèle réel, pas sur l'état figé
    # que les migrations connaissent) — seul `_default_manager` est garanti
    # présent ici.
    ProjectPlanningEntry = apps.get_model("planning", "ProjectPlanningEntry")
    for entry in ProjectPlanningEntry._default_manager.exclude(assignee__isnull=True):
        entry.assignees.add(entry.assignee_id)


def _noop_reverse(apps, schema_editor):
    # Pas de retour en arrière possible sans perte d'information si une
    # entrée a fini avec plusieurs assignés — assumé, cohérent avec le reste
    # du projet (migrations de données non réversibles déjà en place, ex.
    # common.0002_auditlogentry_scoping).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('planning', '0006_calendareventoccurrenceoverride_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='projectplanningentry',
            name='assignees',
            field=models.ManyToManyField(blank=True, related_name='project_planning_entries', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(_copy_assignee_to_assignees, _noop_reverse),
        migrations.RemoveField(
            model_name='projectplanningentry',
            name='assignee',
        ),
        migrations.CreateModel(
            name='ProjectPlanningEntryOutlookSync',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('outlook_event_id', models.CharField(blank=True, default='', max_length=200)),
                ('entry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignee_outlook_syncs', to='planning.projectplanningentry')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('entry', 'user'), name='projectplanningentryoutlooksync_unique_entry_user')],
            },
        ),
    ]
