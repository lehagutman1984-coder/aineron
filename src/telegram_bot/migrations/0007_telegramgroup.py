from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('telegram_bot', '0006_telegramuser_digest_fields'),
        ('teams', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TelegramGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('group_id', models.BigIntegerField(unique=True, verbose_name='Telegram group/channel ID')),
                ('group_title', models.CharField(blank=True, max_length=255, verbose_name='Название группы')),
                ('enabled', models.BooleanField(default=True, verbose_name='Активна')),
                ('system_prompt', models.TextField(blank=True, verbose_name='Системный промт группы')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата регистрации')),
                ('organization', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='telegram_groups',
                    to='teams.organization',
                    verbose_name='Организация',
                )),
                ('registered_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='registered_groups',
                    to='telegram_bot.telegramuser',
                    verbose_name='Кто зарегистрировал',
                )),
            ],
            options={
                'verbose_name': 'Telegram-группа',
                'verbose_name_plural': 'Telegram-группы',
                'ordering': ['-created_at'],
            },
        ),
    ]
