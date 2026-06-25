"""
E2BRuntime — Sprint 2+4+5: live preview через E2B Firecracker sandboxes.
Port forwarding через sbx.get_host(port), без cloudflared.

Sprint 2: next.js/python стеки, base image.
Sprint 4: django стек (migrate→uvicorn), custom templates с pre-installed deps.
Sprint 5: telegram_bot — egress restrict + Redis bot lock + delete_webhook.

Bugfixes (2026-06-25):
- Double-DECR of SLOTS_KEY: removed early decrements from bot pre-flight; outer
  except is the single decrement owner.
- Bot-lock race: guard lock release with acquired_bot_lock flag so a failed SETNX
  (lock held by another session) does NOT delete the OTHER session's lock.
- Non-atomic SETNX+EXPIRE: replaced with single SET nx=True ex=<ttl> call.
- Slot leak on natural expiry: background reaper thread reconciles SLOTS_KEY every
  60s by scanning active session keys.
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
from .sprint5_bot import (
    BOT_MAX_TTL, BOT_LOCK_PREFIX,
    _BOT_STARTUP_CMD, bot_lock_key, token_sha256, bot_egress_network,
)

logger = logging.getLogger(__name__)

_r = _redis_module.from_url(settings.REDIS_URL, decode_responses=True)

SESSION_PREFIX = "preview:sess:"
SLOTS_KEY = "preview:slots"

# Custom template map — env-overridable, empty string = E2B base image
_TEMPLATE_MAP = {
    Stack.NEXTJS: settings.E2B_TEMPLATE_NEXTJS or None,
    Stack.PYTHON: settings.E2B_TEMPLATE_PYTHON or None,
    Stack.DJANGO: settings.E2B_TEMPLATE_DJANGO or None,
    Stack.TELEGRAM_BOT: settings.E2B_TEMPLATE_PYTHON or None,  # reuses python template
}


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


# ── File upload ────────────────────────────────────────────────────────────────

def _upload_files(sbx: Sandbox, code_files: dict[str, str]):
    for path, content in code_files.items():
        dest = "/app/" + path.lstrip("/")
        try:
            sbx.files.write(dest, content)
        except Exception as exc:
            logger.warning("E2B file upload failed %s: %s", path, exc)


# ── Stack-specific startup (all run in background via &) ─────────────────────

def _bg_start_nextjs(sbx: Sandbox, port: int):
    """npm install + next dev — fully detached via setsid so commands.run() returns immediately."""
    cmd = (
        "setsid bash -c '"
        "mkdir -p /app && cd /app && "
        "npm install --legacy-peer-deps >> /tmp/preview.log 2>&1 && "
        f"npm run dev -- -p {port} >> /tmp/preview.log 2>&1"
        "' </dev/null >/dev/null 2>/dev/null &"
    )
    sbx.commands.run(cmd, timeout=30)


def _bg_start_python(sbx: Sandbox, port: int):
    """pip install + python main.py — fully detached via setsid."""
    cmd = (
        "setsid bash -c '"
        "cd /app && "
        "[ -f requirements.txt ] && pip install -r requirements.txt -q >> /tmp/preview.log 2>&1; "
        f"python main.py >> /tmp/preview.log 2>&1"
        "' </dev/null >/dev/null 2>/dev/null &"
    )
    sbx.commands.run(cmd, timeout=30)


def _bg_start_django(sbx: Sandbox, port: int):
    """
    Sprint 4: pip install → manage.py migrate → uvicorn.
    Expects config/asgi.py (standard Django layout) or manage.py at /app/.
    Falls back to `python manage.py runserver 0.0.0.0:{port}` if uvicorn absent.
    """
    cmd = (
        "setsid bash -c '"
        "cd /app && "
        "[ -f requirements.txt ] && pip install -r requirements.txt -q >> /tmp/preview.log 2>&1; "
        "python manage.py migrate --noinput >> /tmp/preview.log 2>&1; "
        "if python -c \"import uvicorn\" 2>/dev/null; then "
        f"  uvicorn config.asgi:application --host 0.0.0.0 --port {port} >> /tmp/preview.log 2>&1; "
        "else "
        f"  python manage.py runserver 0.0.0.0:{port} >> /tmp/preview.log 2>&1; "
        "fi"
        "' </dev/null >/dev/null 2>/dev/null &"
    )
    sbx.commands.run(cmd, timeout=30)


def _bg_start_telegram_bot(sbx: Sandbox):
    """
    Sprint 5: Tier 2 — run bot with delete_webhook wrapper before polling.
    Token arrives via envs= only, never written to any file.
    """
    sbx.commands.run(_BOT_STARTUP_CMD, timeout=30)


def _poll_until_up(session_id: str, public_url: str, timeout: int = 300):
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
    logger.warning("E2B preview startup timeout: %s", session_id)
    _update_sess(session_id, state=SessionState.FAILED.value)


def _poll_bot_alive(session_id: str, sandbox_id: str | None = None, timeout: int = 120):
    """
    Sprint 5: Check sandbox logs for bot startup success marker.
    Falls back to RUNNING after timeout if no FAILED marker found.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(8)
        if sandbox_id:
            try:
                sbx = Sandbox.connect(sandbox_id, api_key=settings.E2B_API_KEY)
                result = sbx.commands.run("cat /tmp/preview.log 2>/dev/null | tail -20", timeout=5)
                log_text = result.stdout or ""
                if "started" in log_text.lower() or "polling" in log_text.lower():
                    _update_sess(session_id, state=SessionState.RUNNING.value)
                    logger.info("Bot RUNNING: %s", session_id)
                    return
                if "error" in log_text.lower() and "traceback" in log_text.lower():
                    _update_sess(session_id, state=SessionState.FAILED.value)
                    return
            except Exception as exc:
                logger.debug("Bot log check failed %s: %s", session_id, exc)
    # Timeout: assume running (can't know for certain without HTTP)
    data = _get_sess(session_id)
    if data and data.get("state") == SessionState.STARTING.value:
        _update_sess(session_id, state=SessionState.RUNNING.value)


