from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('telegram_bot', '0003_telegramevent'),
    ]

    operations = [
        # 1. Add is_active field
        migrations.AddField(
            model_name='telegramchat',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Активный'),
        ),
        # 2. Remove the OneToOne constraint by recreating the field as FK
        migrations.AlterField(
            model_name='telegramchat',
            name='tg_user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='telegram_chats',
                to='telegram_bot.telegramuser',
                verbose_name='TG пользователь',
            ),
        ),
        # 3. Add index for active chat lookup
        migrations.AddIndex(
            model_name='telegramchat',
            index=models.Index(fields=['tg_user', 'is_active'], name='tg_chat_active_idx'),
        ),
        # 4. Update verbose names
        migrations.AlterModelOptions(
            name='telegramchat',
            options={
                'verbose_name': 'Чат бота',
                'verbose_name_plural': 'Чаты бота',
            },
        ),
    ]
