"""
Sandbox API — namespace /sandbox/* для публичного продукта /api/v1/sandboxes/.

Тонкий HTTP-слой над runtime/sandbox_runtime.py. Авторизация — тот же
X-Internal-Token, что и у /preview/* (вызывает только Django). Квоты, биллинг
и валидация пользовательского ввода — на стороне Django; здесь только лимиты
глобальной ёмкости.
"""
import asyncio
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

import settings
from runtime import sandbox_runtime as srt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


def verify_token(x_internal_token: str = Header(...)):
    if x_internal_token != settings.INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Schemas ───────────────────────────────────────────────────────────────────

class SandboxCreateRequest(BaseModel):
    session_id: str
    template: str = "base"
    size: str = "standard"
    ttl: int = 300
    env: dict[str, str] = {}
    user_id: str = ""


class SandboxCreateResponse(BaseModel):
    session_id: str
    e2b_id: str
    public_host: str
    started_at: float
    expires_at: float
    claim_source: str


class ExecRequest(BaseModel):
    command: str = ""
    code: str = ""
    language: str = "python"
    timeout: int = 60
    cwd: str = "/home/user"
    background: bool = False


class ExecResponse(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    truncated: bool


class FileItem(BaseModel):
    path: str
    content: str
    encoding: str = "utf-8"


class WriteFilesRequest(BaseModel):
    files: list[FileItem]


class KillResponse(BaseModel):
    ok: bool
    duration_seconds: float
    started_at: float
    already_gone: bool = False


def _map_error(exc: Exception) -> HTTPException:
    if isinstance(exc, srt.SandboxNotFound):
        return HTTPException(status_code=404, detail="Sandbox not found or expired")
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=429, detail=str(exc))
    logger.exception("sandbox_api error: %s", exc)
    return HTTPException(status_code=500, detail=f"Sandbox error: {exc}")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/create", response_model=SandboxCreateResponse, dependencies=[Depends(verify_token)])
async def sandbox_create(req: SandboxCreateRequest):
    try:
        data = await asyncio.to_thread(
            srt.create_bare, req.session_id, req.template, req.size, req.ttl,
            req.env or {}, req.user_id,
        )
    except Exception as exc:
        raise _map_error(exc)
    return SandboxCreateResponse(
        session_id=req.session_id,
        e2b_id=data["e2b_id"],
        public_host=data["public_host"],
        started_at=data["started_at"],
        expires_at=data["expires_at"],
        claim_source=data["claim_source"],
    )


@router.get("/{session_id}", dependencies=[Depends(verify_token)])
async def sandbox_status(session_id: str):
    try:
        data = await asyncio.to_thread(srt.status, session_id)
    except Exception as exc:
        raise _map_error(exc)
    # e2b_id наружу не отдаём даже Django — ему он не нужен
    return {k: v for k, v in data.items() if k != "e2b_id"}


@router.post("/{session_id}/exec", response_model=ExecResponse, dependencies=[Depends(verify_token)])
async def sandbox_exec(session_id: str, req: ExecRequest):
    if not req.command and not req.code:
        raise HTTPException(status_code=400, detail="Either command or code is required")
    try:
        if req.code:
            result = await asyncio.to_thread(
                srt.exec_code, session_id, req.code, req.language,
                req.timeout, req.cwd, req.background,
            )
        else:
            result = await asyncio.to_thread(
                srt.exec_command, session_id, req.command,
                req.timeout, req.cwd, req.background,
            )
    except Exception as exc:
        raise _map_error(exc)
    return ExecResponse(**result.__dict__)


@router.post("/{session_id}/files", dependencies=[Depends(verify_token)])
async def sandbox_write_files(session_id: str, req: WriteFilesRequest):
    try:
        written = await asyncio.to_thread(
            srt.write_files, session_id, [f.dict() for f in req.files],
        )
    except Exception as exc:
        raise _map_error(exc)
    return {"written": written}


@router.get("/{session_id}/files", dependencies=[Depends(verify_token)])
async def sandbox_read_file(session_id: str, path: str, op: str = "read"):
    try:
        if op == "list":
            entries = await asyncio.to_thread(srt.list_dir, session_id, path)
            return {"path": path, "entries": entries}
        return await asyncio.to_thread(srt.read_file, session_id, path)
    except Exception as exc:
        raise _map_error(exc)


@router.get("/{session_id}/logs", dependencies=[Depends(verify_token)])
async def sandbox_logs(session_id: str, lines: int = 200):
    try:
        result = await asyncio.to_thread(srt.get_logs, session_id, min(lines, 500))
    except Exception as exc:
        raise _map_error(exc)
    return {"session_id": session_id, "lines": result}


@router.get("/{session_id}/logs/stream", dependencies=[Depends(verify_token)])
async def sandbox_logs_stream(session_id: str):
    """SSE-стрим лога песочницы (паттерн /preview/{id}/logs/stream)."""
    import json as _json
    from fastapi.responses import StreamingResponse as _SR

    async def _generator():
        seen = 0
        idle = 0
        while True:
            try:
                lines = await asyncio.to_thread(srt.get_logs, session_id, 500)
                if lines and len(lines) > seen:
                    for line in lines[seen:]:
                        yield f"data: {_json.dumps(line)}\n\n"
                    seen = len(lines)
                    idle = 0
                else:
                    idle += 1
                    yield ": heartbeat\n\n"
                    if idle > 60:  # 2 мин без новых строк → закрываем
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


class TimeoutRequest(BaseModel):
    ttl: int


@router.post("/{session_id}/timeout", dependencies=[Depends(verify_token)])
async def sandbox_timeout(session_id: str, req: TimeoutRequest):
    try:
        data = await asyncio.to_thread(srt.set_ttl, session_id, req.ttl)
    except Exception as exc:
        raise _map_error(exc)
    return {"ok": True, "expires_at": data["expires_at"]}


@router.delete("/{session_id}", response_model=KillResponse, dependencies=[Depends(verify_token)])
async def sandbox_kill(session_id: str):
    try:
        result = await asyncio.to_thread(srt.kill, session_id)
    except Exception as exc:
        raise _map_error(exc)
    return KillResponse(**result)
