from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('aitext', '0026_message_fts_index'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UsageEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('channel', models.CharField(
                    choices=[('web', 'Веб'), ('bot', 'Telegram-бот'), ('api', 'API')],
                    default='web', max_length=10, verbose_name='Канал',
                )),
                ('event_type', models.CharField(
                    choices=[
                        ('message', 'Сообщение (текст)'), ('image', 'Генерация изображения'),
                        ('video', 'Генерация видео'), ('payment', 'Оплата'),
                        ('inline', 'Inline-запрос'), ('search', 'Веб-поиск'),
                        ('voice', 'Голос (ASR/TTS)'), ('export', 'Экспорт чата'),
                        ('img2img', 'Image-to-Image'), ('error', 'Ошибка'), ('onboarding', 'Онбординг'),
                    ],
                    max_length=20, verbose_name='Тип события',
                )),
                ('cost', models.IntegerField(default=0, verbose_name='Стоимость (зв.)')),
                ('meta', models.JSONField(blank=True, default=dict, verbose_name='Доп. данные')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Время')),
                ('network', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='aitext.neuralnetwork', verbose_name='Модель',
                )),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='usage_events',
                    to=settings.AUTH_USER_MODEL, verbose_name='Пользователь',
                )),
            ],
            options={
                'verbose_name': 'Событие использования',
                'verbose_name_plural': 'События использования',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='usageevent',
            index=models.Index(
                fields=['channel', 'event_type', 'created_at'],
                name='usage_event_channel_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='usageevent',
            index=models.Index(
                fields=['user', 'created_at'],
                name='usage_event_user_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='usageevent',
            index=models.Index(
                fields=['created_at'],
                name='usage_event_ts_idx',
            ),
        ),
    ]
