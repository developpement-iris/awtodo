import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0006_backfill_organisation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='organisation',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='projects', to='accounts.organisation'),
        ),
    ]
