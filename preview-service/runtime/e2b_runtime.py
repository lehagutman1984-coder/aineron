"""
E2BRuntime — Sprint 2+4+5 + Cold-Start Layers L1–L7.

Sprint 2: next.js/python стеки, base image.
Sprint 4: django стек (migrate→uvicorn), custom templates с pre-installed deps.
Sprint 5: telegram_bot — egress restrict + Redis bot lock + delete_webhook.

Cold-start system (2026-06-26):
- L1  Symlink-merge for nextjs: reuse /opt/base/node_modules, delta-install only.
- L2  Warm pool: singleton warmer thread (Redis leader lock) pre-creates sandboxes.
- L3  Generation-triggered prewarm(): create+install during generation, not on click.
- L4  Dep-delta hash skip: _compute_dep_hash() drives skip_install decisions.
- L5  Pause/Resume: stop() pauses non-bot sessions; start() resumes via Sandbox.connect().
- L7  Hit-rate counters: preview:claims:{prewarm|paused|pool|cold}.

SLOTS_KEY accounting (deliberately simple — avoids double-count traps):
- The single INCR at the top of start() is the ONLY slot reservation.
- Pool warmer and prewarm() NEVER touch SLOTS_KEY (they are background overhead).
- Hot claims (prewarm/paused/pool) do NOT incr again and do NOT decr — the top INCR
  stands as the session's slot.
- The reaper reconciles SLOTS_KEY to count(preview:sess:*) + count(paused sessions).

Bugfixes carried forward from Sprint 5:
- Single SLOTS_KEY decrement owner (outer except).
- Bot-lock race guarded by acquired_bot_lock flag.
- Atomic SET nx=True ex=<ttl> for bot lock.
- Reaper reconciles SLOTS_KEY (slot-leak-on-TTL-expiry).
"""
import hashlib
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

# ── Cold-start Redis keys ───────────────────────────────────────────────────
POOL_LIST_PREFIX = "preview:pool:"            # LIST of warm sandbox_ids per stack
POOL_META_PREFIX = "preview:pool:meta:"       # HASH per sandbox_id
POOL_TARGET_PREFIX = "preview:pool:target:"   # desired warm count per stack
WARMER_LEADER_KEY = "preview:warmer:leader"   # SET NX EX — singleton guard
PREWARM_PREFIX = "preview:prewarm:"           # sandbox_id per project (EX 600)
PREWARM_HASH_PREFIX = "preview:prewarmhash:"  # dep_hash per project (EX 600)
PAUSED_PREFIX = "preview:paused:"             # sandbox_id per project
PAUSED_META_PREFIX = "preview:paused:meta:"   # HASH per sandbox_id
CLAIMS_PREFIX = "preview:claims:"             # L7 hit-rate counters

# ── Cold-start tunables (getattr with defaults — settings.py may lag) ────────
POOL_TARGET_DEFAULT = getattr(settings, "POOL_TARGET_DEFAULT", 2)
POOL_MAX_AGE = getattr(settings, "POOL_MAX_AGE", 1200)        # 20 min
PAUSE_ENABLED = getattr(settings, "PAUSE_ENABLED", True)
PAUSE_GRACE = getattr(settings, "PAUSE_GRACE", 1800)          # 30 min
MAX_POOL_SIZE = getattr(settings, "MAX_POOL_SIZE", 6)
PREWARM_TTL = 600                                             # EX for prewarm keys

# Custom template map — env-overridable, empty string = E2B base image
_TEMPLATE_MAP = {
    Stack.NEXTJS: settings.E2B_TEMPLATE_NEXTJS or None,
    Stack.PYTHON: settings.E2B_TEMPLATE_PYTHON or None,
    Stack.DJANGO: settings.E2B_TEMPLATE_DJANGO or None,
    Stack.TELEGRAM_BOT: settings.E2B_TEMPLATE_PYTHON or None,  # reuses python template
}

