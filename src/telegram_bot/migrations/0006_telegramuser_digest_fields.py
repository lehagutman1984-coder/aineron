from django.db import migrations, models


class Migration(migrations.Migration):
    """Add daily digest settings to TelegramUser."""

    dependencies = [
        ("telegram_bot", "0005_active_project"),
    ]

    operations = [
        migrations.AddField(
            model_name="telegramuser",
            name="digest_enabled",
            field=models.BooleanField(default=False, verbose_name="Дайджест включён"),
        ),
        migrations.AddField(
            model_name="telegramuser",
            name="digest_hour",
            field=models.SmallIntegerField(default=9, verbose_name="Час дайджеста (МСК)"),
        ),
        migrations.AddField(
            model_name="telegramuser",
            name="digest_minute",
            field=models.SmallIntegerField(default=0, verbose_name="Минута дайджеста (МСК)"),
        ),
    ]
