# Догоняющая миграция: модели поменялись без makemigrations (BILLING_MIGRATION,
# dual-write копейки в TelegramEvent + unique_together вместо именованного
# constraint у TelegramGroupChat) — Django ругался на каждом migrate.
# Написана вручную по manage.py makemigrations telegram_bot --dry-run.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('telegram_bot', '0018_telegramuser_video_settings'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='telegramgroupchat',
            name='unique_group_user_network',
        ),
        migrations.AddField(
            model_name='telegramevent',
            name='cost_kopecks',
            field=models.BigIntegerField(default=0, verbose_name='Стоимость, копейки'),
        ),
        migrations.AlterField(
            model_name='telegramevent',
            name='cost',
            field=models.IntegerField(default=0, verbose_name='Стоимость (зв., legacy)'),
        ),
        migrations.AlterUniqueTogether(
            name='telegramgroupchat',
            unique_together={('group', 'from_user_id', 'network')},
        ),
    ]
