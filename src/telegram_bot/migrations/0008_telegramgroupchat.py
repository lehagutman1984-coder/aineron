from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('telegram_bot', '0007_telegramgroup'),
        ('aitext', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TelegramGroupChat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('from_user_id', models.BigIntegerField(verbose_name='Telegram ID участника')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('group', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='group_chats',
                    to='telegram_bot.telegramgroup',
                    verbose_name='Telegram-группа',
                )),
                ('network', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='aitext.neuralnetwork',
                    verbose_name='Модель',
                )),
                ('chat', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='telegram_group_chats',
                    to='aitext.chat',
                    verbose_name='Чат',
                )),
            ],
            options={
                'verbose_name': 'Чат группы (участник)',
                'verbose_name_plural': 'Чаты группы (участники)',
            },
        ),
        migrations.AddConstraint(
            model_name='telegramgroupchat',
            constraint=models.UniqueConstraint(
                fields=['group', 'from_user_id', 'network'],
                name='unique_group_user_network',
            ),
        ),
        migrations.AddIndex(
            model_name='telegramgroupchat',
            index=models.Index(fields=['group', 'from_user_id'], name='tg_grpchat_user_idx'),
        ),
    ]
