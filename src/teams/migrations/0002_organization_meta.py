from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='meta',
            field=models.JSONField(blank=True, default=dict, verbose_name='Мета-данные (токены, настройки)'),
        ),
    ]
