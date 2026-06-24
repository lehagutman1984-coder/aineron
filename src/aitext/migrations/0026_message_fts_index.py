from django.db import migrations


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
        migrations.RunSQL(
            sql=(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS aitext_message_fts_gin "
                "ON aitext_message "
                "USING gin(to_tsvector('russian', "
                "coalesce(plain_text, '') || ' ' || coalesce(content, '')));"
            ),
            reverse_sql="DROP INDEX IF EXISTS aitext_message_fts_gin;",
        ),
    ]
