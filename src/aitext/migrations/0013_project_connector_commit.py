from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0012_projectfile'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectConnector',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('connector_type', models.CharField(choices=[('github', 'GitHub'), ('gitea', 'Gitea')], max_length=10, verbose_name='Тип')),
                ('repo_url', models.URLField(verbose_name='URL репозитория')),
                ('owner', models.CharField(max_length=100, verbose_name='Владелец')),
                ('repo', models.CharField(max_length=100, verbose_name='Репозиторий')),
                ('branch', models.CharField(default='main', max_length=100, verbose_name='Ветка')),
                ('access_token_enc', models.TextField(verbose_name='Токен (зашифрован)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='connectors', to='aitext.project', verbose_name='Проект')),
            ],
            options={
                'verbose_name': 'Git-коннектор',
                'verbose_name_plural': 'Git-коннекторы',
                'unique_together': {('project', 'owner', 'repo')},
            },
        ),
        migrations.CreateModel(
            name='ProjectCommit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('commit_message', models.CharField(max_length=500, verbose_name='Сообщение коммита')),
                ('files', models.JSONField(default=list, verbose_name='Файлы')),
                ('status', models.CharField(choices=[('pending', 'Ожидает'), ('pushed', 'Запушен'), ('rejected', 'Отклонён'), ('failed', 'Ошибка')], default='pending', max_length=10, verbose_name='Статус')),
                ('error_message', models.TextField(blank=True, verbose_name='Ошибка')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('pushed_at', models.DateTimeField(blank=True, null=True, verbose_name='Дата пуша')),
                ('connector', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='commits', to='aitext.projectconnector', verbose_name='Коннектор')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='commits', to='aitext.project', verbose_name='Проект')),
            ],
            options={
                'verbose_name': 'Коммит проекта',
                'verbose_name_plural': 'Коммиты проекта',
                'ordering': ['-created_at'],
            },
        ),
    ]
