from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
        ('teams', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='apikey',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='api_keys',
                to='teams.organization',
                verbose_name='Организация',
            ),
        ),
        migrations.AddField(
            model_name='tokenusage',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='token_usages',
                to='teams.organization',
                verbose_name='Организация',
            ),
        ),
    ]
