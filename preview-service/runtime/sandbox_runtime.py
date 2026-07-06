"""
Sandbox API runtime — «голые» microVM для публичного продукта /api/v1/sandboxes/.

Отличие от превью (e2b_runtime.start): VM создаётся БЕЗ dev-сервера и без файлов
проекта — клиент сам пишет файлы и выполняет команды через exec. Реюзает warm pool
и низкоуровневые хелперы e2b_runtime.

Слоты: собственный счётчик SANDBOX_SLOTS_KEY (INCR-first), отдельный от превью —
у продуктов разные лимиты и биллинг. Реапер реконсилирует счётчик и добивает
просроченные сессии (страховка: e2b и так убивает VM по timeout=ttl).
"""
import base64
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass

from e2b import Sandbox

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import settings

from .base import Stack
from .e2b_runtime import _r, _claim_from_pool, _TEMPLATE_MAP

logger = logging.getLogger(__name__)

SANDBOX_SESSION_PREFIX = "sandbox:session:"
SANDBOX_SLOTS_KEY = "sandbox:slots"
SANDBOX_LOG = "/tmp/sandbox.log"

SANDBOX_MAX_CONCURRENT = getattr(settings, "SANDBOX_MAX_CONCURRENT", 10)
SANDBOX_EXEC_TIMEOUT_MAX = getattr(settings, "SANDBOX_EXEC_TIMEOUT_MAX", 300)
SANDBOX_OUTPUT_LIMIT_KB = getattr(settings, "SANDBOX_OUTPUT_LIMIT_KB", 256)

# template публичного API → стек существующего пула шаблонов.
# "base" — дефолтный образ e2b (Node 20 + Python 3.11), пула для него нет.
_TEMPLATE_TO_STACK = {
    "python": Stack.PYTHON,
    "nodejs": Stack.NEXTJS,   # шаблон nextjs = Node 20 + прогретые node_modules
    "nextjs": Stack.NEXTJS,
    "django": Stack.DJANGO,
}
ALLOWED_TEMPLATES = ("base",) + tuple(_TEMPLATE_TO_STACK.keys())

_EXEC_RUNNERS = {
    "python": "python3",
    "bash": "bash",
    "node": "node",
}


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    truncated: bool


class SandboxNotFound(Exception):
    pass


# ── session store ─────────────────────────────────────────────────────────────

def _sess_key(session_id: str) -> str:
    return f"{SANDBOX_SESSION_PREFIX}{session_id}"


def _get_sess(session_id: str) -> dict:
    raw = _r.get(_sess_key(session_id))
    if not raw:
        raise SandboxNotFound(session_id)
    return json.loads(raw)


def _connect(session_id: str) -> Sandbox:
    sess = _get_sess(session_id)
    return Sandbox.connect(sess["e2b_id"], api_key=settings.E2B_API_KEY)


# ── output helpers ────────────────────────────────────────────────────────────

def _truncate(text: str) -> tuple[str, bool]:
    limit = SANDBOX_OUTPUT_LIMIT_KB * 1024
    if text and len(text.encode("utf-8", errors="replace")) > limit:
        return text[:limit], True
    return text or "", False


def _run(sbx: Sandbox, command: str, timeout: int, cwd: str) -> ExecResult:
    """commands.run с нормализацией результата: в разных версиях SDK ненулевой
    exit code либо возвращается в результате, либо прилетает исключением с теми же
    атрибутами — приводим оба случая к ExecResult."""
    t0 = time.perf_counter()
    try:
        res = sbx.commands.run(command, timeout=timeout, cwd=cwd)
        exit_code = getattr(res, "exit_code", 0) or 0
        stdout = getattr(res, "stdout", "") or ""
        stderr = getattr(res, "stderr", "") or ""
    except Exception as exc:
        exit_code = getattr(exc, "exit_code", None)
        if exit_code is None:
            # таймаут или сетевая ошибка — 124 по конвенции timeout(1)
            exit_code = 124
        stdout = getattr(exc, "stdout", "") or ""
        stderr = getattr(exc, "stderr", "") or str(exc)
    duration_ms = int((time.perf_counter() - t0) * 1000)
    stdout, t1 = _truncate(stdout)
    stderr, t2 = _truncate(stderr)
    return ExecResult(exit_code=exit_code, stdout=stdout, stderr=stderr,
                      duration_ms=duration_ms, truncated=t1 or t2)


# ── lifecycle ─────────────────────────────────────────────────────────────────

