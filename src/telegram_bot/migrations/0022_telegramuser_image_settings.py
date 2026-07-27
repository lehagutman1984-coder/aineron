from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('telegram_bot', '0021_telegramuser_timezone_offset_minutes'),
    ]

    operations = [
        migrations.AddField(
            model_name='telegramuser',
            name='image_settings',
            field=models.JSONField(blank=True, default=dict, verbose_name='Настройки изображений'),
        ),
    ]
