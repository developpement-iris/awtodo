import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_backfill_organisation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='team',
            name='organisation',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='teams', to='accounts.organisation'),
        ),
        migrations.AlterField(
            model_name='user',
            name='organisation',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='users', to='accounts.organisation'),
        ),
    ]
