from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """SessionAuthentication без проверки CSRF — для DRF API с CORS-защитой."""
    def enforce_csrf(self, request):
        pass


def _blocked_account_response():
    return {
        'error': {
            'message': 'Account is blocked.',
            'type': 'invalid_request_error',
            'code': 'account_blocked',
        }
    }


class ShadowBanAwareJWTAuthentication(JWTAuthentication):
    """
    2026-10-01 (аудит безопасности, MEDIUM, №21): стоковый simplejwt
    JWTAuthentication проверяет только is_active. ShadowBanMiddleware видит
    только сессионных пользователей (request.user там заполняется ДО
    JWT-аутентификации DRF, для JWT-запроса это всегда Anonymous). Телеграм
    Mini App (webapp_auth) выдаёт JWT, и это был единственный путь, где
    забаненный фармер (farm триала с одного IP) продолжал тратить баланс
    после блокировки — тот же класс защиты, что уже есть в
    APIKeyAuthentication, просто не был продублирован сюда.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if getattr(user, 'shadow_banned', False) and not user.has_made_real_payment():
            raise AuthenticationFailed(_blocked_account_response())
        return user


class APIKeyAuthentication(BaseAuthentication):
    """Bearer ak_... аутентификация для /api/v1/ эндпоинтов."""

    def authenticate(self, request):
        # 2026-10-01 (аудит, docs-parity + dev-API): официальный Anthropic SDK
        # шлёт ключ в заголовке x-api-key, не Authorization: Bearer — без этого
        # /v1/messages был недостижим для реального SDK, только для curl с
        # явным Bearer-заголовком (независимо подтверждено двумя агентами ревью).
        api_key_header = request.META.get('HTTP_X_API_KEY', '')
        if api_key_header.startswith('ak_'):
            raw_key = api_key_header
        else:
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if not auth_header.startswith('Bearer ak_'):
                return None  # передаём другим бэкендам (SessionAuthentication)
            raw_key = auth_header[len('Bearer '):]

        from api.models import APIKey
        api_key = APIKey.authenticate(raw_key)
        if api_key is None:
            raise AuthenticationFailed({
                'error': {
                    'message': 'Invalid API key.',
                    'type': 'invalid_request_error',
                    'code': 'invalid_api_key',
                }
            })

        # Ключ не должен обходить блокировки аккаунта: ShadowBanMiddleware и is_active
        # работают только на веб-сессиях, Bearer-пользователь их не видел вовсе - забаненные
        # (фарм триала с одного IP) и деактивированные аккаунты продолжали тратить баланс по API.
        key_user = api_key.user
        if not key_user.is_active or (
            getattr(key_user, 'shadow_banned', False) and not key_user.has_made_real_payment()
        ):
            raise AuthenticationFailed({
                'error': {
                    'message': 'Account is blocked.',
                    'type': 'invalid_request_error',
                    'code': 'account_blocked',
                }
            })

        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=['last_used_at'])

        request.api_key = api_key
        return (api_key.user, api_key)

    def authenticate_header(self, request):
        return 'Bearer realm="aineron.ru API"'
