from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0006_project_settings_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='studioproject',
            name='forked_from',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='forks',
                to='studio.studioproject',
            ),
        ),
    ]