# Stacks that participate in the warm pool / pause / prewarm machinery.
# Bot sandboxes are intentionally excluded (egress-restricted + lock-bound).
_POOLABLE = (Stack.NEXTJS, Stack.PYTHON, Stack.DJANGO)


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


def _bump_claim(source: str):
    """L7: simple hit-rate counter. source ∈ {prewarm, paused, pool, cold}."""
    try:
        _r.incr(f"{CLAIMS_PREFIX}{source}")
    except Exception:
        pass


# ── L4: dep-delta hash ──────────────────────────────────────────────────────────

def _compute_dep_hash(code_files: dict) -> str:
    """Hash of the dependency manifest. Stable across unrelated code edits so that
    a resumed/prewarmed sandbox can skip reinstall when deps are unchanged."""
    manifest = code_files.get('package.json') or code_files.get('requirements.txt') or ''
    return hashlib.sha256(manifest.encode()).hexdigest()[:16]


# ── File upload ────────────────────────────────────────────────────────────────

def _upload_files(sbx: Sandbox, code_files: dict[str, str]):
    for path, content in code_files.items():
        dest = "/app/" + path.lstrip("/")
        try:
            sbx.files.write(dest, content)
        except Exception as exc:
            logger.warning("E2B file upload failed %s: %s", path, exc)


# ── Stack-specific startup (all run in background via &) ─────────────────────

def _bg_start_nextjs(sbx: Sandbox, port: int, skip_install: bool = False):
    """L1: symlink base node_modules, only delta-install if deps changed.

    skip_install=True is used only when a prewarmed/resumed sandbox already has the
    correct node_modules for the *current* dep hash; we then just (re)start dev.
    """
    if skip_install:
        cmd = (
            "setsid bash -c '"
            "mkdir -p /app && cd /app && "
            f"npm run dev -- -p {port} >> /tmp/preview.log 2>&1"
            "' </dev/null >/dev/null 2>/dev/null &"
        )
    else:
        cmd = (
            "setsid bash -c '"
            "mkdir -p /app && cd /app && "
            # Symlink base node_modules if available (L1 template prebake)
            "ln -sfn /opt/base/node_modules /app/node_modules 2>/dev/null || true; "
            # Delta install: only run if package.json differs from base deps manifest
            "if [ -f package.json ] && [ -f /opt/base/deps.json ] && "
            "diff <(node -p \"JSON.stringify(require('./package.json').dependencies||{})\" 2>/dev/null) "
            "/opt/base/deps.json >/dev/null 2>&1; then "
            "  echo 'Deps unchanged, skipping npm install' >> /tmp/preview.log; "
            "else "
            "  npm install --legacy-peer-deps --prefer-offline >> /tmp/preview.log 2>&1; "
            "fi; "
            f"npm run dev -- -p {port} >> /tmp/preview.log 2>&1"
            "' </dev/null >/dev/null 2>/dev/null &"
        )
    sbx.commands.run(cmd, timeout=30)


def _bg_start_python(sbx: Sandbox, port: int, skip_install: bool = False):
    """pip install + python main.py — fully detached via setsid.

    skip_install=True skips the pip step (deps already present from prewarm/resume).
    """
    if skip_install:
        cmd = (
            "setsid bash -c '"
            "cd /app && "
            "python main.py >> /tmp/preview.log 2>&1"
            "' </dev/null >/dev/null 2>/dev/null &"
        )
    else:
        cmd = (
            "setsid bash -c '"
            "cd /app && "
            "[ -f requirements.txt ] && pip install -r requirements.txt -q >> /tmp/preview.log 2>&1; "
            "python main.py >> /tmp/preview.log 2>&1"
            "' </dev/null >/dev/null 2>/dev/null &"
        )
    sbx.commands.run(cmd, timeout=30)


