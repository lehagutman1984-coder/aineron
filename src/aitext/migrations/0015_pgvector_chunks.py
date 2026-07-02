"""
Sprint 4.1 — Vector RAG.

Требования:
  1. PostgreSQL с pgvector (образ pgvector/pgvector:pg15 в docker-compose).
  2. Первая операция — CREATE EXTENSION IF NOT EXISTS vector.

ProjectChunk хранит эмбеддинг в колонке vector(1536).
ANN-индекс НЕ создаётся: per-project exact-scan дешевле при dimensions=1536.
"""

from django.db import migrations, models
import django.db.models.deletion


def _create_vector_extension(apps, schema_editor):
    # Postgres-only: на SQLite (локальные тесты) — no-op.
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('CREATE EXTENSION IF NOT EXISTS vector;')


def _drop_vector_extension(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('DROP EXTENSION IF EXISTS vector;')


def _create_chunk_table(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("""
            CREATE TABLE IF NOT EXISTS aitext_projectchunk (
                id          bigserial PRIMARY KEY,
                project_id  bigint NOT NULL
                    REFERENCES aitext_project(id) ON DELETE CASCADE,
                file_id     bigint NOT NULL
                    REFERENCES aitext_projectfile(id) ON DELETE CASCADE,
                chunk_index integer NOT NULL CHECK (chunk_index >= 0),
                content     text NOT NULL,
                token_count integer NOT NULL DEFAULT 0
                    CHECK (token_count >= 0),
                embedding   vector(1536)
            );
            CREATE INDEX IF NOT EXISTS chunk_project_idx
                ON aitext_projectchunk (project_id);
            CREATE INDEX IF NOT EXISTS chunk_file_idx
                ON aitext_projectchunk (file_id);
        """)
    else:
        # SQLite (локальные тесты, без pgvector): та же таблица, embedding как BLOB.
        # PROJECT_VECTOR_RAG выключен по умолчанию — реальные векторные запросы сюда не идут.
        # sqlite3 не умеет несколько statements в одном execute() — разбиваем по отдельности.
        schema_editor.execute("""
            CREATE TABLE IF NOT EXISTS aitext_projectchunk (
                id          integer PRIMARY KEY AUTOINCREMENT,
                project_id  bigint NOT NULL
                    REFERENCES aitext_project(id) ON DELETE CASCADE,
                file_id     bigint NOT NULL
                    REFERENCES aitext_projectfile(id) ON DELETE CASCADE,
                chunk_index integer NOT NULL CHECK (chunk_index >= 0),
                content     text NOT NULL,
                token_count integer NOT NULL DEFAULT 0
                    CHECK (token_count >= 0),
                embedding   blob
            )
        """)
        schema_editor.execute(
            "CREATE INDEX IF NOT EXISTS chunk_project_idx ON aitext_projectchunk (project_id)"
        )
        schema_editor.execute(
            "CREATE INDEX IF NOT EXISTS chunk_file_idx ON aitext_projectchunk (file_id)"
        )


def _drop_chunk_table(apps, schema_editor):
    schema_editor.execute('DROP TABLE IF EXISTS aitext_projectchunk;')


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0014_public_space'),
    ]

    operations = [
        # 1. Активируем расширение pgvector (Postgres-only, no-op на SQLite)
        migrations.RunPython(_create_vector_extension, _drop_vector_extension),

        # 2. Новые поля на ProjectFile
        migrations.AddField(
            model_name='projectfile',
            name='embed_status',
            field=models.CharField(
                choices=[('none', 'Нет'), ('pending', 'В очереди'), ('done', 'Готово'), ('error', 'Ошибка')],
                default='none', max_length=12, verbose_name='Статус эмбеддингов',
            ),
        ),
        migrations.AddField(
            model_name='projectfile',
            name='source',
            field=models.CharField(
                choices=[('upload', 'Загружен'), ('repo', 'Из репозитория')],
                default='upload', max_length=10, verbose_name='Источник',
            ),
        ),
        migrations.AddField(
            model_name='projectfile',
            name='connector',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='synced_files', to='aitext.projectconnector',
                verbose_name='Коннектор (для repo-файлов)',
            ),
        ),
        migrations.AddField(
            model_name='projectfile',
            name='repo_path',
            field=models.CharField(blank=True, max_length=500, verbose_name='Путь в репозитории'),
        ),

        # 3. ProjectChunk — SeparateDatabaseAndState: SQL создаёт таблицу с vector-колонкой,
        #    CreateModel регистрирует модель в Django state (без физического CREATE TABLE).
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(_create_chunk_table, _drop_chunk_table),
            ],
            state_operations=[
                migrations.CreateModel(
                    name='ProjectChunk',
                    fields=[
                        ('id', models.BigAutoField(
                            auto_created=True, primary_key=True, serialize=False, verbose_name='ID',
                        )),
                        ('chunk_index', models.PositiveIntegerField()),
                        ('content', models.TextField()),
                        ('token_count', models.PositiveIntegerField(default=0)),
                        ('project', models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='chunks', to='aitext.project',
                        )),
                        ('file', models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='chunks', to='aitext.projectfile',
                        )),
                    ],
                    options={
                        'verbose_name': 'Чанк файла',
                        'verbose_name_plural': 'Чанки файлов',
                        'ordering': ['file', 'chunk_index'],
                    },
                ),
            ],
        ),
    ]
