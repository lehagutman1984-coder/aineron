from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0021_pr_proposals'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='public_views',
            field=models.PositiveIntegerField(default=0, verbose_name='Просмотры публичного Space'),
        ),
        migrations.CreateModel(
            name='ProjectAuditEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(
                    choices=[
                        ('chat_message', 'Сообщение в чате'),
                        ('file_upload', 'Загрузка файла'),
                        ('file_delete', 'Удаление файла'),
                        ('commit_push', 'Коммит в репозиторий'),
                        ('pr_open', 'Открытие Pull Request'),
                        ('member_invite', 'Приглашение участника'),
                        ('member_remove', 'Удаление участника'),
                        ('published', 'Публикация Space'),
                        ('unpublished', 'Снятие с публикации'),
                    ],
                    max_length=20, verbose_name='Действие',
                )),
                ('target', models.CharField(blank=True, max_length=500, verbose_name='Объект')),
                ('files_used', models.JSONField(blank=True, default=list, verbose_name='Файлы базы знаний в контексте')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='project_audit_entries',
                    to=settings.AUTH_USER_MODEL, verbose_name='Участник',
                )),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='audit_entries',
                    to='aitext.project', verbose_name='Проект',
                )),
            ],
            options={
                'verbose_name': 'Запись аудита',
                'verbose_name_plural': 'Журнал аудита',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='projectauditentry',
            index=models.Index(fields=['project', '-created_at'], name='aitext_proj_project_audit_idx'),
        ),
    ]
