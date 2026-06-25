"""
preview-service — FastAPI микросервис для live-preview серверных стеков.
Отдельный процесс от src/ (Django): untrusted code изолирован.
Авторизация: X-Internal-Token заголовок (shared secret между Django и этим сервисом).
"""
import asyncio
import logging
from functools import partial

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel

import settings
from runtime.base import Stack
from runtime.e2b_runtime import E2BRuntime
from db.proxy import router as db_router

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="aineron preview-service", version="0.2.0")
_runtime = E2BRuntime()
app.include_router(db_router)


def verify_token(x_internal_token: str = Header(...)):
    if x_internal_token != settings.INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "preview-service", "version": "0.2.0"}


# ── Models ────────────────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    project_id: str
    stack: str
    code_files: dict[str, str]
    ttl: int = settings.DEFAULT_TTL
    env: dict[str, str] = {}


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

    loop = asyncio.get_event_loop()
    try:
        session = await loop.run_in_executor(
            None,
            partial(_runtime.start, req.project_id, req.code_files, stack, req.ttl, req.env or {}),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"E2B error: {exc}")

    return StartResponse(
        session_id=session.session_id,
        public_url=session.public_url,
        expires_at=session.expires_at,
        state="starting",
    )


@app.delete("/preview/{session_id}", dependencies=[Depends(verify_token)])
async def preview_stop(session_id: str):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, partial(_runtime.stop, session_id))
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
