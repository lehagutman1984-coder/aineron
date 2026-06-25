"""
E2BRuntime — Sprint 2: live preview через E2B Firecracker sandboxes.
Port forwarding через sbx.get_host(port), без cloudflared.
Egress не ограничен для nextjs/python — npm/pip нужен интернет.
Sprint 4: добавить кастомные templates с pre-installed deps + egress restrict.
"""
import json
import logging
import threading
import time
import urllib.error
import urllib.request
import uuid

import redis as _redis_module
from e2b import Sandbox

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import settings

from .base import Runtime, Stack, SessionState, PreviewSession, SessionStatus

logger = logging.getLogger(__name__)

_r = _redis_module.from_url(settings.REDIS_URL, decode_responses=True)

SESSION_PREFIX = "preview:sess:"
SLOTS_KEY = "preview:slots"
SLOT_TTL = settings.DEFAULT_TTL + 600  # extra buffer so decr always has a key


# ── Redis helpers ──────────────────────────────────────────────────────────────

def _sess_key(session_id: str) -> str:
    return f"{SESSION_PREFIX}{session_id}"


def _set_sess(session_id: str, data: dict, ttl: int):
    _r.setex(_sess_key(session_id), ttl + 300, json.dumps(data))


def _get_sess(session_id: str) -> dict | None:
    raw = _r.get(_sess_key(session_id))
    return json.loads(raw) if raw else None


def _update_sess(session_id: str, **kwargs):
    key = _sess_key(session_id)
    raw = _r.get(key)
    if not raw:
        return
    data = json.loads(raw)
    data.update(kwargs)
    ttl = _r.ttl(key)
    if ttl and ttl > 0:
        _r.setex(key, ttl, json.dumps(data))


# ── Startup helpers ────────────────────────────────────────────────────────────

def _upload_files(sbx: Sandbox, code_files: dict[str, str]):
    for path, content in code_files.items():
        dest = "/app/" + path.lstrip("/")
        try:
            sbx.files.write(dest, content)
        except Exception as exc:
            logger.warning("E2B file upload failed %s: %s", path, exc)


def _bg_start_nextjs(sbx: Sandbox, port: int):
    cmd = (
        "bash -c '"
        "mkdir -p /app && cd /app && "
        "npm install --legacy-peer-deps >> /tmp/preview.log 2>&1 && "
        f"npm run dev -- -p {port} >> /tmp/preview.log 2>&1 "
        "& echo started"
        "'"
    )
    sbx.commands.run(cmd, timeout=10)


def _bg_start_python(sbx: Sandbox, port: int):
    cmd = (
        "bash -c '"
        "cd /app && "
        "pip install -r requirements.txt -q >> /tmp/preview.log 2>&1 && "
        f"python main.py >> /tmp/preview.log 2>&1 "
        "& echo started"
        "'"
    )
    sbx.commands.run(cmd, timeout=10)


def _poll_until_up(session_id: str, public_url: str, timeout: int = 180):
    """Background thread: polls URL, updates state to RUNNING when app responds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(public_url, timeout=5)
            _update_sess(session_id, state=SessionState.RUNNING.value)
            logger.info("E2B preview RUNNING: %s", session_id)
            return
        except (urllib.error.URLError, Exception):
            pass
        time.sleep(5)
    logger.warning("E2B preview timeout waiting for app: %s", session_id)
    _update_sess(session_id, state=SessionState.FAILED.value)


# ── E2BRuntime ─────────────────────────────────────────────────────────────────

class E2BRuntime(Runtime):
    """
    Sprint 2 implementation: e2b Firecracker + port forwarding.
    start() returns in <15s (sandbox create + file upload + background npm/pip).
    Frontend polls status until RUNNING.
    """

    def start(
        self,
        project_id: str,
        code_files: dict[str, str],
        stack: Stack,
        ttl: int = settings.DEFAULT_TTL,
        env: dict[str, str] | None = None,
    ) -> PreviewSession:
        # Slot semaphore
        slots = int(_r.incr(SLOTS_KEY))
        if slots > settings.MAX_CONCURRENT:
            _r.decr(SLOTS_KEY)
            raise RuntimeError(
                f"Превышен лимит одновременных превью ({settings.MAX_CONCURRENT}). Попробуйте позже."
            )

        sbx = None
        try:
            sbx = Sandbox.create(
                api_key=settings.E2B_API_KEY,
                timeout=ttl,
                envs=env or {},
            )

            _upload_files(sbx, code_files)

            port = 3000
            if stack == Stack.NEXTJS:
                _bg_start_nextjs(sbx, port)
            elif stack in (Stack.PYTHON, Stack.DJANGO):
                _bg_start_python(sbx, port)
            else:
                raise ValueError(f"Стек {stack} не поддерживается в Sprint 2")

            public_host = sbx.get_host(port)
            public_url = f"https://{public_host}"
            session_id = str(uuid.uuid4())
            expires_at = time.time() + ttl

            _set_sess(session_id, {
                "session_id": session_id,
                "project_id": project_id,
                "public_url": public_url,
                "internal_sandbox_id": sbx.sandbox_id,
                "expires_at": expires_at,
                "state": SessionState.STARTING.value,
                "logs": [],
            }, ttl)

            # Background thread: wait for app to respond → set RUNNING
            threading.Thread(
                target=_poll_until_up,
                args=(session_id, public_url),
                daemon=True,
            ).start()

            return PreviewSession(
                session_id=session_id,
                project_id=project_id,
                public_url=public_url,
                internal_sandbox_id=sbx.sandbox_id,
                expires_at=expires_at,
            )

        except Exception:
            if sbx:
                try:
                    sbx.kill()
                except Exception:
                    pass
            _r.decr(SLOTS_KEY)
            raise

    def stop(self, session_id: str) -> None:
        data = _get_sess(session_id)
        if not data:
            return
        sandbox_id = data.get("internal_sandbox_id")
        if sandbox_id:
            try:
                sbx = Sandbox.connect(sandbox_id, api_key=settings.E2B_API_KEY)
                sbx.kill()
            except Exception as exc:
                logger.warning("E2B kill failed %s: %s", sandbox_id, exc)
        _r.delete(_sess_key(session_id))
        _r.decr(SLOTS_KEY)

    def status(self, session_id: str) -> SessionStatus:
        data = _get_sess(session_id)
        if not data:
            return SessionStatus(
                session_id=session_id,
                state=SessionState.STOPPED,
                public_url=None,
                logs_tail=[],
            )
        state_str = data.get("state", SessionState.STOPPED.value)
        if time.time() > data.get("expires_at", 0):
            state_str = SessionState.EXPIRED.value
        return SessionStatus(
            session_id=session_id,
            state=SessionState(state_str),
            public_url=data.get("public_url"),
            logs_tail=data.get("logs", []),
        )
