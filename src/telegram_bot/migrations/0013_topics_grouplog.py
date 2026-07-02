from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0001_initial'),
        ('telegram_bot', '0012_business'),
    ]

    operations = [
        migrations.CreateModel(
            name='TelegramTopic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('topic_id', models.IntegerField(verbose_name='message_thread_id топика')),
                ('title', models.CharField(blank=True, max_length=128, verbose_name='Название топика')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('chat', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='telegram_topics', to='aitext.chat', verbose_name='Чат контекста')),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='telegram_topics', to='aitext.project', verbose_name='Проект')),
                ('tg_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='topics', to='telegram_bot.telegramuser', verbose_name='TG пользователь')),
            ],
            options={
                'verbose_name': 'Топик бота',
                'verbose_name_plural': 'Топики бота',
                'unique_together': {('tg_user', 'topic_id')},
            },
        ),
        migrations.CreateModel(
            name='GroupMessageLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('from_name', models.CharField(blank=True, max_length=150, verbose_name='Автор')),
                ('text', models.CharField(max_length=500, verbose_name='Текст (обрезан)')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='message_logs', to='telegram_bot.telegramgroup', verbose_name='Группа')),
            ],
            options={
                'verbose_name': 'Лог сообщения группы',
                'verbose_name_plural': 'Логи сообщений групп',
            },
        ),
        migrations.AddIndex(
            model_name='groupmessagelog',
            index=models.Index(fields=['group', 'created_at'], name='grouplog_idx'),
        ),
    ]
