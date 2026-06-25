"""
preview-service — FastAPI микросервис для live-preview серверных стеков.
Отдельный процесс от src/ (Django): untrusted code изолирован.
Авторизация: X-Internal-Token заголовок (shared secret между Django и этим сервисом).
"""
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel

import settings

app = FastAPI(title="aineron preview-service", version="0.1.0")


def verify_token(x_internal_token: str = Header(...)):
    if x_internal_token != settings.INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "preview-service"}


# ── Preview endpoints (stubs — Sprint 2) ─────────────────────────────────────

class StartRequest(BaseModel):
    project_id: str
    stack: str                        # nextjs | django | telegram_bot | ...
    code_files: dict[str, str]        # path → content
    ttl: int = settings.DEFAULT_TTL
    env: dict[str, str] = {}


class StartResponse(BaseModel):
    session_id: str
    public_url: str
    expires_at: float


class StatusResponse(BaseModel):
    session_id: str
    state: str
    public_url: str | None
    logs_tail: list[str]


@app.post("/preview/start", response_model=StartResponse, dependencies=[Depends(verify_token)])
def preview_start(req: StartRequest):
    # Sprint 2: реализовать E2BRuntime.start()
    raise HTTPException(status_code=501, detail="Not implemented — Sprint 2")


@app.delete("/preview/{session_id}", dependencies=[Depends(verify_token)])
def preview_stop(session_id: str):
    # Sprint 2: реализовать E2BRuntime.stop()
    raise HTTPException(status_code=501, detail="Not implemented — Sprint 2")


@app.get("/preview/{session_id}/status", response_model=StatusResponse, dependencies=[Depends(verify_token)])
def preview_status(session_id: str):
    # Sprint 2: реализовать E2BRuntime.status()
    raise HTTPException(status_code=501, detail="Not implemented — Sprint 2")
