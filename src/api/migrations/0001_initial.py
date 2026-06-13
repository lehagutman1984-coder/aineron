from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('aitext', '0004_neuralnetwork_stars_per_1k_tokens'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='APIKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Название ключа')),
                ('key_prefix', models.CharField(db_index=True, max_length=8, verbose_name='Префикс (для отображения)')),
                ('hashed_key', models.CharField(max_length=64, unique=True, verbose_name='Хеш ключа')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('last_used_at', models.DateTimeField(blank=True, null=True, verbose_name='Последнее использование')),
                ('scopes', models.JSONField(blank=True, default=list, verbose_name='Разрешения')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='api_keys', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'API-ключ',
                'verbose_name_plural': 'API-ключи',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TokenUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prompt_tokens', models.PositiveIntegerField(default=0, verbose_name='Токены запроса')),
                ('completion_tokens', models.PositiveIntegerField(default=0, verbose_name='Токены ответа')),
                ('total_tokens', models.PositiveIntegerField(default=0, verbose_name='Всего токенов')),
                ('stars_charged', models.PositiveIntegerField(default=0, verbose_name='Списано звёзд')),
                ('request_id', models.CharField(blank=True, max_length=64, verbose_name='ID запроса')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Время запроса')),
                ('api_key', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='token_usages', to='api.apikey', verbose_name='API-ключ')),
                ('network', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='token_usages', to='aitext.neuralnetwork', verbose_name='Нейросеть')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='token_usages', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Использование токенов',
                'verbose_name_plural': 'Использование токенов',
                'ordering': ['-created_at'],
            },
        ),
    ]
