from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied


class IsEmailVerified(BasePermission):
    """
    Требует подтверждённый email — для эндпоинтов, которые тратят баланс
    (генерация текста/изображений/видео/аудио, sandbox-сессии, batch,
    agent/research) или создают постоянный канал обхода веб-формы
    (создание API-ключей).

    Раньше подтверждение email было только фронтенд-редиректом после
    регистрации/логина (см. (auth)/login, (auth)/register, account/layout.tsx)
    — сам DRF ничего не проверял, и прямой запрос к API с валидной сессией
    (или уже выпущенным API-ключом) обходил его полностью. Обнаружено
    2026-08-30 живым тестом: 102 незавершённых регистрации на aineron.ru
    уже потратили/держат бесплатный баланс, ни разу не подтвердив почту.

    Staff/superuser исключены — они заводятся через createsuperuser, минуя
    публичную регистрацию, и никогда не проходят email_verified=True.
    """

    message = 'Email не подтверждён'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        if getattr(user, 'email_verified', True):
            return True
        raise PermissionDenied({
            'error': {
                'message': 'Подтвердите email, чтобы продолжить — мы отправили код при регистрации.',
                'type': 'permission_error',
                'code': 'email_not_verified',
            }
        })