def _reaper_loop():
    """
    Slot reaper: reconcile SLOTS_KEY against actual live session count every 60s.
    Prevents permanent slot leaks when sessions expire via Redis TTL without explicit stop().
    """
    while True:
        time.sleep(60)
        try:
            count = sum(1 for _ in _r.scan_iter(f"{SESSION_PREFIX}*"))
            _r.set(SLOTS_KEY, max(0, count))
        except Exception as exc:
            logger.warning("Slot reaper error: %s", exc)


# ── E2BRuntime ─────────────────────────────────────────────────────────────────

class E2BRuntime(Runtime):
    """
    Sprint 2+4: e2b Firecracker + port forwarding.
    start() returns in <15s (sandbox create + file upload + background startup).
    Frontend polls status until RUNNING.
    """

    def __init__(self):
        # Start background slot reaper (fixes slot-leak-on-TTL-expiry)
        threading.Thread(target=_reaper_loop, daemon=True, name="slot-reaper").start()

    def _create_sandbox(self, stack: Stack, ttl: int, env: dict) -> Sandbox:
        """Create E2B sandbox, using custom template + egress policy per stack."""
        template = _TEMPLATE_MAP.get(stack)
        kwargs = {
            "api_key": settings.E2B_API_KEY,
            "timeout": ttl,
            "envs": env,
        }
        if template:
            kwargs["template"] = template
        # Sprint 5: restrict egress for bot sandbox to api.telegram.org only.
        # network= kwarg was empirically verified working in SPIKE-3 (e2b v2.29.6).
        # If SDK raises TypeError, egress restriction is silently disabled (logged below).
        if stack == Stack.TELEGRAM_BOT:
            try:
                kwargs["network"] = bot_egress_network()
            except Exception as exc:
                logger.warning("E2B network= not supported in this SDK version: %s", exc)
        return Sandbox.create(**kwargs)

    def get_logs(self, session_id: str, lines: int = 200) -> list[str]:
        """Read last N lines of /tmp/preview.log from the running sandbox."""
        sess = _get_sess(session_id)
        if not sess:
            return []
        sandbox_id = sess.get("internal_sandbox_id")
        if not sandbox_id:
            return []
        try:
            sbx = Sandbox.connect(sandbox_id, api_key=settings.E2B_API_KEY)
            raw = sbx.files.read("/tmp/preview.log")
            all_lines = (raw or "").splitlines()
            return all_lines[-lines:]
        except Exception:
            return []

    def start(
        self,
        project_id: str,
        code_files: dict[str, str],
        stack: Stack,
        ttl: int = settings.DEFAULT_TTL,
        env: dict[str, str] | None = None,
        db_credentials_enc: str = "",
    ) -> PreviewSession:
        # Slot semaphore
        slots = int(_r.incr(SLOTS_KEY))
        if slots > settings.MAX_CONCURRENT:
            _r.decr(SLOTS_KEY)
            raise RuntimeError(
                f"Превышен лимит одновременных превью ({settings.MAX_CONCURRENT}). Попробуйте позже."
            )

        sbx = None
        bot_sha = None
        acquired_bot_lock = False  # track whether WE acquired the bot lock
        try:
            env = env or {}

            # Sprint 5: bot-specific pre-flight checks
            if stack == Stack.TELEGRAM_BOT:
                token = env.get("TELEGRAM_BOT_TOKEN", "")
                if not token:
                    # outer except will decrement SLOTS_KEY — do NOT decrement here
                    raise ValueError("TELEGRAM_BOT_TOKEN обязателен для стека telegram_bot")
                ttl = min(ttl, BOT_MAX_TTL)  # cap bot sessions at 15 min
                bot_sha = token_sha256(token)
                lock_key = bot_lock_key(token)
                # Atomic SET: returns True if we acquired, None/False if already held
                acquired_bot_lock = bool(
                    _r.set(lock_key, "locked", nx=True, ex=ttl + 60)
                )
                if not acquired_bot_lock:
                    # outer except decrements SLOTS_KEY; do NOT touch the other session's lock
                    raise RuntimeError(
                        "Этот бот уже запущен в другой сессии. "
                        "Остановите предыдущую сессию перед запуском новой."
                    )

            sbx = self._create_sandbox(stack, ttl, env)

            _upload_files(sbx, code_files)

            port = 3000
            if stack == Stack.NEXTJS:
                _bg_start_nextjs(sbx, port)
            elif stack == Stack.PYTHON:
                _bg_start_python(sbx, port)
            elif stack == Stack.DJANGO:
                _bg_start_django(sbx, port)
            elif stack == Stack.TELEGRAM_BOT:
                _bg_start_telegram_bot(sbx)
            else:
                raise ValueError(f"Стек {stack} не поддерживается")

            if stack == Stack.TELEGRAM_BOT:
                public_url = None
                poll_target = None
            else:
                public_host = sbx.get_host(port)
                public_url = f"https://{public_host}"
                poll_target = public_url

            session_id = str(uuid.uuid4())
            expires_at = time.time() + ttl

            _set_sess(session_id, {
                "session_id": session_id,
                "project_id": project_id,
                "public_url": public_url,
                "internal_sandbox_id": sbx.sandbox_id,
                "started_at": time.time(),
                "expires_at": expires_at,
                "state": SessionState.STARTING.value,
                "logs": [],
                "stack": stack.value,
                # Sprint 7: Fernet-encrypted DBCredentials JSON (empty = no DB binding)
                "db_credentials_enc": db_credentials_enc,
                # Store sha256 so stop() can release bot lock without needing the token
                "bot_sha": bot_sha,
            }, ttl)

            if stack == Stack.TELEGRAM_BOT:
                threading.Thread(
                    target=_poll_bot_alive,
                    args=(session_id, sbx.sandbox_id),
                    daemon=True,
                ).start()
            else:
                threading.Thread(
                    target=_poll_until_up,
                    args=(session_id, poll_target),
                    daemon=True,
                ).start()

            return PreviewSession(
                session_id=session_id,
                project_id=project_id,
                public_url=public_url or "",
                internal_sandbox_id=sbx.sandbox_id,
                expires_at=expires_at,
            )

        except Exception:
            if sbx:
                try:
                    sbx.kill()
                except Exception:
                    pass
            # Only release bot lock if WE acquired it — never touch another session's lock
            if acquired_bot_lock and bot_sha:
                try:
                    _r.delete(f"{BOT_LOCK_PREFIX}{bot_sha}")
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
        # Sprint 5: release bot lock so the bot can be restarted
        bot_sha = data.get("bot_sha")
        if bot_sha:
            try:
                _r.delete(f"{BOT_LOCK_PREFIX}{bot_sha}")
            except Exception:
                pass
        deleted = _r.delete(_sess_key(session_id))
        if deleted:
            _r.decr(SLOTS_KEY)  # only decrement if key existed (no double-decrement)

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