def create_bare(session_id: str, template: str, size: str, ttl: int,
                env: dict[str, str], user_id: str = "") -> dict:
    """Создать пустую VM. Возвращает {e2b_id, public_host, started_at, expires_at,
    claim_source}. Слот резервируется INCR-first и освобождается при любой ошибке."""
    if template not in ALLOWED_TEMPLATES:
        raise ValueError(f"Неизвестный template: {template}")

    slots = int(_r.incr(SANDBOX_SLOTS_KEY))
    if slots > SANDBOX_MAX_CONCURRENT:
        _r.decr(SANDBOX_SLOTS_KEY)
        raise RuntimeError(
            f"Превышен глобальный лимит песочниц ({SANDBOX_MAX_CONCURRENT}). Попробуйте позже."
        )

    sbx = None
    try:
        claim_source = "cold"
        stack = _TEMPLATE_TO_STACK.get(template)
        # Warm pool только для standard: пул создаётся под дефолтные ресурсы шаблона.
        if stack is not None and size == "standard":
            sbx = _claim_from_pool(stack)
            if sbx is not None:
                claim_source = "pool"
                try:
                    sbx.set_timeout(ttl)  # пул создан с POOL_MAX_AGE — сузить до ttl сессии
                except Exception as exc:
                    logger.debug("set_timeout unsupported/failed: %s", exc)
        if sbx is None:
            kwargs = {"api_key": settings.E2B_API_KEY, "timeout": ttl, "envs": env or {}}
            template_id = _TEMPLATE_MAP.get(stack) if stack is not None else None
            if template_id:
                kwargs["template"] = template_id
            sbx = Sandbox.create(**kwargs)

        # env для pool-клейма не попали в create — доносим через профиль шелла.
        if claim_source == "pool" and env:
            exports = "".join(
                f"export {k}={json.dumps(v)}\n" for k, v in env.items()
            )
            try:
                sbx.files.write("/home/user/.sandbox_env", exports)
                sbx.commands.run(
                    "grep -q sandbox_env ~/.bashrc || echo 'source ~/.sandbox_env' >> ~/.bashrc",
                    timeout=10,
                )
            except Exception as exc:
                logger.warning("env injection into pool sandbox failed: %s", exc)

        started_at = time.time()
        public_host = sbx.get_host(3000)
        data = {
            "session_id": session_id,
            "e2b_id": sbx.sandbox_id,
            "template": template,
            "size": size,
            "user_id": user_id,
            "public_host": public_host,
            "started_at": started_at,
            "expires_at": started_at + ttl,
            "claim_source": claim_source,
        }
        _r.setex(_sess_key(session_id), ttl + 120, json.dumps(data))
        logger.info("Sandbox created: sid=%s e2b=%s template=%s source=%s",
                    session_id, sbx.sandbox_id, template, claim_source)
        return data
    except Exception:
        if sbx is not None:
            try:
                sbx.kill()
            except Exception:
                pass
        _r.decr(SANDBOX_SLOTS_KEY)
        raise


def kill(session_id: str) -> dict:
    """Убить VM. Идемпотентно: повторный вызов по несуществующей сессии → ok=True
    с нулевой длительностью (VM уже нет, биллинг закрыт reconcile'ом)."""
    raw = _r.get(_sess_key(session_id))
    if not raw:
        return {"ok": True, "duration_seconds": 0.0, "started_at": 0.0, "already_gone": True}
    data = json.loads(raw)
    started_at = data.get("started_at", time.time())
    duration = max(0.0, time.time() - started_at)
    try:
        Sandbox.connect(data["e2b_id"], api_key=settings.E2B_API_KEY).kill()
    except Exception as exc:
        logger.warning("Sandbox kill failed (sid=%s): %s", session_id, exc)
    deleted = _r.delete(_sess_key(session_id))
    if deleted:
        _r.decr(SANDBOX_SLOTS_KEY)
    return {"ok": True, "duration_seconds": duration, "started_at": started_at,
            "already_gone": False}


def set_ttl(session_id: str, ttl_seconds: int) -> dict:
    """Новый TTL от текущего момента: e2b set_timeout + сдвиг expires_at."""
    data = _get_sess(session_id)
    sbx = Sandbox.connect(data["e2b_id"], api_key=settings.E2B_API_KEY)
    try:
        sbx.set_timeout(ttl_seconds)
    except Exception as exc:
        logger.warning("set_timeout failed (sid=%s): %s", session_id, exc)
    data["expires_at"] = time.time() + ttl_seconds
    _r.setex(_sess_key(session_id), ttl_seconds + 120, json.dumps(data))
    return data


def status(session_id: str) -> dict:
    data = _get_sess(session_id)
    state = "running"
    if time.time() > data.get("expires_at", 0):
        state = "expired"
    return {**data, "state": state}


# ── exec ──────────────────────────────────────────────────────────────────────

