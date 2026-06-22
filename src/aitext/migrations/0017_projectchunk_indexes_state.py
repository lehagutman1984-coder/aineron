"""
Sprint 4.1 фикс: регистрируем индексы ProjectChunk в Django state.

Индексы chunk_project_idx и chunk_file_idx уже созданы через raw SQL
в миграции 0015 (SeparateDatabaseAndState.database_operations), но не были
зарегистрированы в state_operations.CreateModel — что вызывало auto-генерацию
"0017 add indexes" при каждом makemigrations и падение migrate на
"relation already exists".

database_operations=[] — ничего не делаем в БД (индексы уже есть).
state_operations=[AddIndex×2] — синхронизируем Django migration state.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0016_connector_sync'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],  # индексы уже созданы в 0015 через RunSQL
            state_operations=[
                migrations.AddIndex(
                    model_name='projectchunk',
                    index=models.Index(fields=['project'], name='chunk_project_idx'),
                ),
                migrations.AddIndex(
                    model_name='projectchunk',
                    index=models.Index(fields=['file'], name='chunk_file_idx'),
                ),
            ],
        ),
    ]
