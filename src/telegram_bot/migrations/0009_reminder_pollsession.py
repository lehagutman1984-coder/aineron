from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('telegram_bot', '0008_telegramgroupchat'),
    ]

    operations = [
        migrations.CreateModel(
            name='Reminder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField(verbose_name='Текст напоминания')),
                ('remind_at', models.DateTimeField(verbose_name='Когда напомнить (UTC)')),
                ('is_sent', models.BooleanField(default=False, verbose_name='Отправлено')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tg_user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reminders',
                    to='telegram_bot.telegramuser',
                    verbose_name='TG пользователь',
                )),
            ],
            options={
                'verbose_name': 'Напоминание',
                'verbose_name_plural': 'Напоминания',
                'ordering': ['remind_at'],
            },
        ),
        migrations.AddIndex(
            model_name='reminder',
            index=models.Index(fields=['is_sent', 'remind_at'], name='reminder_unsent_idx'),
        ),
        migrations.CreateModel(
            name='PollSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question', models.TextField(verbose_name='Вопрос')),
                ('options', models.JSONField(default=list, verbose_name='Варианты ответа')),
                ('vote_counts', models.JSONField(default=list, verbose_name='Голоса по вариантам')),
                ('status', models.CharField(
                    choices=[('active', 'Активный'), ('closed', 'Закрыт')],
                    default='active',
                    max_length=10,
                )),
                ('ai_summary', models.TextField(blank=True, verbose_name='AI-анализ результатов')),
                ('telegram_poll_id', models.CharField(blank=True, max_length=100, verbose_name='ID опроса в TG')),
                ('chat_id', models.BigIntegerField(verbose_name='Chat ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tg_user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='poll_sessions',
                    to='telegram_bot.telegramuser',
                    verbose_name='Создатель опроса',
                )),
            ],
            options={
                'verbose_name': 'AI-опрос',
                'verbose_name_plural': 'AI-опросы',
                'ordering': ['-created_at'],
            },
        ),
    ]
