from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0011_migrate_coder_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='studioproject',
            name='agent_models',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
