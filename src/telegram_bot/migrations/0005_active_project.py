"""Sprint 4.4 — TelegramUser.active_project FK."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('telegram_bot', '0004_telegrmchat_fk_is_active'),
        ('aitext', '0015_pgvector_chunks'),
    ]

    operations = [
        migrations.AddField(
            model_name='telegramuser',
            name='active_project',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='telegram_users',
                to='aitext.project',
                verbose_name='Активный проект',
            ),
        ),
    ]
