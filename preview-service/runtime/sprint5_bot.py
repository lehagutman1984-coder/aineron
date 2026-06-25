"""
Sprint 5: Telegram Bot preview — security helpers.
Code-complete, not integration-tested (requires a test bot token from @BotFather).

SECURITY INVARIANTS:
1. Bot token NEVER written to files — only passed via Sandbox.create(envs=...)
2. delete_webhook(drop_pending_updates=True) MANDATORY before polling
3. Redis lock: bot_preview:{sha256(token)} prevents double-polling
4. Egress: only api.telegram.org + pypi.org + files.pythonhosted.org
5. Max TTL: 900s (15 min)
"""
import hashlib

BOT_MAX_TTL = 900  # 15 min

# Redis key for bot lock (keyed by sha256 of token, not the token itself)
BOT_LOCK_PREFIX = "bot_preview:"

# delete_webhook wrapper: must run before any polling to avoid 409 conflicts.
# Runs synchronously, then starts bot.py in background.
_BOT_STARTUP_CMD = r"""bash -c '
cd /app
[ -f requirements.txt ] && pip install -r requirements.txt -q >> /tmp/preview.log 2>&1
# Mandatory: delete webhook before polling (aiogram/python-telegram-bot convention)
python -c "
import os, asyncio
token = os.environ.get(\"TELEGRAM_BOT_TOKEN\", \"\")
if token:
    try:
        import aiogram
        bot = aiogram.Bot(token=token)
        asyncio.run(bot.delete_webhook(drop_pending_updates=True))
        asyncio.run(bot.session.close())
    except Exception:
        try:
            import telegram
            b = telegram.Bot(token=token)
            asyncio.run(b.delete_webhook(drop_pending_updates=True))
        except Exception:
            pass
" >> /tmp/preview.log 2>&1
# Start the actual bot
python bot.py >> /tmp/preview.log 2>&1 &
echo started
'"""


def bot_lock_key(token: str) -> str:
    """Returns Redis key for bot lock. Uses sha256 so token never appears in keys."""
    sha = hashlib.sha256(token.encode()).hexdigest()
    return f"{BOT_LOCK_PREFIX}{sha}"


def token_sha256(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def bot_egress_network() -> dict:
    """
    E2B network opts for Telegram Bot sandbox.
    Only allows connections to Telegram API + pip (for install step).
    """
    return {
        "deny_out": lambda ctx: [ctx.all_traffic],
        "allow_out": ["api.telegram.org", "pypi.org", "files.pythonhosted.org"],
    }
