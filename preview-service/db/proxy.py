"""
db-proxy — executes SQL from inside an E2B preview sandbox against the project's
provisioned database.

Sprint 3 — code-complete, not integration-tested.

INTEGRATION GAP (intentional, deferred): the Redis session dict written today by
runtime/e2b_runtime.py (E2BRuntime.start, the `preview:sess:<id>` key) does NOT
yet carry `db_credentials_enc`. Wiring the provisioned credentials into that
session is a later step ("E2BRuntime.start() provisions lazily"). Until then the
proxy returns 404 "no database" for sessions without `db_credentials_enc`,
rather than crashing.

Security model:
  - X-Internal-Token shared secret (same as the rest of preview-service).
  - Credentials live Fernet-encrypted in the Redis session; decrypted per-request,
    never logged.
  - connect_timeout=3s; statement_timeout=5s.
  - Per-(provider, project) circuit breaker in Redis: 3 fails -> 503 for 60s.
  - DROP / ALTER / TRUNCATE refused (case-insensitive, leading whitespace stripped).
"""
import json
import logging
import sys
import os

import psycopg2
from psycopg2.extras import RealDictCursor
import redis as _redis_module
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import settings

from .base import DBCredentials
from . import crypto

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/db-proxy", tags=["db-proxy"])

_r = _redis_module.from_url(settings.REDIS_URL, decode_responses=True)

# Must match runtime/e2b_runtime.py SESSION_PREFIX so we read the same sessions.
SESSION_PREFIX = "preview:sess:"

_CONNECT_TIMEOUT = 3          # seconds
_STATEMENT_TIMEOUT_MS = 5000  # 5s
_CB_THRESHOLD = 3
_CB_TTL = 60                  # seconds
_MAX_ROWS = 1000

_BLOCKED_PREFIXES = ("DROP", "ALTER", "TRUNCATE")


# ── Auth ────────────────────────────────────────────────────────────────────────

def verify_token(x_internal_token: str = Header(...)):
    if x_internal_token != settings.INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Models ──────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    session_id: str
    sql: str
    params: list = []


class QueryResponse(BaseModel):
    rows: list[dict]
    rowcount: int


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _sess_key(session_id: str) -> str:
    return f"{SESSION_PREFIX}{session_id}"


def _get_session(session_id: str) -> dict:
    raw = _r.get(_sess_key(session_id))
    if not raw:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    return json.loads(raw)


def _load_credentials(session: dict) -> DBCredentials:
    enc = session.get("db_credentials_enc")
    if not enc:
        # See INTEGRATION GAP in module docstring.
        raise HTTPException(status_code=404, detail="У сессии нет базы данных")
    try:
        return DBCredentials.from_json(crypto.decrypt(enc))
    except Exception:
        # Do not leak ciphertext or key material.
        raise HTTPException(status_code=500, detail="Невозможно расшифровать учётные данные БД")


def _is_blocked(sql_text: str) -> bool:
    head = sql_text.lstrip().upper()
    return any(head.startswith(prefix) for prefix in _BLOCKED_PREFIXES)


def _cb_key(provider: str, project_id: str) -> str:
    return f"cb:{provider}:{project_id}:fails"


def _circuit_check(provider: str, project_id: str) -> None:
    fails = _r.get(_cb_key(provider, project_id))
    if fails is not None and int(fails) >= _CB_THRESHOLD:
        raise HTTPException(status_code=503, detail="Circuit open")


def _circuit_record_failure(provider: str, project_id: str) -> None:
    key = _cb_key(provider, project_id)
    _r.incr(key)
    _r.expire(key, _CB_TTL)


def _circuit_record_success(provider: str, project_id: str) -> None:
    _r.delete(_cb_key(provider, project_id))


# ── Endpoint ────────────────────────────────────────────────────────────────────

@router.post("/query", response_model=QueryResponse, dependencies=[Depends(verify_token)])
def db_query(req: QueryRequest):
    if _is_blocked(req.sql):
        raise HTTPException(status_code=403, detail="DDL-операция запрещена (DROP/ALTER/TRUNCATE)")

    session = _get_session(req.session_id)
    project_id = session.get("project_id", "unknown")
    creds = _load_credentials(session)

    _circuit_check(creds.provider, project_id)

    conn = None
    try:
        conn = psycopg2.connect(
            host=creds.host,
            port=creds.port,
            dbname=creds.dbname,
            user=creds.user,
            password=creds.password,
            connect_timeout=_CONNECT_TIMEOUT,
            cursor_factory=RealDictCursor,
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '{_STATEMENT_TIMEOUT_MS}'")
            if creds.schema:
                cur.execute("SET search_path TO %s", (creds.schema,))
            cur.execute(req.sql, req.params or None)
            rowcount = cur.rowcount
            if cur.description is not None:
                rows = [dict(r) for r in cur.fetchmany(_MAX_ROWS)]
            else:
                rows = []
    except HTTPException:
        raise
    except Exception as exc:
        _circuit_record_failure(creds.provider, project_id)
        # Log the DB error class server-side only. The caller is untrusted code
        # inside the sandbox — a psycopg2 OperationalError can carry host/user,
        # so never echo str(exc) back over the wire.
        logger.warning("db-proxy query failed for project %s: %s", project_id, type(exc).__name__)
        raise HTTPException(status_code=400, detail="Ошибка выполнения SQL-запроса")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    _circuit_record_success(creds.provider, project_id)
    return QueryResponse(rows=rows, rowcount=rowcount)
