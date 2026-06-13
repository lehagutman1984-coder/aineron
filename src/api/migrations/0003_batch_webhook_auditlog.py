from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_org_fk'),
        ('teams', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # BatchJob
        migrations.CreateModel(
            name='BatchJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.CharField(default='/v1/chat/completions', max_length=100, verbose_name='Эндпоинт')),
                ('completion_window', models.CharField(default='24h', max_length=20, verbose_name='Окно завершения')),
                ('status', models.CharField(choices=[
                    ('validating', 'Валидация'), ('in_progress', 'В обработке'),
                    ('completed', 'Завершён'), ('failed', 'Ошибка'),
                    ('cancelled', 'Отменён'), ('expired', 'Истёк'),
                ], db_index=True, default='validating', max_length=20, verbose_name='Статус')),
                ('request_counts_total', models.PositiveIntegerField(default=0, verbose_name='Всего запросов')),
                ('request_counts_completed', models.PositiveIntegerField(default=0, verbose_name='Выполнено')),
                ('request_counts_failed', models.PositiveIntegerField(default=0, verbose_name='Ошибок')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='Метаданные')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Создан')),
                ('in_progress_at', models.DateTimeField(blank=True, null=True, verbose_name='Начат')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Завершён')),
                ('cancelled_at', models.DateTimeField(blank=True, null=True, verbose_name='Отменён')),
                ('expires_at', models.DateTimeField(blank=True, null=True, verbose_name='Истекает')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='batch_jobs', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
                ('api_key', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='api.apikey', verbose_name='API-ключ')),
                ('organization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='teams.organization', verbose_name='Организация')),
            ],
            options={'verbose_name': 'Пакетное задание', 'verbose_name_plural': 'Пакетные задания', 'ordering': ['-created_at']},
        ),
        # BatchJobItem
        migrations.CreateModel(
            name='BatchJobItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('custom_id', models.CharField(blank=True, max_length=64, verbose_name='ID запроса (custom_id)')),
                ('method', models.CharField(default='POST', max_length=10, verbose_name='HTTP метод')),
                ('url', models.CharField(default='/v1/chat/completions', max_length=200, verbose_name='URL')),
                ('body', models.JSONField(default=dict, verbose_name='Тело запроса')),
                ('status', models.CharField(choices=[
                    ('pending', 'Ожидает'), ('in_progress', 'Обрабатывается'),
                    ('completed', 'Выполнен'), ('failed', 'Ошибка'),
                ], db_index=True, default='pending', max_length=20, verbose_name='Статус')),
                ('response_body', models.JSONField(blank=True, null=True, verbose_name='Ответ')),
                ('error_message', models.TextField(blank=True, verbose_name='Сообщение об ошибке')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Завершён')),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='api.batchjob', verbose_name='Задание')),
            ],
            options={'verbose_name': 'Запрос в пакете', 'verbose_name_plural': 'Запросы в пакете', 'ordering': ['created_at']},
        ),
        # Webhook
        migrations.CreateModel(
            name='Webhook',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.URLField(verbose_name='URL')),
                ('events', models.JSONField(default=list, verbose_name='События')),
                ('secret', models.CharField(editable=False, max_length=64, verbose_name='Секрет подписи')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('last_triggered_at', models.DateTimeField(blank=True, null=True, verbose_name='Последний вызов')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='webhooks', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
                ('organization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='teams.organization', verbose_name='Организация')),
            ],
            options={'verbose_name': 'Webhook', 'verbose_name_plural': 'Webhooks', 'ordering': ['-created_at']},
        ),
        # AuditLog
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[
                    ('key.created', 'Ключ создан'), ('key.deleted', 'Ключ удалён'),
                    ('org.created', 'Организация создана'), ('org.updated', 'Организация обновлена'),
                    ('member.added', 'Участник добавлен'), ('member.removed', 'Участник удалён'),
                    ('invite.sent', 'Приглашение отправлено'),
                    ('webhook.created', 'Webhook создан'), ('webhook.deleted', 'Webhook удалён'),
                    ('batch.created', 'Пакет создан'), ('batch.cancelled', 'Пакет отменён'),
                ], db_index=True, max_length=50, verbose_name='Действие')),
                ('resource_type', models.CharField(blank=True, max_length=50, verbose_name='Тип ресурса')),
                ('resource_id', models.CharField(blank=True, max_length=64, verbose_name='ID ресурса')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='Детали')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP-адрес')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Время')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
                ('organization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to='teams.organization', verbose_name='Организация')),
            ],
            options={'verbose_name': 'Запись аудита', 'verbose_name_plural': 'Журнал аудита', 'ordering': ['-created_at']},
        ),
    ]
