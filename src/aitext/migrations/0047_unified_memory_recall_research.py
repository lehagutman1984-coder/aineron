"""UNIFIED_SUPREMACY U1–U3 (aitext-часть).

U1: UserMemory.project / UserMemory.organization — скоуп памяти (nullable,
    прежнее поведение не меняется) + индексы.
U2: ChatSummary.embedding — raw vector(1536)-колонка (как ProjectChunk:
    без Django-поля, чтобы SQLite-тесты работали; запросы через cursor).
U3: Project.auto_save_research, DeepResearch.saved_file.
"""
from django.db import migrations, models
import django.db.models.deletion


def _add_summary_embedding(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(
            'ALTER TABLE aitext_chatsummary '
            'ADD COLUMN IF NOT EXISTS embedding vector(1536);'
        )
    else:
        # SQLite (локальные тесты): колонка-заглушка, векторные запросы не идут
        try:
            schema_editor.execute(
                'ALTER TABLE aitext_chatsummary ADD COLUMN embedding blob;'
            )
        except Exception:
            pass  # колонка уже есть


def _drop_summary_embedding(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(
            'ALTER TABLE aitext_chatsummary DROP COLUMN IF EXISTS embedding;'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0001_initial'),
        ('aitext', '0046_backfill_kopecks'),
    ]

    operations = [
        # U1 — скоуп памяти
        migrations.AddField(
            model_name='usermemory',
            name='project',
            field=models.ForeignKey(blank=True, null=True,
                                    on_delete=django.db.models.deletion.CASCADE,
                                    related_name='memories', to='aitext.project',
                                    verbose_name='Проект (скоуп)'),
        ),
        migrations.AddField(
            model_name='usermemory',
            name='organization',
            field=models.ForeignKey(blank=True, null=True,
                                    on_delete=django.db.models.deletion.CASCADE,
                                    related_name='memories', to='teams.organization',
                                    verbose_name='Организация (общая память)'),
        ),
        migrations.AddIndex(
            model_name='usermemory',
            index=models.Index(fields=['user', 'project', 'is_active'],
                               name='usermem_user_proj_idx'),
        ),
        migrations.AddIndex(
            model_name='usermemory',
            index=models.Index(fields=['organization', 'is_active'],
                               name='usermem_org_idx'),
        ),

        # U2 — эмбеддинг резюме чатов (raw SQL, вне Django-state)
        migrations.RunPython(_add_summary_embedding, _drop_summary_embedding),

        # U3 — компаундинг research
        migrations.AddField(
            model_name='project',
            name='auto_save_research',
            field=models.BooleanField(default=False,
                                      verbose_name='Автосохранять research-отчёты в базу знаний'),
        ),
        # U5 — типы коннекторов website/rss
        migrations.AlterField(
            model_name='projectconnector',
            name='connector_type',
            field=models.CharField(choices=[
                ('github', 'GitHub'), ('gitea', 'Gitea'),
                ('website', 'Сайт (краулер)'), ('rss', 'RSS-лента'),
            ], max_length=10, verbose_name='Тип'),
        ),

        # U3/U5 — новые источники файлов базы знаний
        migrations.AlterField(
            model_name='projectfile',
            name='source',
            field=models.CharField(choices=[
                ('upload', 'Загружен'), ('repo', 'Из репозитория'),
                ('research', 'Deep Research'), ('web', 'Сайт (краулер)'),
                ('rss', 'RSS-лента'),
            ], default='upload', max_length=10, verbose_name='Источник'),
        ),
        migrations.AddField(
            model_name='deepresearch',
            name='saved_file',
            field=models.ForeignKey(blank=True, null=True,
                                    on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='research_reports', to='aitext.projectfile',
                                    verbose_name='Сохранён в базу знаний'),
        ),
    ]
