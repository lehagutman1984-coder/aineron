"""
preview-service — FastAPI микросервис для live-preview серверных стеков.
Отдельный процесс от src/ (Django): untrusted code изолирован.
Авторизация: X-Internal-Token заголовок (shared secret между Django и этим сервисом).

Sprint 6: per-user rate limit (max 5 sessions/user), startup latency metrics (p95/p99).
Sprint 12: cold-start acceleration — /preview/prewarm, /pool/stats, claim_source/eta in StartResponse.

Bugfix (2026-06-25): TOCTOU race in per-user rate limit fixed with INCR-first pattern.
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
from runtime.e2b_runtime import E2BRuntime, POOL_LIST_PREFIX, POOL_TARGET_PREFIX, CLAIMS_PREFIX
from db.proxy import router as db_router

from concurrent.futures import ThreadPoolExecutor as _TPE
_PREWARM_EXECUTOR = _TPE(max_workers=4, thread_name_prefix="prewarm")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(title="aineron preview-service", version="0.4.0")
_runtime = E2BRuntime()
app.include_router(db_router)

_r = _redis_module.from_url(settings.REDIS_URL, decode_responses=True)

MAX_SESSIONS_PER_USER = int(settings.MAX_CONCURRENT // 2) or 3
LATENCY_KEY = "preview:latency"  # Redis list of startup durations (float seconds)
LATENCY_KEEP = 1000              # Keep last N samples for percentile calc

# ETA by claim source — rough p50 values for UX hint (seconds)
_ETA_BY_SOURCE = {
    "prewarm": 3,
    "paused": 2,
    "pool": 5,
    "cold": 12,
}


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
    return {"ok": True, "service": "preview-service", "version": "0.4.0"}


# ── Metrics (Sprint 6 + Sprint 12 hit rates) ──────────────────────────────────

@app.get("/metrics", dependencies=[Depends(verify_token)])
def metrics():
    """Startup latency percentiles + cold-start hit rates."""
    raw = _r.lrange(LATENCY_KEY, 0, -1)
    data = [float(x) for x in raw if x]

    # L7 hit-rate counters
    claim_prewarm = int(_r.get(f"{CLAIMS_PREFIX}prewarm") or 0)
    claim_paused  = int(_r.get(f"{CLAIMS_PREFIX}paused")  or 0)
    claim_pool    = int(_r.get(f"{CLAIMS_PREFIX}pool")    or 0)
    claim_cold    = int(_r.get(f"{CLAIMS_PREFIX}cold")    or 0)
    total_claims  = claim_prewarm + claim_paused + claim_pool + claim_cold or 1

    return {
        "samples": len(data),
        "p50_s": round(_percentile(data, 50), 3),
        "p95_s": round(_percentile(data, 95), 3),
        "p99_s": round(_percentile(data, 99), 3),
        "slots_used": int(_r.get("preview:slots") or 0),
        "max_concurrent": settings.MAX_CONCURRENT,
        # Sprint 12 cold-start metrics
        "hit_rate": round((claim_prewarm + claim_paused + claim_pool) / total_claims, 3),
        "prewarm_hits": claim_prewarm,
        "paused_hits": claim_paused,
        "pool_hits": claim_pool,
        "cold_starts": claim_cold,
    }


# ── Pool stats (Sprint 12) ────────────────────────────────────────────────────

@app.get("/pool/stats", dependencies=[Depends(verify_token)])
def pool_stats():
    """Current warm pool depth per stack."""
    result = {}
    for stack in (Stack.NEXTJS, Stack.PYTHON, Stack.DJANGO):
        k = f"{POOL_LIST_PREFIX}{stack.value}"
        result[stack.value] = {
            "warm": _r.llen(k),
            "target": int(_r.get(f"{POOL_TARGET_PREFIX}{stack.value}") or getattr(settings, "POOL_TARGET_DEFAULT", 2)),
        }
    return result


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
    started_at: float = 0.0
    state: str = "starting"
    # Sprint 12: cold-start UX hints for frontend
    claim_source: str = "cold"    # prewarm | paused | pool | cold
    eta_seconds: int = 12         # rough time-to-running estimate


class StopResponse(BaseModel):
    ok: bool
    duration_seconds: float = 0.0
    started_at: float = 0.0


class StatusResponse(BaseModel):
    session_id: str
    state: str
    public_url: str | None
    logs_tail: list[str]


class PrewarmRequest(BaseModel):
    project_id: str
    stack: str
    dep_manifest: str = ""   # content of package.json or requirements.txt
    dep_hash: str = ""       # sha256[:16] of dep_manifest for idempotency check


# ── Preview/start ─────────────────────────────────────────────────────────────

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
        logger.exception("preview_start failed (project=%s stack=%s): %s", req.project_id, req.stack, exc)
        raise HTTPException(status_code=500, detail=f"E2B error: {exc}")

    # Record startup latency
    elapsed = time.perf_counter() - t0
    _record_latency(elapsed)

    # Retrieve started_at and claim_source from Redis session
    _sess_raw = _r.get(f"preview:sess:{session.session_id}")
    _sess_data = json.loads(_sess_raw) if _sess_raw else {}
    claim_source = _sess_data.get("claim_source", "cold")
    return StartResponse(
        session_id=session.session_id,
        public_url=session.public_url,
        expires_at=session.expires_at,
        started_at=_sess_data.get("started_at", time.time()),
        state="starting",
        claim_source=claim_source,
        eta_seconds=_ETA_BY_SOURCE.get(claim_source, 12),
    )


# ── Preview/prewarm (Sprint 12 / L3) ─────────────────────────────────────────

@app.post("/preview/prewarm", dependencies=[Depends(verify_token)])
async def preview_prewarm(req: PrewarmRequest):
    """Fire-and-forget: create + install deps during generation, not on user click.

    Idempotent: skips if prewarm already exists for the same project+dep_hash.
    Called by Celery task prewarm_e2b after each commit_to_gitea.
    """
    try:
        stack = Stack(req.stack)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Неизвестный стек: {req.stack}")

    # Idempotency: same dep_hash → already warm, skip
    existing_sid = _r.get(f"preview:prewarm:{req.project_id}")
    existing_hash = _r.get(f"preview:prewarmhash:{req.project_id}")
    if existing_sid and existing_hash == req.dep_hash:
        return {"status": "already_warm", "sandbox_id": existing_sid}

    # Build code_files dict containing the manifest (for prewarm + hash compute)
    code_files: dict[str, str] = {}
    if req.dep_manifest:
        fname = "package.json" if stack == Stack.NEXTJS else "requirements.txt"
        code_files[fname] = req.dep_manifest

    # Fire-and-forget: don't await prewarm() — it can take 30-60s
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        _PREWARM_EXECUTOR,
        partial(_runtime.prewarm, req.project_id, code_files, stack),
    )
    return {"status": "warming"}


# ── Preview/stop ──────────────────────────────────────────────────────────────

@app.delete("/preview/{session_id}", response_model=StopResponse, dependencies=[Depends(verify_token)])
async def preview_stop(session_id: str, x_user_id: str = Header(default="")):
    # Read started_at BEFORE stopping (session key will be deleted by stop())
    _sess_raw = _r.get(f"preview:sess:{session_id}")
    _sess_data = json.loads(_sess_raw) if _sess_raw else {}
    started_at = _sess_data.get("started_at", time.time())
    duration_seconds = max(0.0, time.time() - started_at)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, partial(_runtime.stop, session_id))
    if x_user_id:
        _dec_user_sessions(x_user_id)  # reaper also reconciles, so this is a best-effort fast path
    return StopResponse(ok=True, duration_seconds=duration_seconds, started_at=started_at)


# ── Preview/status & logs ─────────────────────────────────────────────────────

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


@app.get("/preview/{session_id}/logs/stream", dependencies=[Depends(verify_token)])
async def preview_logs_stream(session_id: str):
    """Sprint 10: SSE stream of sandbox logs, polled every 2 seconds."""
    from fastapi.responses import StreamingResponse as _SR

    async def _generator():
        seen = 0
        idle = 0
        while True:
            try:
                lines = await asyncio.to_thread(_runtime.get_logs, session_id, 500)
                if lines and len(lines) > seen:
                    for line in lines[seen:]:
                        yield f"data: {json.dumps(line)}\n\n"
                    seen = len(lines)
                    idle = 0
                else:
                    idle += 1
                    yield ": heartbeat\n\n"
                    if idle > 60:  # 2 min no new logs → stop
                        break
                await asyncio.sleep(2)
            except Exception:
                break
        yield "event: close\ndata: {}\n\n"

    return _SR(
        _generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
