from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0001_initial'),
        ('telegram_bot', '0013_topics_grouplog'),
    ]

    operations = [
        migrations.CreateModel(
            name='ManagedBot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bot_username', models.CharField(blank=True, max_length=100, verbose_name='Username бота')),
                ('token', models.CharField(max_length=100, verbose_name='Токен бота')),
                ('name', models.CharField(max_length=100, verbose_name='Имя агента')),
                ('greeting', models.TextField(blank=True, default='Привет! Я AI-ассистент. Задайте вопрос.', verbose_name='Приветствие (/start)')),
                ('system_prompt', models.TextField(blank=True, verbose_name='Персона / системный промт')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('messages_count', models.PositiveIntegerField(default=0, verbose_name='Сообщений гостей')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('network', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='managed_bots', to='aitext.neuralnetwork', verbose_name='Модель (пусто = самая дешёвая)')),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='managed_bots', to='aitext.project', verbose_name='Проект (база знаний RAG)')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='managed_bots', to='telegram_bot.telegramuser', verbose_name='Владелец')),
            ],
            options={
                'verbose_name': 'Персональный бот',
                'verbose_name_plural': 'Персональные боты',
            },
        ),
    ]
