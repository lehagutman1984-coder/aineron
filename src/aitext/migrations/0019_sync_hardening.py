from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0018_kb_usage_stat'),
    ]

    operations = [
        # Sprint 5.4: новые поля на ProjectConnector
        migrations.AddField(
            model_name='projectconnector',
            name='auto_sync',
            field=models.BooleanField(default=True, verbose_name='Авто-синхронизация'),
        ),
        migrations.AddField(
            model_name='projectconnector',
            name='sync_status',
            field=models.CharField(
                blank=True, default='', max_length=10,
                choices=[('ok', 'OK'), ('error', 'Ошибка'), ('running', 'Идёт')],
                verbose_name='Статус последнего синка',
            ),
        ),
        migrations.AddField(
            model_name='projectconnector',
            name='last_sync_report',
            field=models.JSONField(blank=True, default=dict, verbose_name='Отчёт последнего синка'),
        ),
        migrations.AddField(
            model_name='projectconnector',
            name='last_repo_head_sha',
            field=models.CharField(blank=True, max_length=64, verbose_name='Последний HEAD SHA'),
        ),
        # Sprint 5.4: новая модель ProjectFileVersion
        migrations.CreateModel(
            name='ProjectFileVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_snapshot', models.TextField(verbose_name='Содержимое (снапшот)')),
                ('repo_sha', models.CharField(blank=True, max_length=64, verbose_name='Git SHA (для repo-файлов)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('file', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='versions',
                    to='aitext.projectfile',
                    verbose_name='Файл',
                )),
            ],
            options={
                'verbose_name': 'Версия файла',
                'verbose_name_plural': 'Версии файлов',
                'ordering': ['-created_at'],
            },
        ),
    ]
