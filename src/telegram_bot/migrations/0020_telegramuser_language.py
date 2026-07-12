# Локаль бота (G4, GLOBAL_EXPANSION_PLAN.md §4.6). Написана вручную по
# образцу 0019 — makemigrations на проде недоступен.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('telegram_bot', '0019_telegramevent_cost_kopecks_groupchat_unique_together'),
    ]

    operations = [
        migrations.AddField(
            model_name='telegramuser',
            name='language',
            field=models.CharField(blank=True, max_length=8, verbose_name='Язык бота'),
        ),
    ]
