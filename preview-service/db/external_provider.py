"""
ExternalProvider — connects to a user-owned PostgreSQL via a supplied DSN.

Sprint 3 — code-complete, not integration-tested.

The DSN (postgresql://user:pass@host:5432/db) is stored Fernet-encrypted on the
Django side and decrypted here only at connection time. The user owns the DB, so
provision() just parses the DSN and deprovision() is a no-op.

SECURITY: never log the decrypted DSN (it carries credentials).
"""
import urllib.parse

from .base import DatabaseProvider, DBCredentials
from . import crypto, _migrate


class ExternalProvider(DatabaseProvider):
    def __init__(self, conn_str_enc: str, fernet_key: str | None = None):
        # fernet_key accepted for interface symmetry; crypto reads shared key.
        self._conn_str_enc = conn_str_enc

    def provision(self, project_id: str) -> DBCredentials:
        dsn = crypto.decrypt(self._conn_str_enc)
        parsed = urllib.parse.urlparse(dsn)
        if parsed.scheme not in ("postgresql", "postgres"):
            raise ValueError("External DSN must be a postgresql:// connection string")
        host = parsed.hostname
        if not host:
            raise ValueError("External DSN is missing a host")
        return DBCredentials(
            host=host,
            port=parsed.port or 5432,
            dbname=(parsed.path or "/").lstrip("/") or "postgres",
            user=urllib.parse.unquote(parsed.username or ""),
            password=urllib.parse.unquote(parsed.password or ""),
            schema=None,
            provider="external",
        )

    def sync_schema(self, credentials: DBCredentials, migrations: list[str]) -> None:
        _migrate.run_migrations(credentials, migrations)

    def deprovision(self, project_id: str) -> None:
        # User owns the database — nothing to tear down.
        return None