def exec_command(session_id: str, command: str, timeout: int = 60,
                 cwd: str = "/home/user", background: bool = False) -> ExecResult:
    timeout = min(max(1, timeout), SANDBOX_EXEC_TIMEOUT_MAX)
    sbx = _connect(session_id)
    if background:
        # Полностью отвязанный процесс, вывод — в общий лог сессии (паттерн _bg_start).
        wrapped = (
            "setsid bash -c "
            + json.dumps(f"{command} >> {SANDBOX_LOG} 2>&1")
            + " </dev/null >/dev/null 2>/dev/null & echo $!"
        )
        res = _run(sbx, wrapped, timeout=15, cwd=cwd)
        return ExecResult(exit_code=0, stdout=res.stdout.strip(), stderr="",
                          duration_ms=res.duration_ms, truncated=False)
    return _run(sbx, command, timeout=timeout, cwd=cwd)


def exec_code(session_id: str, code: str, language: str = "python",
              timeout: int = 60, cwd: str = "/home/user",
              background: bool = False) -> ExecResult:
    runner = _EXEC_RUNNERS.get(language)
    if runner is None:
        raise ValueError(f"Неизвестный language: {language}")
    ext = {"python": "py", "bash": "sh", "node": "js"}[language]
    path = f"/tmp/exec_{uuid.uuid4().hex[:12]}.{ext}"
    sbx = _connect(session_id)
    sbx.files.write(path, code)
    return exec_command(session_id, f"{runner} {path}", timeout=timeout,
                        cwd=cwd, background=background)


# ── files ─────────────────────────────────────────────────────────────────────

def write_files(session_id: str, files: list[dict]) -> int:
    """files: [{path, content, encoding?}]. Возвращает число записанных файлов.
    Валидация путей — на стороне Django; здесь только нормализация."""
    sbx = _connect(session_id)
    written = 0
    for f in files:
        path = f["path"]
        if not path.startswith("/"):
            path = "/home/user/" + path
        content = f.get("content", "")
        if f.get("encoding") == "base64":
            content = base64.b64decode(content)
        sbx.files.write(path, content)
        written += 1
    return written


def read_file(session_id: str, path: str) -> dict:
    sbx = _connect(session_id)
    try:
        content = sbx.files.read(path)
        if isinstance(content, bytes):
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "bytes")
        return {"path": path, "content": content, "encoding": "utf-8"}
    except UnicodeDecodeError:
        raw = sbx.files.read(path, format="bytes")
        return {"path": path,
                "content": base64.b64encode(raw).decode(),
                "encoding": "base64"}


def list_dir(session_id: str, path: str) -> list[dict]:
    sbx = _connect(session_id)
    try:
        entries = sbx.files.list(path)
        return [{"name": getattr(e, "name", str(e)),
                 "type": str(getattr(e, "type", "file")).split(".")[-1].lower()}
                for e in entries]
    except Exception:
        res = _run(sbx, f"ls -1ap {json.dumps(path)}", timeout=10, cwd="/home/user")
        out = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line or line in ("./", "../"):
                continue
            if line.endswith("/"):
                out.append({"name": line[:-1], "type": "dir"})
            else:
                out.append({"name": line, "type": "file"})
        return out


def get_logs(session_id: str, lines: int = 200) -> list[str]:
    """Хвост общего лога сессии (background-процессы пишут в SANDBOX_LOG)."""
    try:
        sbx = _connect(session_id)
        raw = sbx.files.read(SANDBOX_LOG)
        return (raw or "").splitlines()[-lines:]
    except SandboxNotFound:
        raise
    except Exception:
        return []


# ── reaper ────────────────────────────────────────────────────────────────────

def _sandbox_reaper_loop():
    """Каждые 60 с: убить просроченные сессии (страховка поверх e2b timeout) и
    реконсилировать счётчик слотов по фактическому числу сессий."""
    while True:
        time.sleep(60)
        try:
            live = 0
            now = time.time()
            for key in _r.scan_iter(f"{SANDBOX_SESSION_PREFIX}*"):
                raw = _r.get(key)
                if not raw:
                    continue
                data = json.loads(raw)
                if now > data.get("expires_at", 0):
                    try:
                        Sandbox.connect(data["e2b_id"], api_key=settings.E2B_API_KEY).kill()
                    except Exception:
                        pass
                    _r.delete(key)
                else:
                    live += 1
            _r.set(SANDBOX_SLOTS_KEY, live)
        except Exception as exc:
            logger.warning("Sandbox reaper error: %s", exc)


def start_reaper():
    threading.Thread(target=_sandbox_reaper_loop, daemon=True,
                     name="sandbox-reaper").start()
