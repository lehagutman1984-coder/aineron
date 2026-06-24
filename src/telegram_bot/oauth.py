"""
Telegram OAuth backend for django-oauth-toolkit.
Authenticates users via Telegram WebApp initData (HMAC-SHA256).
"""
import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qsl

from django.conf import settings

logger = logging.getLogger(__name__)

INIT_DATA_MAX_AGE_SECONDS = 300


def _validate_init_data(init_data: str) -> dict | None:
    """Validate Telegram WebApp initData. Returns user dict or None."""
    try:
        params = dict(parse_qsl(init_data, keep_blank_values=True))
        hash_value = params.pop('hash', None)
        if not hash_value:
            return None

        # Freshness check — reject stale initData (replay protection)
        auth_date = int(params.get('auth_date', 0))
        if time.time() - auth_date > INIT_DATA_MAX_AGE_SECONDS:
            logger.warning('OAuth: initData expired (auth_date=%s)', auth_date)
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
            logger.warning('OAuth: initData HMAC mismatch')
            return None

        return json.loads(params.get('user', '{}'))
    except Exception as e:
        logger.warning('OAuth: initData validation error: %s', e)
        return None


class TelegramOAuthBackend:
    """
    Authenticate a Django user from Telegram WebApp initData.
    Used by django-oauth-toolkit AUTHENTICATION_BACKENDS.
    """

    def authenticate(self, request, init_data: str = None, **kwargs):
        if not init_data:
            return None
        user_data = _validate_init_data(init_data)
        if not user_data:
            return None

        telegram_id = user_data.get('id')
        if not telegram_id:
            return None

        from telegram_bot.models import TelegramUser
        try:
            tg_user = TelegramUser.objects.select_related('user').get(telegram_id=telegram_id)
            return tg_user.user
        except TelegramUser.DoesNotExist:
            logger.info('OAuth: telegram_id %s has no linked Django user', telegram_id)
            return None

    def get_user(self, user_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
