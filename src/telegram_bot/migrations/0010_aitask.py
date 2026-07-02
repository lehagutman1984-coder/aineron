from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('aitext', '0001_initial'),
        ('telegram_bot', '0009_reminder_pollsession'),
    ]

    operations = [
        migrations.AlterField(
            model_name='telegramevent',
            name='event_type',
            field=models.CharField(choices=[
                ('message', 'Сообщение'), ('image', 'Изображение'), ('video', 'Видео'),
                ('payment', 'Оплата'), ('inline', 'Inline-запрос'), ('error', 'Ошибка'),
                ('onboarding', 'Онбординг'), ('task_run', 'AI-задача (запуск)'),
                ('research', 'Deep Research'), ('business_reply', 'AI-секретарь (ответ)'),
                ('subscription', 'Stars-подписка'), ('affiliate_join', 'Партнёрская регистрация'),
            ], max_length=20, verbose_name='Тип события'),
        ),
        migrations.CreateModel(
            name='AITask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, max_length=120, verbose_name='Название')),
                ('prompt', models.TextField(verbose_name='Промт задачи')),
                ('schedule_type', models.CharField(choices=[('once', 'Один раз'), ('daily', 'Ежедневно'), ('weekly', 'Еженедельно'), ('cron', 'Cron-выражение')], default='daily', max_length=10, verbose_name='Тип расписания')),
                ('run_time', models.TimeField(blank=True, null=True, verbose_name='Время запуска (МСК)')),
                ('weekday', models.SmallIntegerField(blank=True, null=True, verbose_name='День недели (0=пн, для weekly)')),
                ('cron', models.CharField(blank=True, max_length=120, verbose_name='Cron-выражение (5 полей)')),
                ('next_run_at', models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='Следующий запуск (UTC)')),
                ('use_web_search', models.BooleanField(default=True, verbose_name='Веб-поиск (Tavily)')),
                ('deliver_chat_id', models.BigIntegerField(blank=True, null=True, verbose_name='Чат доставки (пусто = личка пользователя)')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активна')),
                ('paused_reason', models.CharField(blank=True, default='', max_length=20, verbose_name='Причина паузы (balance/user/max_runs)')),
                ('last_run_at', models.DateTimeField(blank=True, null=True, verbose_name='Последний запуск')),
                ('runs_count', models.PositiveIntegerField(default=0, verbose_name='Запусков всего')),
                ('max_runs', models.PositiveIntegerField(blank=True, null=True, verbose_name='Максимум запусков (пусто = без лимита)')),
                ('created_from', models.CharField(choices=[('bot', 'Telegram-бот'), ('web', 'Веб')], default='bot', max_length=10, verbose_name='Создана из')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('network', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ai_tasks', to='aitext.neuralnetwork', verbose_name='Модель (пусто = самая дешёвая текстовая)')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_tasks', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'AI-задача',
                'verbose_name_plural': 'AI-задачи',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='aitask',
            index=models.Index(fields=['is_active', 'next_run_at'], name='aitask_due_idx'),
        ),
        migrations.AddIndex(
            model_name='aitask',
            index=models.Index(fields=['user', 'is_active'], name='aitask_user_idx'),
        ),
    ]
