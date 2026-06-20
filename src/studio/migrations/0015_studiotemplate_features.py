from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0014_v4_autofix_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='studiotemplate',
            name='features',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
