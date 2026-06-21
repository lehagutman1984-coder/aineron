from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('telegram_bot', '0002_telegramuser_default_video_network'),
        ('aitext', '0009_message_search_context'),
    ]

    operations = [
        migrations.CreateModel(
            name='TelegramEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(
                    choices=[
                        ('message', 'Сообщение'), ('image', 'Изображение'),
                        ('video', 'Видео'), ('payment', 'Оплата'),
                        ('inline', 'Inline-запрос'), ('error', 'Ошибка'),
                        ('onboarding', 'Онбординг'),
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
                ('telegram_user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='events',
                    to='telegram_bot.telegramuser', verbose_name='TG пользователь',
                )),
            ],
            options={
                'verbose_name': 'Событие бота',
                'verbose_name_plural': 'События бота',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='telegramevent',
            index=models.Index(fields=['event_type', 'created_at'], name='tg_event_type_idx'),
        ),
        migrations.AddIndex(
            model_name='telegramevent',
            index=models.Index(fields=['telegram_user', 'created_at'], name='tg_event_user_idx'),
        ),
    ]
