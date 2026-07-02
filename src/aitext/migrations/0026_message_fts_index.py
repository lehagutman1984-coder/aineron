from django.db import migrations


def _create_fts_index(apps, schema_editor):
    # Postgres-only (GIN FTS): на SQLite (локальные тесты) — no-op.
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS aitext_message_fts_gin "
            "ON aitext_message "
            "USING gin(to_tsvector('russian', "
            "coalesce(plain_text, '') || ' ' || coalesce(content, '')));"
        )


def _drop_fts_index(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("DROP INDEX IF EXISTS aitext_message_fts_gin;")


class Migration(migrations.Migration):
    """
    Add GIN FTS index on Message content fields for chat search.
    atomic=False required by CONCURRENTLY — avoids lock on large tables.
    """

    atomic = False  # CONCURRENTLY cannot run inside a transaction

    dependencies = [
        ("aitext", "0025_projectchunk_index_integerfield"),
    ]

    operations = [
        migrations.RunPython(_create_fts_index, _drop_fts_index),
    ]