def _bg_start_django(sbx: Sandbox, port: int, skip_install: bool = False):
    """
    Sprint 4: pip install → manage.py migrate → uvicorn.
    Expects config/asgi.py (standard Django layout) or manage.py at /app/.
    Falls back to `python manage.py runserver 0.0.0.0:{port}` if uvicorn absent.

    skip_install=True skips the pip step (deps already present from prewarm/resume);
    migrate still runs (cheap, idempotent, and the DB/code may have changed).
    """
    install_step = (
        "" if skip_install
        else "[ -f requirements.txt ] && pip install -r requirements.txt -q >> /tmp/preview.log 2>&1; "
    )
    cmd = (
        "setsid bash -c '"
        "cd /app && "
        f"{install_step}"
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


def _bg_start(stack: Stack, sbx: Sandbox, port: int, skip_install: bool = False):
    """Dispatch to the right background-start routine for the stack."""
    if stack == Stack.NEXTJS:
        _bg_start_nextjs(sbx, port, skip_install=skip_install)
    elif stack == Stack.PYTHON:
        _bg_start_python(sbx, port, skip_install=skip_install)
    elif stack == Stack.DJANGO:
        _bg_start_django(sbx, port, skip_install=skip_install)
    elif stack == Stack.TELEGRAM_BOT:
        _bg_start_telegram_bot(sbx)
    else:
        raise ValueError(f"Стек {stack} не поддерживается")


# ── Poll helpers ─────────────────────────────────────────────────────────────

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


# ── L2: warm pool ────────────────────────────────────────────────────────────

def _pool_key(stack: Stack) -> str:
    return f"{POOL_LIST_PREFIX}{stack.value}"


def _pool_target(stack: Stack) -> int:
    """Desired warm count for a stack (Redis override, else default)."""
    try:
        raw = _r.get(f"{POOL_TARGET_PREFIX}{stack.value}")
        if raw is not None:
            return max(0, int(raw))
    except Exception:
        pass
    return POOL_TARGET_DEFAULT


def _create_sandbox_raw(stack: Stack, ttl: int, env: dict) -> Sandbox:
    """Low-level sandbox create with template + bot egress policy.

    Standalone (not a method) so the warmer/prewarm can use it without an instance.
    """
    template = _TEMPLATE_MAP.get(stack)
    kwargs = {
        "api_key": settings.E2B_API_KEY,
        "timeout": ttl,
        "envs": env,
    }
    if template:
        kwargs["template"] = template
    # Sprint 5: restrict egress for bot sandbox to api.telegram.org only.
    if stack == Stack.TELEGRAM_BOT:
        try:
            kwargs["network"] = bot_egress_network()
        except Exception as exc:
            logger.warning("E2B network= not supported in this SDK version: %s", exc)
    return Sandbox.create(**kwargs)


def _spawn_warm_sandbox(stack: Stack):
    """Create one warm sandbox, register it in the pool LIST + meta HASH.

    Does NOT touch SLOTS_KEY — warm sandboxes are background overhead, not sessions.
    Does NOT start a dev server (no project files yet); it is base-image-only and is
    claimed later by start(), which uploads files and starts the server.
    """
    sbx = None
    try:
        sbx = _create_sandbox_raw(stack, POOL_MAX_AGE, env={})
        sid = sbx.sandbox_id
        pipe = _r.pipeline()
        pipe.rpush(_pool_key(stack), sid)
        pipe.hset(f"{POOL_META_PREFIX}{sid}", mapping={
            "stack": stack.value,
            "created_at": str(int(time.time())),
            "dev_ready": "0",
        })
        pipe.expire(f"{POOL_META_PREFIX}{sid}", POOL_MAX_AGE + 120)
        pipe.execute()
        logger.info("Warm sandbox spawned: stack=%s id=%s", stack.value, sid)
    except Exception as exc:
        logger.warning("Warm spawn failed (stack=%s): %s", stack.value, exc)
        if sbx is not None:
            try:
                sbx.kill()
            except Exception:
                pass


def _reap_stale_pool(stack: Stack):
    """Kill + drop warm sandboxes older than POOL_MAX_AGE."""
    try:
        sids = _r.lrange(_pool_key(stack), 0, -1)
    except Exception:
        return
    now = int(time.time())
    for sid in sids:
        try:
            meta = _r.hgetall(f"{POOL_META_PREFIX}{sid}")
            created = int(meta.get("created_at", "0")) if meta else 0
            if not meta or (now - created) > POOL_MAX_AGE:
                # Remove from list first so it can't be claimed mid-reap.
                _r.lrem(_pool_key(stack), 0, sid)
                _r.delete(f"{POOL_META_PREFIX}{sid}")
                try:
                    Sandbox.connect(sid, api_key=settings.E2B_API_KEY).kill()
                except Exception:
                    pass
                logger.info("Reaped stale warm sandbox: %s", sid)
        except Exception as exc:
            logger.debug("Pool reap error for %s: %s", sid, exc)


def _pool_warmer():
    """
    L2 singleton warmer. Holds a Redis leader lock (30s TTL) refreshed every loop so
    only one uvicorn worker actively warms. Each iteration:
      - refresh/acquire leader lock,
      - for each poolable stack: reap stale, then top up toward target (bounded by
        MAX_POOL_SIZE across the stack's list).
    """
    while True:
        try:
            # Leader election: try to take the lock; if held by another worker, wait.
            got = _r.set(WARMER_LEADER_KEY, "leader", nx=True, ex=30)
            if not got:
                time.sleep(10)
                continue

            for stack in _POOLABLE:
                # Skip stacks without a custom template — warming a base image with no
                # pre-baked deps gives little benefit and risks unbounded spend.
                if not _TEMPLATE_MAP.get(stack):
                    continue
                _reap_stale_pool(stack)
                try:
                    have = _r.llen(_pool_key(stack))
                except Exception:
                    have = 0
                target = min(_pool_target(stack), MAX_POOL_SIZE)
                deficit = target - have
                for _ in range(max(0, deficit)):
                    if _r.llen(_pool_key(stack)) >= MAX_POOL_SIZE:
                        break
                    _spawn_warm_sandbox(stack)
                    # Keep the leader lock fresh during slow spawns.
                    _r.expire(WARMER_LEADER_KEY, 30)
        except Exception as exc:
            logger.warning("Pool warmer error: %s", exc)
        # Refresh lock & pace the loop (<30s so the lock never lapses while we lead).
        try:
            _r.expire(WARMER_LEADER_KEY, 30)
        except Exception:
            pass
        time.sleep(15)


def _claim_from_pool(stack: Stack) -> Sandbox | None:
    """LPOP a warm sandbox id and connect. Returns None if pool empty or all stale.

    Loops past stale ids (LPOP next) so one dead entry doesn't starve the caller.
    """
    if stack not in _POOLABLE:
        return None
    for _ in range(5):  # bounded attempts to skip dead entries
        try:
            sid = _r.lpop(_pool_key(stack))
        except Exception:
            return None
        if not sid:
            return None
        try:
            sbx = Sandbox.connect(sid, api_key=settings.E2B_API_KEY)
            _r.delete(f"{POOL_META_PREFIX}{sid}")
            return sbx
        except Exception as exc:
            logger.debug("Pool sandbox %s stale, skipping: %s", sid, exc)
            _r.delete(f"{POOL_META_PREFIX}{sid}")
            continue
    return None


# ── Reaper ───────────────────────────────────────────────────────────────────

def _reaper_loop():
    """
    Slot reaper: reconcile SLOTS_KEY against live+paused session count every 60s.
    Prevents permanent slot leaks when sessions expire via Redis TTL without stop().

    Pool/prewarm sandboxes are intentionally NOT counted — only real user sessions
    (running + paused) hold a slot.
    """
    while True:
        time.sleep(60)
        try:
            running = sum(1 for _ in _r.scan_iter(f"{SESSION_PREFIX}*"))
            # Count paused project keys but NOT their meta hashes. Meta keys live under
            # the "preview:paused:meta:" prefix, so filter those out explicitly.
            paused_count = sum(
                1 for k in _r.scan_iter(f"{PAUSED_PREFIX}*")
                if not k.startswith(PAUSED_META_PREFIX)
            )
            _r.set(SLOTS_KEY, max(0, running + paused_count))
        except Exception as exc:
            logger.warning("Slot reaper error: %s", exc)


# ── E2BRuntime ─────────────────────────────────────────────────────────────────

class E2BRuntime(Runtime):
    """
    e2b Firecracker + port forwarding with L1–L7 cold-start acceleration.
    start() returns in <15s; frontend polls status until RUNNING.
    """

    def __init__(self):
        # Background slot reaper (fixes slot-leak-on-TTL-expiry).
        threading.Thread(target=_reaper_loop, daemon=True, name="slot-reaper").start()
        # L2 warm pool — singleton via Redis leader lock, safe to start in every worker.
        threading.Thread(target=_pool_warmer, daemon=True, name="pool-warmer").start()

    # ── sandbox create (instance wrapper around standalone helper) ──────────────

    def _create_sandbox(self, stack: Stack, ttl: int, env: dict) -> Sandbox:
        """Create E2B sandbox, using custom template + egress policy per stack."""
        return _create_sandbox_raw(stack, ttl, env)

    # ── L3: generation-triggered prewarm ───────────────────────────────────────

    def prewarm(self, project_id: str, code_files: dict[str, str], stack: Stack,
                env: dict[str, str] | None = None) -> str | None:
        """
        Create a sandbox and run the slow dependency install NOW (during generation),
        so the eventual user click only needs file upload + dev-server start.

        Claims a warm pool sandbox if available, else cold-creates. Installs deps but
        does NOT start the dev server. Stores the sandbox id + dep hash in Redis for
        start() to claim. Returns the sandbox id, or None on failure.

        Not used for telegram_bot (lock-bound, egress-restricted, token-via-env only).
        Does NOT touch SLOTS_KEY — prewarm is background prep, not a session.
        """
        if stack not in _POOLABLE:
            return None
        env = env or {}
        sbx = None
        try:
            sbx = _claim_from_pool(stack) or self._create_sandbox(stack, POOL_MAX_AGE, env)
            sid = sbx.sandbox_id

            # Upload the dep manifest so install operates on the real deps.
            manifest_name = "package.json" if stack == Stack.NEXTJS else "requirements.txt"
            manifest = code_files.get(manifest_name)
            if manifest is not None:
                try:
                    sbx.files.write(f"/app/{manifest_name}", manifest)
                except Exception as exc:
                    logger.warning("prewarm manifest write failed: %s", exc)

            # Slow step — runs during generation, not on user click.
            if stack == Stack.NEXTJS:
                install_cmd = (
                    "bash -c 'mkdir -p /app && cd /app && "
                    "ln -sfn /opt/base/node_modules /app/node_modules 2>/dev/null || true; "
                    "[ -f package.json ] && npm install --legacy-peer-deps --prefer-offline "
                    ">> /tmp/preview.log 2>&1; echo prewarmed'"
                )
            else:  # python / django
                install_cmd = (
                    "bash -c 'mkdir -p /app && cd /app && "
                    "[ -f requirements.txt ] && pip install -r requirements.txt -q "
                    ">> /tmp/preview.log 2>&1; echo prewarmed'"
                )
            try:
                res = sbx.commands.run(install_cmd, timeout=300)
                install_ok = getattr(res, 'exit_code', 0) == 0
            except Exception as exc:
                logger.warning("prewarm install failed (project=%s): %s — discarding sandbox", project_id, exc)
                install_ok = False

            if not install_ok:
                try:
                    sbx.kill()
                except Exception:
                    pass
                return None

            dep_hash = _compute_dep_hash(code_files)
            pipe = _r.pipeline()
            pipe.setex(f"{PREWARM_PREFIX}{project_id}", PREWARM_TTL, sid)
            pipe.setex(f"{PREWARM_HASH_PREFIX}{project_id}", PREWARM_TTL, dep_hash)
            pipe.execute()
            logger.info("Prewarmed project=%s sandbox=%s hash=%s", project_id, sid, dep_hash)
            return sid
        except Exception as exc:
            logger.warning("prewarm failed (project=%s): %s", project_id, exc)
            if sbx is not None:
                try:
                    sbx.kill()
                except Exception:
                    pass
            return None

    # ── claim helpers — each returns (sbx, skip_install) or None ────────────────

    def _claim_prewarm(self, project_id: str, new_hash: str):
        """Tier 1: prewarmed sandbox for this project. Atomic GETDEL prevents double-claim.
        Connects AFTER claiming to avoid leaking if connect() fails."""
        try:
            # Atomic claim: winner gets the sid, losers get None
            sid = _r.getdel(f"{PREWARM_PREFIX}{project_id}")
            if not sid:
                return None
            stored_hash = _r.getdel(f"{PREWARM_HASH_PREFIX}{project_id}")
            try:
                sbx = Sandbox.connect(sid, api_key=settings.E2B_API_KEY)
            except Exception as exc:
                logger.warning("prewarm connect failed (project=%s sid=%s): %s — killing orphan", project_id, sid, exc)
                try:
                    Sandbox.connect(sid, api_key=settings.E2B_API_KEY, timeout=5).kill()
                except Exception:
                    pass
                return None
            skip_install = bool(stored_hash and stored_hash == new_hash)
            return sbx, skip_install
        except Exception as exc:
            logger.debug("prewarm claim miss (project=%s): %s", project_id, exc)
            return None

    def _claim_paused(self, project_id: str, new_hash: str):
        """Tier 2: paused sandbox (Sandbox.connect auto-resumes). Atomic GETDEL prevents double-claim."""
        try:
            # Atomic claim: GETDEL so only one concurrent caller gets this sid
            sid = _r.getdel(f"{PAUSED_PREFIX}{project_id}")
            if not sid:
                return None
            meta = _r.hgetall(f"{PAUSED_META_PREFIX}{sid}") or {}
            _r.delete(f"{PAUSED_META_PREFIX}{sid}")
            try:
                sbx = Sandbox.connect(sid, api_key=settings.E2B_API_KEY)  # auto-resumes if paused
            except Exception as exc:
                logger.warning("paused connect failed (project=%s sid=%s): %s — killing orphan", project_id, sid, exc)
                try:
                    Sandbox.connect(sid, api_key=settings.E2B_API_KEY, timeout=5).kill()
                except Exception:
                    pass
                return None
            stored_hash = meta.get("dep_hash", "")
            skip_install = bool(stored_hash and stored_hash == new_hash)
            return sbx, skip_install
        except Exception as exc:
            logger.debug("paused claim miss (project=%s): %s", project_id, exc)
            return None

    def _claim_pool(self, stack: Stack):
        """Tier 3: generic warm pool sandbox. Never skip_install — a pool sandbox holds
        only the base image's /opt/base/node_modules, so the project delta must still
        install (the L1 symlink+delta path in _bg_start_nextjs handles that)."""
        sbx = _claim_from_pool(stack)
        if sbx is None:
            return None
        return sbx, False

    # ── logs ────────────────────────────────────────────────────────────────────

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

    # ── start ───────────────────────────────────────────────────────────────────

    def start(
        self,
        project_id: str,
        code_files: dict[str, str],
        stack: Stack,
        ttl: int = settings.DEFAULT_TTL,
        env: dict[str, str] | None = None,
        db_credentials_enc: str = "",
    ) -> PreviewSession:
        # Slot semaphore — single INCR is the ONLY slot reservation. Hot claims reuse it.
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
                    raise ValueError("TELEGRAM_BOT_TOKEN обязателен для стека telegram_bot")
                ttl = min(ttl, BOT_MAX_TTL)  # cap bot sessions at 15 min
                bot_sha = token_sha256(token)
                lock_key = bot_lock_key(token)
                acquired_bot_lock = bool(
                    _r.set(lock_key, "locked", nx=True, ex=ttl + 60)
                )
                if not acquired_bot_lock:
                    raise RuntimeError(
                        "Этот бот уже запущен в другой сессии. "
                        "Остановите предыдущую сессию перед запуском новой."
                    )

            # ── 4-tier claim order (non-bot stacks only) ────────────────────────
            # Each tier try/excepts internally and returns None on miss → fall through.
            # claim_source ∈ {prewarm, paused, pool, cold}; skip_install per L4 hash.
            claim_source = "cold"
            skip_install = False
            dep_hash = _compute_dep_hash(code_files)

            if stack in _POOLABLE:
                claimed = self._claim_prewarm(project_id, dep_hash)
                if claimed is not None:
                    claim_source = "prewarm"
                else:
                    claimed = self._claim_paused(project_id, dep_hash)
                    if claimed is not None:
                        claim_source = "paused"
                    else:
                        claimed = self._claim_pool(stack)
                        if claimed is not None:
                            claim_source = "pool"
                if claimed is not None:
                    sbx, skip_install = claimed

            # Cold path: no hot claim succeeded (or stack not poolable / bot).
            if sbx is None:
                sbx = self._create_sandbox(stack, ttl, env)
                claim_source = "cold"
                skip_install = False

            _bump_claim(claim_source)  # L7 hit-rate counter

            # Upload project files (overwrites manifests; safe for all claim sources).
            _upload_files(sbx, code_files)

            port = 3000
            _bg_start(stack, sbx, port, skip_install=skip_install)

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
                "db_credentials_enc": db_credentials_enc,
                "bot_sha": bot_sha,
                "dep_hash": dep_hash,
                "claim_source": claim_source,
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
            if acquired_bot_lock and bot_sha:
                try:
                    _r.delete(f"{BOT_LOCK_PREFIX}{bot_sha}")
                except Exception:
                    pass
            _r.decr(SLOTS_KEY)
            raise

    # ── stop (L5: pause before kill for non-bot) ────────────────────────────────

    def stop(self, session_id: str) -> None:
        data = _get_sess(session_id)
        if not data:
            return
        sandbox_id = data.get("internal_sandbox_id")
        stack_val = data.get("stack")
        project_id = data.get("project_id")
        dep_hash = data.get("dep_hash", "")
        is_bot = stack_val == Stack.TELEGRAM_BOT.value

        if sandbox_id:
            paused = False
            # L5: try pause (state-preserving resume later) for non-bot sessions.
            if PAUSE_ENABLED and not is_bot and project_id:
                try:
                    sbx = Sandbox.connect(sandbox_id, api_key=settings.E2B_API_KEY)
                    paused = bool(sbx.pause())
                    if paused:
                        pipe = _r.pipeline()
                        pipe.setex(f"{PAUSED_PREFIX}{project_id}", PAUSE_GRACE, sandbox_id)
                        pipe.hset(f"{PAUSED_META_PREFIX}{sandbox_id}", mapping={
                            "project_id": project_id,
                            "stack": stack_val or "",
                            "dep_hash": dep_hash,
                            "paused_at": str(int(time.time())),
                        })
                        pipe.expire(f"{PAUSED_META_PREFIX}{sandbox_id}", PAUSE_GRACE + 120)
                        pipe.execute()
                        logger.info("Paused session %s → sandbox %s", session_id, sandbox_id)
                except Exception as exc:
                    logger.warning("E2B pause failed %s, falling back to kill: %s", sandbox_id, exc)
            # Kill if not paused (bot sessions, pause disabled, or pause failed).
            if not paused:
                try:
                    sbx = Sandbox.connect(sandbox_id, api_key=settings.E2B_API_KEY)
                    sbx.kill()
                except Exception as exc:
                    logger.warning("E2B kill failed %s: %s", sandbox_id, exc)

        # Sprint 5: release bot lock so the bot can be restarted.
        bot_sha = data.get("bot_sha")
        if bot_sha:
            try:
                _r.delete(f"{BOT_LOCK_PREFIX}{bot_sha}")
            except Exception:
                pass

        deleted = _r.delete(_sess_key(session_id))
        if deleted:
            _r.decr(SLOTS_KEY)  # only decrement if key existed (no double-decrement)

    # ── status ──────────────────────────────────────────────────────────────────

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
