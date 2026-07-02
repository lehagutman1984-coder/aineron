from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('telegram_bot', '0011_starssubscription'),
    ]

    operations = [
        migrations.CreateModel(
            name='BusinessConnection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('connection_id', models.CharField(max_length=128, unique=True, verbose_name='business_connection_id')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='Подключение активно')),
                ('secretary_on', models.BooleanField(default=True, verbose_name='Секретарь включён')),
                ('mode', models.CharField(choices=[('drafts', 'Черновики (подтверждение владельцем)'), ('autopilot', 'Автопилот (типовые вопросы)')], default='drafts', max_length=10, verbose_name='Режим')),
                ('scope_all', models.BooleanField(default=True, verbose_name='Работать во всех чатах')),
                ('allowed_chat_ids', models.JSONField(blank=True, default=list, verbose_name='Белый список чатов')),
                ('tone', models.TextField(blank=True, verbose_name='Тон ответов (инструкция AI)')),
                ('stop_word', models.CharField(default='оператор', max_length=50, verbose_name='Стоп-слово клиента (передать человеку)')),
                ('can_reply', models.BooleanField(default=False, verbose_name='Право отвечать (rights)')),
                ('replies_month', models.CharField(blank=True, default='', max_length=7, verbose_name='Месяц счётчика (YYYY-MM)')),
                ('replies_this_month', models.PositiveIntegerField(default=0, verbose_name='Ответов за месяц')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tg_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='business_connections', to='telegram_bot.telegramuser', verbose_name='Владелец (TG пользователь)')),
            ],
            options={
                'verbose_name': 'Business-подключение',
                'verbose_name_plural': 'Business-подключения',
            },
        ),
        migrations.CreateModel(
            name='BusinessDraft',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('client_chat_id', models.BigIntegerField(verbose_name='Чат клиента')),
                ('client_name', models.CharField(blank=True, max_length=150, verbose_name='Имя клиента')),
                ('incoming_text', models.TextField(verbose_name='Сообщение клиента')),
                ('draft_text', models.TextField(blank=True, verbose_name='Черновик ответа')),
                ('status', models.CharField(choices=[('pending', 'Ждёт решения'), ('sent', 'Отправлен'), ('ignored', 'Игнор'), ('auto', 'Автоответ')], default='pending', max_length=10, verbose_name='Статус')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('connection', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='drafts', to='telegram_bot.businessconnection', verbose_name='Подключение')),
            ],
            options={
                'verbose_name': 'Черновик секретаря',
                'verbose_name_plural': 'Черновики секретаря',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='businessdraft',
            index=models.Index(fields=['connection', 'status'], name='bizdraft_conn_idx'),
        ),
    ]
