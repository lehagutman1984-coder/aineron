"""
AineronSchemaProvider — schema-per-project on aineron's own PostgreSQL.

Sprint 3 — code-complete, not integration-tested.

Each Studio project gets a dedicated schema `proj_<uuid_no_dashes>` plus a
schema-scoped PG role `sp_<short_id>` whose privileges are confined to that
schema. The admin connection (AINERON_DB_*) provisions/deprovisions; the
returned DBCredentials use the per-project role so untrusted preview code can
never reach other schemas.

Never log the generated password.
"""
import sys
import os

import psycopg2
from psycopg2 import sql

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import settings

from .base import DatabaseProvider, DBCredentials
from . import _migrate

_CONNECT_TIMEOUT = 5


def _schema_name(project_id: str) -> str:
    return "proj_" + project_id.replace("-", "")


def _role_name(project_id: str) -> str:
    # Use full UUID (32 hex chars) to avoid collision on first 12 chars.
    # sp_ + 32 = 35 chars, well within PG's 63-byte limit.
    return "sp_" + project_id.replace("-", "")


def _gen_password() -> str:
    import secrets
    return secrets.token_urlsafe(32)


class AineronSchemaProvider(DatabaseProvider):
    def __init__(self):
        self.host = settings.AINERON_DB_HOST
        self.port = settings.AINERON_DB_PORT
        self.dbname = settings.AINERON_DB_NAME
        self._admin_user = settings.AINERON_DB_USER
        self._admin_password = settings.AINERON_DB_PASSWORD

    def _admin_conn(self):
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=self._admin_user,
            password=self._admin_password,
            connect_timeout=_CONNECT_TIMEOUT,
        )

    def provision(self, project_id: str) -> DBCredentials:
        schema = _schema_name(project_id)
        role = _role_name(project_id)
        password = _gen_password()

        conn = self._admin_conn()
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema))
                )
                # Create or reset the schema role with a fresh password.
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s;", (role,))
                exists = cur.fetchone() is not None
                if exists:
                    cur.execute(
                        sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD %s").format(
                            sql.Identifier(role)
                        ),
                        (password,),
                    )
                else:
                    cur.execute(
                        sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(
                            sql.Identifier(role)
                        ),
                        (password,),
                    )
                # Confine the role to its own schema.
                cur.execute(
                    sql.SQL("ALTER SCHEMA {} OWNER TO {}").format(
                        sql.Identifier(schema), sql.Identifier(role)
                    )
                )
                cur.execute(
                    sql.SQL("GRANT USAGE, CREATE ON SCHEMA {} TO {}").format(
                        sql.Identifier(schema), sql.Identifier(role)
                    )
                )
                cur.execute(
                    sql.SQL("ALTER ROLE {} SET search_path TO {}").format(
                        sql.Identifier(role), sql.Identifier(schema)
                    )
                )
        finally:
            conn.close()

        return DBCredentials(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=role,
            password=password,
            schema=schema,
            provider="aineron",
        )

    def sync_schema(self, credentials: DBCredentials, migrations: list[str]) -> None:
        _migrate.run_migrations(credentials, migrations)

    def deprovision(self, project_id: str) -> None:
        schema = _schema_name(project_id)
        role = _role_name(project_id)
        conn = self._admin_conn()
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(schema)
                    )
                )
                # Strip any residual cross-database/default privileges before drop.
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s;", (role,))
                if cur.fetchone() is not None:
                    cur.execute(
                        sql.SQL("DROP OWNED BY {} CASCADE").format(sql.Identifier(role))
                    )
                    cur.execute(
                        sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role))
                    )
        finally:
            conn.close()
