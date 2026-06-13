from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
import logging
from django.contrib import messages

logger = logging.getLogger(__name__)


class EmailVerificationMiddleware(MiddlewareMixin):
    """
    Middleware для проверки подтверждения email
    Перенаправляет пользователей с неподтвержденным email на страницу верификации
    """

    def __call__(self, request):
        # Список URL, которые доступны без подтверждения email
        allowed_paths = [
            '/api/',  # DRF API (Next.js frontend)
            '/users/api/auth/',  # Allauth URLs
            '/users/api/ajax/login/',  # AJAX вход
            '/users/api/ajax/register/',  # AJAX регистрация
            '/users/api/ajax/logout/',  # AJAX выход
            '/users/api/ajax/password-reset/',  # Восстановление пароля
            '/users/api/ajax/resend-verification/',  # Повторная отправка
            '/users/api/ajax/verify-email/',  # AJAX проверка кода
            '/users/api/verify-email/',  # Страница верификации и ссылка
            '/admin/',  # Админка
            '/accounts/',  # Allauth
            '/jsi18n/',  # JavaScript i18n
            '/static/',  # Статические файлы
            '/media/',  # Медиа файлы
            '/__debug__/',  # Django Debug Toolbar
            '/users/pages/blocked/',  # Страница блокировки
        ]

        # Исключения для статических файлов и API
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return self.get_response(request)

        # Проверяем, авторизован ли пользователь
        if request.user.is_authenticated:
            # Проверяем, подтвержден ли email
            if hasattr(request.user, 'email_verified') and not request.user.email_verified:

                # Проверяем, разрешен ли доступ к этому пути
                is_allowed = False
                for path in allowed_paths:
                    if request.path.startswith(path):
                        is_allowed = True
                        break

                if not is_allowed:
                    logger.info(f"[RENEW] Перенаправление {request.user.email} на верификацию с {request.path}")

                    # Добавляем сообщение если нужно
                    if request.method == 'GET' and not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        messages.info(
                            request,
                            'Для доступа к этой странице необходимо подтвердить email'
                        )

                    return redirect('users_api:verify_email_page')

        response = self.get_response(request)
        return response


class ShadowBanMiddleware(MiddlewareMixin):
    """
    Middleware для обработки теневого бана
    Перенаправляет забаненных пользователей на специальную страницу
    """

    def __call__(self, request):
        # Список URL, доступных забаненным пользователям
        allowed_paths = [
            '/users/pages/auth/',  # Страница авторизации
            '/users/api/auth/',  # Allauth URLs
            '/users/api/ajax/logout/',  # AJAX выход (чтобы могли выйти)
            '/admin/',  # Админка
            '/accounts/',  # Allauth
            '/jsi18n/',  # JavaScript i18n
            '/static/',  # Статические файлы
            '/media/',  # Медиа файлы
            '/__debug__/',  # Django Debug Toolbar
            '/users/pages/blocked/',  # Страница блокировки (чтобы не было цикла)
        ]

        # Проверяем, авторизован ли пользователь и находится ли в теневом бане
        if request.user.is_authenticated and hasattr(request.user, 'shadow_banned'):
            if request.user.shadow_banned:
                # Добавляем атрибут в request для использования в других частях приложения
                request.shadow_banned = True

                # Проверяем, разрешен ли доступ к этому пути
                is_allowed = False
                for path in allowed_paths:
                    if request.path.startswith(path):
                        is_allowed = True
                        break

                # Если путь не разрешен - перенаправляем на страницу блокировки
                if not is_allowed and request.path != '/users/pages/blocked/':
                    logger.warning(
                        f"[BLOCK] Забаненный пользователь {request.user.email} пытался получить доступ к {request.path}")

                    # Для AJAX запросов возвращаем JSON
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        from django.http import JsonResponse
                        return JsonResponse({
                            'success': False,
                            'error': 'account_blocked',
                            'message': 'Ваш аккаунт заблокирован',
                            'redirect': '/users/pages/blocked/'
                        }, status=403)

                    # ИСПРАВЛЕНО: добавляем namespace
                    return redirect('users_pages:blocked_page')
            else:
                request.shadow_banned = False

        response = self.get_response(request)
        return response


class UserActivityMiddleware(MiddlewareMixin):
    """
    Middleware для отслеживания активности пользователей
    Обновляет last_login и записывает IP-адреса
    """

    def __call__(self, request):
        # Обрабатываем запрос
        response = self.get_response(request)

        # После обработки запроса проверяем пользователя
        if request.user.is_authenticated and not request.user.shadow_banned:
            try:
                from .models import UserIPAddress, UserActivityLog
                from ipware import get_client_ip

                # Получаем IP пользователя
                client_ip, is_routable = get_client_ip(request)

                if client_ip:
                    # Сохраняем IP адрес если его еще нет
                    UserIPAddress.objects.get_or_create(
                        user=request.user,
                        ip_address=client_ip
                    )

                # Обновляем активность при GET запросах (не каждый AJAX)
                if request.method == 'GET' and not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    from django.utils import timezone

                    today = timezone.now().date()

                    # Обновляем или создаем запись в активности
                    UserActivityLog.objects.get_or_create(
                        user=request.user,
                        date=today,
                        defaults={
                            'login_count': 0,
                            'last_login_time': request.user.last_login
                        }
                    )

            except Exception as e:
                # Логируем ошибки, но не прерываем выполнение
                logger.error(f"[ERR] Ошибка в UserActivityMiddleware: {e}")

        return response


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware для добавления заголовков безопасности
    """

    def __call__(self, request):
        response = self.get_response(request)

        # Добавляем заголовки безопасности
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        return response