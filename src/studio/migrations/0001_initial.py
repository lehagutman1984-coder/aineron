import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StudioProject',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(
                    choices=[
                        ('draft', 'Черновик'), ('interview', 'Интервью'),
                        ('planning', 'Планирование'), ('ready', 'Готов к кодингу'),
                        ('coding', 'Кодинг'), ('paused', 'Пауза'),
                        ('completed', 'Завершён'), ('failed', 'Ошибка'),
                    ],
                    default='draft', max_length=20,
                )),
                ('mode', models.CharField(
                    choices=[('auto', 'Авто'), ('semi', 'Полу-авто'), ('manual', 'Ручной')],
                    default='auto', max_length=10,
                )),
                ('entry_mode', models.CharField(
                    choices=[('description', 'С нуля'), ('clone_url', 'Клон по URL')],
                    default='description', max_length=20,
                )),
                ('target_url', models.URLField(blank=True)),
                ('target_stack', models.CharField(
                    choices=[
                        ('nextjs', 'Next.js'), ('react', 'React'),
                        ('vue', 'Vue'), ('html', 'HTML'),
                    ],
                    default='nextjs', max_length=10,
                )),
                ('interview_data', models.JSONField(blank=True, default=dict)),
                ('project_md_content', models.TextField(blank=True)),
                ('commits_md_content', models.TextField(blank=True)),
                ('sandbox_container_id', models.CharField(blank=True, max_length=128)),
                ('preview_port', models.IntegerField(blank=True, null=True)),
                ('repo_url', models.URLField(blank=True)),
                ('stars_reserved', models.IntegerField(default=0)),
                ('stars_spent', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='studio_projects',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='StudioFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('path', models.CharField(max_length=512)),
                ('content', models.TextField(blank=True)),
                ('language', models.CharField(blank=True, max_length=40)),
                ('last_modified_by', models.CharField(default='agent', max_length=40)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='files',
                    to='studio.studioproject',
                )),
            ],
            options={'ordering': ['path'], 'unique_together': {('project', 'path')}},
        ),
        migrations.CreateModel(
            name='StudioPipelineState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[
                        ('idle', 'idle'), ('running', 'running'),
                        ('paused_on_loop', 'paused_on_loop'), ('paused_manual', 'paused_manual'),
                        ('completed', 'completed'), ('failed', 'failed'),
                    ],
                    default='idle', max_length=20,
                )),
                ('step_index', models.IntegerField(default=0)),
                ('iteration_count', models.IntegerField(default=0)),
                ('review_report', models.JSONField(blank=True, default=dict)),
                ('test_report', models.JSONField(blank=True, default=dict)),
                ('fix_plan', models.JSONField(blank=True, default=dict)),
                ('last_error', models.TextField(blank=True)),
                ('pause_reason', models.TextField(blank=True)),
                ('resume_hint', models.TextField(blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('project', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pipeline',
                    to='studio.studioproject',
                )),
            ],
        ),
        migrations.CreateModel(
            name='StudioVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('git_sha', models.CharField(blank=True, max_length=64)),
                ('step_index', models.IntegerField(default=0)),
                ('step_name', models.CharField(blank=True, max_length=200)),
                ('stars_spent_at_version', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='versions',
                    to='studio.studioproject',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
