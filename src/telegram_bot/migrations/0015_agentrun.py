from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('telegram_bot', '0014_managedbot'),
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
                ('agent', 'Agent Mode (запуск)'),
            ], max_length=20, verbose_name='Тип события'),
        ),
        migrations.CreateModel(
            name='AgentRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('goal', models.TextField(verbose_name='Задача')),
                ('status', models.CharField(choices=[('pending', 'Ожидает'), ('running', 'Выполняется'), ('done', 'Готово'), ('error', 'Ошибка')], default='pending', max_length=10, verbose_name='Статус')),
                ('steps', models.JSONField(blank=True, default=list, verbose_name='Шаги выполнения')),
                ('result_md', models.TextField(blank=True, verbose_name='Итоговый отчёт (markdown)')),
                ('error', models.TextField(blank=True, verbose_name='Ошибка')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='agent_runs', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Agent Mode запуск',
                'verbose_name_plural': 'Agent Mode запуски',
                'ordering': ['-created_at'],
            },
        ),
    ]
