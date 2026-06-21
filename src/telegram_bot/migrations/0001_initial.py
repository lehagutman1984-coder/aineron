from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('aitext', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TelegramUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telegram_id', models.BigIntegerField(unique=True, verbose_name='Telegram ID')),
                ('telegram_username', models.CharField(blank=True, max_length=100, verbose_name='Username')),
                ('telegram_first_name', models.CharField(blank=True, max_length=100, verbose_name='Имя')),
                ('linked_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата привязки')),
                ('voice_responses', models.BooleanField(default=False, verbose_name='Голосовые ответы')),
                ('web_search', models.BooleanField(default=False, verbose_name='Веб-поиск')),
                ('system_prompt', models.TextField(blank=True, verbose_name='Системный промт')),
                ('streaming', models.BooleanField(default=True, verbose_name='Streaming (edit_message)')),
                ('last_message_at', models.DateTimeField(blank=True, null=True, verbose_name='Последнее сообщение')),
                ('messages_today', models.PositiveIntegerField(default=0, verbose_name='Сообщений сегодня')),
                ('messages_today_date', models.DateField(blank=True, null=True, verbose_name='Дата счётчика')),
                ('default_network', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='telegram_users_text',
                    to='aitext.neuralnetwork',
                    verbose_name='Текстовая модель по умолчанию',
                )),
                ('default_image_network', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='telegram_users_image',
                    to='aitext.neuralnetwork',
                    verbose_name='Image-модель по умолчанию',
                )),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='telegram',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Пользователь',
                )),
            ],
            options={
                'verbose_name': 'Telegram пользователь',
                'verbose_name_plural': 'Telegram пользователи',
            },
        ),
        migrations.CreateModel(
            name='TelegramChat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chat', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='aitext.chat',
                    verbose_name='Чат',
                )),
                ('tg_user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='active_chat',
                    to='telegram_bot.telegramuser',
                    verbose_name='TG пользователь',
                )),
            ],
            options={
                'verbose_name': 'Активный чат бота',
                'verbose_name_plural': 'Активные чаты бота',
            },
        ),
        migrations.CreateModel(
            name='TelegramLinkToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=64, unique=True, verbose_name='Токен')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(verbose_name='Истекает')),
                ('used', models.BooleanField(default=False, verbose_name='Использован')),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='telegram_link_tokens',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Пользователь',
                )),
            ],
            options={
                'verbose_name': 'Токен привязки Telegram',
                'verbose_name_plural': 'Токены привязки Telegram',
            },
        ),
    ]
