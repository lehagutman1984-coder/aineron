"""
TimewebProvider — Sprint 4: Timeweb Cloud Databases API (российская юрисдикция, 152-ФЗ).
Code-complete, not integration-tested (requires TIMEWEB_API_TOKEN).

API reference: https://timeweb.cloud/api-docs
Endpoint base: https://api.timeweb.cloud/api/v2
Auth: Bearer {TIMEWEB_API_TOKEN}
"""
import logging
import time

import httpx

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import settings

from .base import DatabaseProvider, DBCredentials

logger = logging.getLogger(__name__)

_TIMEWEB_BASE = "https://api.timeweb.cloud/api/v2"
_DEFAULT_PRESET_ID = 19   # Самый маленький preset (1 CPU, 512MB RAM) — уточнить в ЛК Timeweb
_DEFAULT_LOCATION = "ru-1"
_CREATE_TIMEOUT_S = 120   # DB provisioning takes up to 2 minutes


class TimewebProvider(DatabaseProvider):
    """
    Создаёт управляемую PostgreSQL базу в Timeweb Cloud.
    Данные обрабатываются на серверах в РФ — соответствие 152-ФЗ.

    Timeweb Cloud API v2 для баз данных:
    - POST /dbs             — создать instance
    - GET  /dbs/{id}        — получить статус и credentials
    - DELETE /dbs/{id}      — удалить
    """

    def __init__(self, api_token: str | None = None):
        self._token = api_token or settings.TIMEWEB_API_TOKEN
        if not self._token:
            raise RuntimeError("TIMEWEB_API_TOKEN не установлен — нельзя создать Timeweb БД")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def provision(self, project_id: str) -> DBCredentials:
        short = project_id.replace("-", "")[:12]
        db_name = f"aineron-{short}"

        with httpx.Client(timeout=30) as client:
            # Create DB instance
            resp = client.post(
                f"{_TIMEWEB_BASE}/dbs",
                headers=self._headers(),
                json={
                    "name": db_name,
                    "type": "postgres",
                    "preset_id": _DEFAULT_PRESET_ID,
                    "location": _DEFAULT_LOCATION,
                    "is_external_ip": False,
                },
            )
            if not resp.is_success:
                raise RuntimeError(
                    f"Timeweb создание БД: {resp.status_code} — {resp.text[:300]}"
                )
            db_id = resp.json()["db"]["id"]
            logger.info("Timeweb DB created: id=%s project=%s", db_id, project_id)

            # Poll until status == 'on'
            deadline = time.time() + _CREATE_TIMEOUT_S
            while time.time() < deadline:
                info_resp = client.get(
                    f"{_TIMEWEB_BASE}/dbs/{db_id}",
                    headers=self._headers(),
                )
                if not info_resp.is_success:
                    time.sleep(5)
                    continue
                db = info_resp.json()["db"]
                if db.get("status") == "on":
                    return DBCredentials(
                        host=db["ip"],
                        port=db.get("port", 5432),
                        dbname=db.get("name", db_name),
                        user=db.get("login", "postgres"),
                        password=db.get("password", ""),
                        schema=None,
                        provider="timeweb",
                    )
                time.sleep(5)

            raise RuntimeError(
                f"Timeweb БД {db_id} не перешла в статус 'on' за {_CREATE_TIMEOUT_S}с"
            )

    def sync_schema(self, credentials: DBCredentials, migrations: list[str]) -> None:
        """Run forward-only migrations via psycopg2 + schema version table."""
        from db._migrate import run_migrations
        run_migrations(credentials, migrations)

    def deprovision(self, project_id: str) -> None:
        """
        Удаляет Timeweb DB по db_id, хранящемуся в Redis/Django.
        В текущей реализации project_id используется как маркер — реальный db_id
        должен быть сохранён при provision() (в ProjectDatabase.neon_project_id поле
        переиспользуется под Timeweb ID для унификации).
        """
        db_id = project_id  # caller passes actual db_id
        if not db_id:
            return
        try:
            with httpx.Client(timeout=10) as client:
                client.delete(
                    f"{_TIMEWEB_BASE}/dbs/{db_id}",
                    headers=self._headers(),
                )
            logger.info("Timeweb DB deleted: id=%s", db_id)
        except Exception as exc:
            logger.warning("Timeweb deprovision failed %s: %s", db_id, exc)
