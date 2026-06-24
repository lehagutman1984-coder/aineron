from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from django.conf import settings


def _make_storage():
    redis_url = getattr(settings, 'TELEGRAM_FSM_REDIS_URL', 'redis://redis:6379/2')
    return RedisStorage.from_url(redis_url)


dp = Dispatcher(storage=_make_storage())

# Роутеры и middleware подключаются при первом запросе, чтобы избежать circular imports
_routers_registered = False


def register_routers():
    global _routers_registered
    if _routers_registered:
        return
    from telegram_bot.middlewares import AuthMiddleware
    from telegram_bot.handlers import (
        menu, onboarding, start, history, files,
        chat, balance, payment, models_cmd, voice, images,
        video_cmd, prompts_cmd, settings_cmd, referral,
        inline, group, admin, projects_cmd,
        search_cmd, export_cmd, img2img_cmd, img2video_cmd, digest_cmd, scenarios_cmd,
        reggroup_cmd, sticker_cmd, memory_cmd,
    )
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.inline_query.middleware(AuthMiddleware())
    dp.include_router(inline.router)        # FIRST — inline queries
    dp.include_router(menu.router)          # SECOND — reply keyboard buttons
    dp.include_router(onboarding.router)    # FSM onboarding callbacks
    dp.include_router(start.router)
    dp.include_router(history.router)
    dp.include_router(files.router)         # photos/docs before generic text
    dp.include_router(projects_cmd.router)  # /projects — Sprint 4.4
    dp.include_router(chat.router)
    dp.include_router(balance.router)
    dp.include_router(payment.router)
    dp.include_router(models_cmd.router)
    dp.include_router(voice.router)
    dp.include_router(images.router)
    dp.include_router(video_cmd.router)
    dp.include_router(prompts_cmd.router)
    dp.include_router(settings_cmd.router)
    dp.include_router(referral.router)
    dp.include_router(admin.router)
    dp.include_router(search_cmd.router)
    dp.include_router(export_cmd.router)
    dp.include_router(img2img_cmd.router)    # Image-to-image FSM
    dp.include_router(img2video_cmd.router)  # Image-to-video FSM
    dp.include_router(digest_cmd.router)      # /digest — daily AI digest
    dp.include_router(scenarios_cmd.router)  # /ai — AI scenarios/agents
    dp.include_router(reggroup_cmd.router)   # /reggroup — register group with org
    dp.include_router(sticker_cmd.router)    # /sticker — AI sticker generation
    dp.include_router(memory_cmd.router)     # /memory — persistent memory management
    dp.include_router(group.router)           # LAST — group chat fallback
    _routers_registered = True
