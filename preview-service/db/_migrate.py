"""
Forward-only migration runner shared by the DB providers.

Sprint 3 — code-complete, not integration-tested.

Tracks the applied version in a `__schema_version` table (one row). Migrations
are a list of SQL strings; index i in the list is "version i+1". Already-applied
migrations are skipped. Each unapplied migration + the version bump run in one
transaction so a failure leaves the version consistent.
"""
import psycopg2

from .base import DBCredentials

_CONNECT_TIMEOUT = 5
_VERSION_TABLE = "__schema_version"


def _connect(credentials: DBCredentials):
    conn = psycopg2.connect(
        host=credentials.host,
        port=credentials.port,
        dbname=credentials.dbname,
        user=credentials.user,
        password=credentials.password,
        connect_timeout=_CONNECT_TIMEOUT,
    )
    conn.autocommit = False
    return conn


def _qualified(schema: str | None, table: str) -> str:
    if schema:
        return f'"{schema}"."{table}"'
    return f'"{table}"'


def run_migrations(credentials: DBCredentials, migrations: list[str]) -> None:
    """Run forward-only migrations, skipping ones already applied."""
    if not migrations:
        return
    conn = _connect(credentials)
    try:
        with conn.cursor() as cur:
            if credentials.schema:
                # Ensure the schema exists and is on the search_path.
                cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{credentials.schema}";')
                cur.execute(f'SET search_path TO "{credentials.schema}";')
            version_table = _qualified(credentials.schema, _VERSION_TABLE)
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {version_table} "
                "(version INTEGER NOT NULL, applied_at TIMESTAMPTZ DEFAULT now());"
            )
            cur.execute(f"SELECT COALESCE(MAX(version), 0) FROM {version_table};")
            current = cur.fetchone()[0] or 0
        conn.commit()

        for idx, sql in enumerate(migrations, start=1):
            if idx <= current:
                continue
            with conn.cursor() as cur:
                if credentials.schema:
                    cur.execute(f'SET search_path TO "{credentials.schema}";')
                cur.execute(sql)
                version_table = _qualified(credentials.schema, _VERSION_TABLE)
                cur.execute(
                    f"INSERT INTO {version_table} (version) VALUES (%s);", (idx,)
                )
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
