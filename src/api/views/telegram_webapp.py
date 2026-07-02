import hashlib
import hmac
import json
import logging
from urllib.parse import parse_qsl

from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def _validate_telegram_webapp_data(init_data: str):
    """Validate Telegram WebApp initData HMAC. Returns user dict or None."""
    try:
        params = dict(parse_qsl(init_data, keep_blank_values=True))
        hash_value = params.pop('hash', None)
        if not hash_value:
            return None
        data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(params.items()))
        secret_key = hmac.new(
            b'WebAppData',
            settings.TELEGRAM_BOT_TOKEN.encode('utf-8'),
            hashlib.sha256,
        ).digest()
        expected = hmac.new(
            secret_key,
            data_check_string.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, hash_value):
            return None
        user_data = json.loads(params.get('user', '{}'))
        return user_data
    except Exception as e:
        logger.warning(f'WebApp validation error: {e}')
        return None


@api_view(['POST'])
@permission_classes([AllowAny])
def telegram_webapp_auth(request):
    """Exchange Telegram WebApp initData for JWT tokens."""
    init_data = request.data.get('init_data', '')
    if not init_data:
        return Response({'error': 'init_data required'}, status=400)

    user_data = _validate_telegram_webapp_data(init_data)
    if not user_data:
        return Response({'error': 'Invalid initData signature'}, status=401)

    telegram_id = user_data.get('id')
    if not telegram_id:
        return Response({'error': 'No user id in initData'}, status=401)

    try:
        from telegram_bot.models import TelegramUser
        tg_user = TelegramUser.objects.select_related('user').get(telegram_id=telegram_id)
    except Exception:
        return Response(
            {'error': 'Telegram account not linked. Use /start in the bot.'},
            status=404,
        )

    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(tg_user.user)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': {
            'id': tg_user.user.id,
            'email': tg_user.user.email,
            'pages_count': tg_user.user.pages_count,
            'balance_kopecks': tg_user.user.balance_kopecks,
        },
    })


# ═══════════════════════════════════════════════════════════════════════════
# S6 — Mini App 2.0: галерея генераций и виральный шаринг
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
def telegram_webapp_files(request):
    """GET /v1/telegram/webapp/files/ — генерации пользователя для галереи
    Mini App (JWT-аутентификация)."""
    from django.core.paginator import Paginator
    from aitext.models import GeneratedImage

    page = int(request.query_params.get('page', 1))
    from django.db.models import Q
    qs = (
        GeneratedImage.objects
        .filter(Q(message__chat__user=request.user) | Q(user=request.user))
        .exclude(image='')
        .order_by('-created_at')
    )
    paginator = Paginator(qs, 24)
    total_pages = paginator.num_pages
    items = []
    if paginator.count and page <= total_pages:
        for f in paginator.page(page):
            try:
                url = request.build_absolute_uri(f.image.url)
            except Exception:
                continue
            items.append({
                'id': f.id,
                'url': url,
                'prompt': (f.prompt or '')[:100],
                'media_type': getattr(f, 'media_type', 'image') or 'image',
            })
    return Response({
        'files': items,
        'page': page,
        'has_next': page < total_pages,
    })


@api_view(['POST'])
def telegram_prepare_share(request):
    """POST /v1/telegram/webapp/prepare-share/ — savePreparedInlineMessage
    для tg.shareMessage(): поделиться генерацией в любой чат одним тапом.
    В сообщении — кнопка «Создать своё» (deeplink) — виральная петля."""
    import asyncio
    from aitext.models import GeneratedImage

    gen_id = request.data.get('generation_id')
    if not gen_id:
        return Response({'error': 'generation_id required'}, status=400)
    from django.db.models import Q
    gen = GeneratedImage.objects.filter(
        Q(message__chat__user=request.user) | Q(user=request.user), pk=gen_id,
    ).exclude(image='').first()
    if gen is None:
        return Response({'error': 'not found'}, status=404)

    tg = getattr(request.user, 'telegram', None)
    if tg is None:
        return Response({'error': 'Telegram not linked'}, status=400)

    site_url = getattr(settings, 'SITE_URL', 'https://aineron.ru')
    media_url = f"{site_url}{gen.image.url}"
    bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'aineron_bot')
    is_video = getattr(gen, 'media_type', 'image') == 'video'

    async def _prepare():
        from aiogram import Bot
        from aiogram.types import (
            InlineQueryResultPhoto, InlineQueryResultVideo,
            InlineKeyboardMarkup, InlineKeyboardButton,
        )
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        try:
            save = getattr(bot, 'save_prepared_inline_message', None)
            if save is None:
                return None
            markup = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text='Создать своё',
                    url=f'https://t.me/{bot_username}?start=share_{gen.pk}',
                ),
            ]])
            caption = f'Создано в aineron: {(gen.prompt or "")[:150]}'
            if is_video:
                result = InlineQueryResultVideo(
                    id=f'gen{gen.pk}', video_url=media_url, mime_type='video/mp4',
                    thumbnail_url=media_url, title='Видео aineron',
                    caption=caption, reply_markup=markup,
                )
            else:
                result = InlineQueryResultPhoto(
                    id=f'gen{gen.pk}', photo_url=media_url,
                    thumbnail_url=media_url, caption=caption, reply_markup=markup,
                )
            prepared = await save(
                user_id=tg.telegram_id, result=result,
                allow_user_chats=True, allow_group_chats=True,
                allow_bot_chats=True, allow_channel_chats=True,
            )
            return getattr(prepared, 'id', None)
        finally:
            await bot.session.close()

    try:
        prepared_id = asyncio.run(_prepare())
    except Exception as e:
        logger.warning(f'prepare_share failed: {e}')
        prepared_id = None

    if prepared_id is None:
        # Fallback для клиента: обычная share-ссылка
        return Response({
            'prepared_message_id': None,
            'fallback_url': f'https://t.me/share/url?url={media_url}',
        })
    return Response({'prepared_message_id': prepared_id})
