from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('telegram_bot', '0017_agent_business_project'),
    ]

    operations = [
        migrations.AddField(
            model_name='telegramuser',
            name='video_settings',
            field=models.JSONField(blank=True, default=dict, verbose_name='Настройки видео'),
        ),
    ]
