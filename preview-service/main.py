"""
preview-service — FastAPI микросервис для live-preview серверных стеков.
Отдельный процесс от src/ (Django): untrusted code изолирован.
Авторизация: X-Internal-Token заголовок (shared secret между Django и этим сервисом).

Sprint 6: per-user rate limit (max 5 sessions/user), startup latency metrics (p95/p99).

Bugfix (2026-06-25): TOCTOU race in per-user rate limit fixed with INCR-first pattern:
increment counter BEFORE expensive sandbox start, decrement on failure. This prevents
two concurrent /preview/start calls from both reading 0 and bypassing the limit.
"""
import asyncio
import json
import logging
import time
from functools import partial

import redis as _redis_module
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel

import settings
from runtime.base import Stack
from runtime.e2b_runtime import E2BRuntime
from db.proxy import router as db_router

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="aineron preview-service", version="0.3.0")
_runtime = E2BRuntime()
app.include_router(db_router)

_r = _redis_module.from_url(settings.REDIS_URL, decode_responses=True)

MAX_SESSIONS_PER_USER = int(settings.MAX_CONCURRENT // 2) or 3
LATENCY_KEY = "preview:latency"  # Redis list of startup durations (float seconds)
LATENCY_KEEP = 1000              # Keep last N samples for percentile calc


def verify_token(x_internal_token: str = Header(...)):
    if x_internal_token != settings.INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _user_sessions_key(user_id: str) -> str:
    return f"preview:user_sessions:{user_id}"


def _try_acquire_user_slot(user_id: str, ttl: int) -> bool:
    """
    INCR-first rate limit: increment counter atomically, check limit, rollback if exceeded.
    Prevents TOCTOU race where two concurrent requests both read count=0 and both pass.
    Returns True if slot acquired, False if limit exceeded.
    """
    key = _user_sessions_key(user_id)
    new_count = _r.incr(key)
    _r.expire(key, ttl + 120)
    if new_count > MAX_SESSIONS_PER_USER:
        _r.decr(key)
        return False
    return True


def _dec_user_sessions(user_id: str):
    key = _user_sessions_key(user_id)
    val = int(_r.get(key) or 0)
    if val > 0:
        _r.decr(key)


def _record_latency(seconds: float):
    _r.lpush(LATENCY_KEY, seconds)
    _r.ltrim(LATENCY_KEY, 0, LATENCY_KEEP - 1)


def _percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p / 100)
    return sorted_data[min(idx, len(sorted_data) - 1)]


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "preview-service", "version": "0.3.0"}


# ── Metrics (Sprint 6) ────────────────────────────────────────────────────────

@app.get("/metrics", dependencies=[Depends(verify_token)])
def metrics():
    """Startup latency percentiles (p50/p95/p99) over last 1000 samples."""
    raw = _r.lrange(LATENCY_KEY, 0, -1)
    data = [float(x) for x in raw if x]
    return {
        "samples": len(data),
        "p50_s": round(_percentile(data, 50), 3),
        "p95_s": round(_percentile(data, 95), 3),
        "p99_s": round(_percentile(data, 99), 3),
        "slots_used": int(_r.get("preview:slots") or 0),
        "max_concurrent": settings.MAX_CONCURRENT,
    }


# ── Models ────────────────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    project_id: str
    stack: str
    code_files: dict[str, str]
    ttl: int = settings.DEFAULT_TTL
    env: dict[str, str] = {}
    user_id: str = ""           # Sprint 6: for per-user rate limit
    db_credentials_enc: str = ""  # Sprint 7: Fernet-encrypted DBCredentials JSON


class LogsResponse(BaseModel):
    session_id: str
    lines: list[str]


class StartResponse(BaseModel):
    session_id: str
    public_url: str
    expires_at: float
    state: str = "starting"


class StatusResponse(BaseModel):
    session_id: str
    state: str
    public_url: str | None
    logs_tail: list[str]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/preview/start", response_model=StartResponse, dependencies=[Depends(verify_token)])
async def preview_start(req: StartRequest):
    try:
        stack = Stack(req.stack)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Неизвестный стек: {req.stack}")

    # Sprint 6: per-user rate limit (INCR-first, atomic — no TOCTOU)
    user_slot_acquired = False
    if req.user_id:
        if not _try_acquire_user_slot(req.user_id, req.ttl):
            raise HTTPException(
                status_code=429,
                detail=f"Превышен лимит активных превью ({MAX_SESSIONS_PER_USER} на пользователя). Остановите предыдущую сессию.",
            )
        user_slot_acquired = True

    t0 = time.perf_counter()
    loop = asyncio.get_event_loop()
    try:
        session = await loop.run_in_executor(
            None,
            partial(_runtime.start, req.project_id, req.code_files, stack, req.ttl, req.env or {}, req.db_credentials_enc),
        )
    except RuntimeError as exc:
        if user_slot_acquired:
            _dec_user_sessions(req.user_id)
        raise HTTPException(status_code=429, detail=str(exc))
    except ValueError as exc:
        if user_slot_acquired:
            _dec_user_sessions(req.user_id)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        if user_slot_acquired:
            _dec_user_sessions(req.user_id)
        raise HTTPException(status_code=500, detail=f"E2B error: {exc}")

    # Record startup latency
    elapsed = time.perf_counter() - t0
    _record_latency(elapsed)

    return StartResponse(
        session_id=session.session_id,
        public_url=session.public_url,
        expires_at=session.expires_at,
        state="starting",
    )


@app.delete("/preview/{session_id}", dependencies=[Depends(verify_token)])
async def preview_stop(session_id: str, x_user_id: str = Header(default="")):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, partial(_runtime.stop, session_id))
    if x_user_id:
        _dec_user_sessions(x_user_id)  # reaper also reconciles, so this is a best-effort fast path
    return {"ok": True}


@app.get("/preview/{session_id}/status", response_model=StatusResponse, dependencies=[Depends(verify_token)])
def preview_status(session_id: str):
    status = _runtime.status(session_id)
    return StatusResponse(
        session_id=status.session_id,
        state=status.state.value,
        public_url=status.public_url,
        logs_tail=status.logs_tail,
    )


@app.get("/preview/{session_id}/logs", response_model=LogsResponse, dependencies=[Depends(verify_token)])
def preview_logs(session_id: str, lines: int = 200):
    """Sprint 7: tail /tmp/preview.log from the running E2B sandbox."""
    return LogsResponse(
        session_id=session_id,
        lines=_runtime.get_logs(session_id, lines=min(lines, 500)),
    )
