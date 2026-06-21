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
        },
    })
