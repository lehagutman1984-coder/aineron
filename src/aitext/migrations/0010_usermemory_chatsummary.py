from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0009_message_search_context'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserMemory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(
                    choices=[
                        ('profile', 'Профиль'), ('preference', 'Предпочтения'),
                        ('project', 'Проекты'), ('fact', 'Факты'), ('skill', 'Навыки'),
                    ],
                    default='fact', max_length=20, verbose_name='Категория',
                )),
                ('content', models.TextField(verbose_name='Факт')),
                ('content_key', models.CharField(
                    blank=True, db_index=True, max_length=255,
                    verbose_name='Ключ дедупликации',
                )),
                ('source', models.CharField(
                    choices=[('auto', 'Авто'), ('user', 'Вручную')],
                    default='auto', max_length=10, verbose_name='Источник',
                )),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('is_pinned', models.BooleanField(default=False, verbose_name='Закреплён')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='memories',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Пользователь',
                )),
                ('source_chat', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='extracted_memories',
                    to='aitext.chat',
                )),
            ],
            options={
                'verbose_name': 'Факт о пользователе',
                'verbose_name_plural': 'Факты о пользователях',
                'ordering': ['-is_pinned', '-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='usermemory',
            constraint=models.UniqueConstraint(
                condition=models.Q(content_key__gt=''),
                fields=['user', 'content_key'],
                name='unique_user_memory_content_key',
            ),
        ),
        migrations.CreateModel(
            name='ChatSummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('summary_text', models.TextField(verbose_name='Резюме сессии')),
                ('rolling_summary', models.TextField(
                    blank=True, default='',
                    verbose_name='Сжатое начало текущей сессии',
                )),
                ('message_count', models.PositiveIntegerField(default=0, verbose_name='Кол-во сообщений')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chat', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='summary',
                    to='aitext.chat',
                    verbose_name='Чат',
                )),
            ],
            options={
                'verbose_name': 'Резюме чата',
                'verbose_name_plural': 'Резюме чатов',
            },
        ),
    ]
