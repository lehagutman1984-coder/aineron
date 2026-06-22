from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0023_file_summary'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectconnector',
            name='deploy_webhook_url',
            field=models.CharField(blank=True, max_length=500, verbose_name='URL deploy-вебхука'),
        ),
        migrations.AddField(
            model_name='projectconnector',
            name='deploy_secret_enc',
            field=models.TextField(blank=True, verbose_name='Deploy secret (зашифрован Fernet)'),
        ),
        migrations.AddField(
            model_name='projectconnector',
            name='deploy_status',
            field=models.CharField(
                blank=True, default='', max_length=10,
                choices=[('', '—'), ('pending', 'Ожидает'), ('running', 'В процессе'),
                         ('success', 'Успешно'), ('error', 'Ошибка')],
                verbose_name='Статус деплоя',
            ),
        ),
        migrations.AddField(
            model_name='projectconnector',
            name='last_deploy_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Последний деплой'),
        ),
        migrations.AddField(
            model_name='projectconnector',
            name='last_deploy_log',
            field=models.TextField(blank=True, verbose_name='Лог последнего деплоя'),
        ),
    ]
