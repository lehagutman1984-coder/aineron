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
  - Per-(provider, project) circuit breaker in Redis: 3 connectivity fails → 503 for 60s.
    Query-level user errors (ProgrammingError, DataError) do NOT trip the breaker.
  - DROP / ALTER / TRUNCATE refused (case-insensitive).
  - Stacked statements (semicolons) refused — prevents prefix-check bypass.

Bugfixes (2026-06-25):
  - DDL blocklist bypass via stacked statements fixed (semicolon rejection).
  - Circuit breaker now only trips on OperationalError (connectivity), not user query errors.
"""
import json
import logging
import sys
import os

import psycopg2
import psycopg2.errorcodes
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

_BLOCKED_PREFIXES = (
    "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "COPY",
)


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
    """
    Reject DDL/DDL-stacked statements.

    Security model:
    - Strip block comments (/* ... */) and line comments (-- ...) before keyword check
      so that comment-prefixed DDL like '/* */ DROP TABLE x' doesn't slip through.
    - Reject stacked statements (;) except when inside a string literal.
      Simple heuristic: reject if ';' appears outside of single-quoted strings.
    - Blocklist covers DDL + privilege statements (schema-change intent blocked;
      DML writes are allowed for the sandboxed app).
    """
    import re

    # Strip block comments (/* ... */) — multiline
    cleaned = re.sub(r"/\*.*?\*/", " ", sql_text, flags=re.DOTALL)
    # Strip line comments (-- to end of line)
    cleaned = re.sub(r"--[^\n]*", " ", cleaned)

    head = cleaned.lstrip().upper()
    if any(head.startswith(prefix) for prefix in _BLOCKED_PREFIXES):
        return True

    # Reject stacked statements: check for ';' outside string literals
    # Walk character by character to track string context
    in_string = False
    escape_next = False
    for ch in sql_text:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == "'":
            in_string = not in_string
            continue
        if ch == ';' and not in_string:
            return True

    return False


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
        raise HTTPException(
            status_code=403,
            detail="Запрос запрещён (DDL-операция или многострочный запрос не поддерживаются)",
        )

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
                from psycopg2 import sql as _sql
                cur.execute(_sql.SQL("SET search_path TO {}").format(_sql.Identifier(creds.schema)))
            cur.execute(req.sql, req.params or None)
            rowcount = cur.rowcount
            if cur.description is not None:
                rows = [dict(r) for r in cur.fetchmany(_MAX_ROWS)]
            else:
                rows = []
    except HTTPException:
        raise
    except psycopg2.OperationalError as exc:
        # Connectivity failure → trip circuit breaker (DB might be down/unreachable)
        _circuit_record_failure(creds.provider, project_id)
        logger.warning(
            "db-proxy connection failed for project %s: %s", project_id, type(exc).__name__
        )
        raise HTTPException(status_code=503, detail="Ошибка подключения к БД")
    except Exception as exc:
        # Query-level error (ProgrammingError, DataError, timeout) → don't trip the breaker;
        # this is user error, not a connectivity problem.
        logger.warning(
            "db-proxy query failed for project %s: %s", project_id, type(exc).__name__
        )
        raise HTTPException(status_code=400, detail="Ошибка выполнения SQL-запроса")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    _circuit_record_success(creds.provider, project_id)
    return QueryResponse(rows=rows, rowcount=rowcount)
