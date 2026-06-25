"""
NeonProvider — provisions a Neon project via the user's own Neon API key.

Sprint 3 — code-complete, not integration-tested.

Self-serve model (no OAuth partnership): the user supplies their Neon API key,
which is stored Fernet-encrypted on the Django side and decrypted here only to
call the Neon Management API.

SECURITY: the decrypted API key is never logged. Neon API errors are caught and
re-raised with status + a generic message — the bearer token is never echoed.
"""
import sys
import os
import urllib.parse

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import settings

from .base import DatabaseProvider, DBCredentials
from . import crypto, _migrate

_NEON_API = "https://console.neon.tech/api/v2"
_HTTP_TIMEOUT = 30.0


class NeonProvider(DatabaseProvider):
    def __init__(self, neon_api_key_enc: str, fernet_key: str | None = None):
        # fernet_key accepted for interface symmetry; crypto reads the shared
        # settings.FERNET_KEY so both sides stay byte-compatible.
        self._neon_api_key_enc = neon_api_key_enc
        self._neon_project_id: str | None = None

    def _decrypt_key(self) -> str:
        return crypto.decrypt(self._neon_api_key_enc)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._decrypt_key()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @staticmethod
    def _raise_clean(resp: httpx.Response) -> None:
        # Never include the request (which carries the bearer token) in the error.
        raise RuntimeError(f"Neon API error {resp.status_code}: {resp.text[:300]}")

    def provision(self, project_id: str) -> DBCredentials:
        body = {
            "project": {
                "name": f"aineron-{project_id[:8]}",
                "region_id": settings.NEON_DEFAULT_REGION,
                "pg_version": 16,
            }
        }
        try:
            with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
                resp = client.post(
                    f"{_NEON_API}/projects", headers=self._headers(), json=body
                )
        except httpx.HTTPError as e:
            # Re-raise without the key; httpx errors don't carry headers in str().
            raise RuntimeError(f"Neon API request failed: {type(e).__name__}") from None
        if resp.status_code not in (200, 201):
            self._raise_clean(resp)

        data = resp.json()
        self._neon_project_id = data.get("project", {}).get("id")

        conn_uri = self._extract_connection_uri(data)
        if not conn_uri:
            raise RuntimeError("Neon API response missing connection_uri")

        parsed = urllib.parse.urlparse(conn_uri)
        return DBCredentials(
            host=parsed.hostname or "",
            port=parsed.port or 5432,
            dbname=(parsed.path or "/").lstrip("/") or "neondb",
            user=urllib.parse.unquote(parsed.username or ""),
            password=urllib.parse.unquote(parsed.password or ""),
            schema=None,
            provider="neon",
        )

    @staticmethod
    def _extract_connection_uri(data: dict) -> str | None:
        # Neon returns connection_uris: [{connection_uri, connection_parameters}, ...]
        uris = data.get("connection_uris") or []
        if uris and isinstance(uris, list):
            return uris[0].get("connection_uri")
        return None

    @property
    def neon_project_id(self) -> str | None:
        return self._neon_project_id

    def sync_schema(self, credentials: DBCredentials, migrations: list[str]) -> None:
        _migrate.run_migrations(credentials, migrations)

    def deprovision(self, project_id: str, neon_project_id: str | None = None) -> None:
        pid = neon_project_id or self._neon_project_id
        if not pid:
            raise RuntimeError("Cannot deprovision Neon project: unknown neon_project_id")
        try:
            with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
                resp = client.delete(
                    f"{_NEON_API}/projects/{pid}", headers=self._headers()
                )
        except httpx.HTTPError as e:
            raise RuntimeError(f"Neon API request failed: {type(e).__name__}") from None
        if resp.status_code not in (200, 204):
            self._raise_clean(resp)
