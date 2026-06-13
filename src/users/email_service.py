from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.sites.models import Site
from django.conf import settings
import uuid
import secrets
import string
import random
import threading  # ДОБАВЛЕНО для асинхронности
from .models import CustomUser
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger(__name__)


def generate_verification_token():
    """Генерирует уникальный токен для подтверждения email"""
    return str(uuid.uuid4())


def generate_verification_code():
    """Генерирует 6-значный код подтверждения"""
    return ''.join(random.choice('0123456789') for _ in range(6))


def generate_random_password(length=12):
    """Генерирует случайный пароль"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


from django.contrib.sites.models import Site

def send_verification_email(user, request):
    """
    Отправляет email с ссылкой и кодом для подтверждения (асинхронно)
    """
    try:
        current_site = Site.objects.get_current()
        site_name = current_site.name
        protocol = 'https' if request.is_secure() else 'http'
        domain = request.get_host()
        site_url = f"{protocol}://{domain}"

        # Генерируем токен для ссылки
        token = generate_verification_token()

        # Генерируем 6-значный код
        verification_code = generate_verification_code()

        # Сохраняем ОБА значения
        user.email_verification_token = token
        user.email_verification_code = verification_code
        user.save(update_fields=['email_verification_token', 'email_verification_code'])

        verification_url = f"{site_url}/users/api/verify-email/{token}/"

        # Тема письма
        subject = _('Подтверждение email адреса')

        # Контекст для шаблона
        context = {
            'username': user.username or user.email.split('@')[0],
            'verification_code': verification_code,
            'verification_url': verification_url,
            'email': user.email,
            'domain': domain,
            'site_name': site_name,
            'site_url': site_url,
        }

        # Рендерим HTML шаблон
        html_content = render_to_string('neuro/emails/verification_email.html', context)
        text_content = strip_tags(html_content)

        def send_email_thread():
            try:
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                    to=[user.email],
                )
                email.attach_alternative(html_content, "text/html")
                email.send(fail_silently=False)
                logger.info(f"✅ Письмо подтверждения отправлено на {user.email}")
                logger.debug(f"🔗 Ссылка: {verification_url}")
                logger.debug(f"🔢 Код: {verification_code}")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки письма подтверждения: {e}")

        thread = threading.Thread(target=send_email_thread)
        thread.daemon = True
        thread.start()

        logger.info(f"📧 Письмо подтверждения поставлено в очередь на отправку для {user.email}")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при подготовке письма подтверждения: {e}")
        return False

def send_password_reset_email(user, new_password, request):
    """
    Отправляет email с новым паролем (асинхронно)
    """
    try:
        # Тема письма
        subject = _('Восстановление пароля')

        # Получаем текущий сайт
        current_site = Site.objects.get_current()
        site_name = current_site.name

        # Строим URL для входа
        protocol = 'https' if request.is_secure() else 'http'
        domain = request.get_host()
        site_url = f"{protocol}://{domain}"
        login_url = f"{site_url}/users/pages/auth/"

        # Контекст для шаблона
        context = {
            'username': user.username or user.email.split('@')[0],
            'new_password': new_password,
            'login_url': login_url,
            'site_url': site_url,
            'site_name': site_name,
            'email': user.email,
            'domain': domain,
        }

        # Рендерим HTML шаблон
        html_content = render_to_string('neuro/emails/password_reset_email.html', context)
        text_content = strip_tags(html_content)

        def send_email_thread():
            """Функция для отправки письма в отдельном потоке"""
            try:
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                    to=[user.email],
                )

                # Прикрепляем HTML версию
                email.attach_alternative(html_content, "text/html")

                email.send(fail_silently=False)

                logger.info(f"✅ Письмо с новым паролем отправлено на {user.email}")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки письма с паролем: {e}")

        # Запускаем отправку в отдельном потоке
        thread = threading.Thread(target=send_email_thread)
        thread.daemon = True
        thread.start()

        logger.info(f"📧 Письмо с паролем поставлено в очередь на отправку для {user.email}")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при подготовке письма с паролем: {e}")
        return False


def verify_email_token(token):
    """
    Проверяет токен ИЛИ код подтверждения email
    Возвращает пользователя или None
    """
    try:
        # Пробуем найти по токену (ссылка)
        user = CustomUser.objects.get(email_verification_token=token)

        # Подтверждаем email
        user.verify_email()

        logger.info(f"✅ Email подтвержден по ссылке для {user.email}")
        return user

    except CustomUser.DoesNotExist:
        try:
            # Пробуем найти по коду (6 цифр)
            user = CustomUser.objects.get(email_verification_code=token)

            # Подтверждаем email
            user.verify_email()

            logger.info(f"✅ Email подтвержден по коду для {user.email}")
            return user

        except CustomUser.DoesNotExist:
            logger.warning(f"❌ Недействительный токен/код подтверждения: {token}")
            return None


def send_test_email(to_email):
    """
    Отправляет тестовое письмо для проверки настроек (асинхронно)
    """
    try:
        subject = 'Тестовое письмо от EroGent'
        html_content = '<h1>Тестовое письмо</h1><p>Если вы видите это письмо, значит настройки email работают корректно!</p>'
        text_content = 'Тестовое письмо. Если вы видите это письмо, значит настройки email работают корректно!'

        def send_email_thread():
            try:
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                    to=[to_email],
                )

                email.attach_alternative(html_content, "text/html")
                email.send(fail_silently=False)

                logger.info(f"✅ Тестовое письмо отправлено на {to_email}")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки тестового письма: {e}")

        thread = threading.Thread(target=send_email_thread)
        thread.daemon = True
        thread.start()

        logger.info(f"📧 Тестовое письмо поставлено в очередь на отправку для {to_email}")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при подготовке тестового письма: {e}")
        return False


def send_welcome_email(user, request):
    """
    Отправляет приветственное письмо после подтверждения email (асинхронно)
    """
    try:
        subject = _('Добро пожаловать!')

        protocol = 'https' if request.is_secure() else 'http'
        domain = request.get_host()
        site_url = f"{protocol}://{domain}/"

        context = {
            'username': user.username or user.email.split('@')[0],
            'site_url': site_url,
            'site_name': getattr(settings, 'SITE_NAME', 'EroGent'),
            'email': user.email,
        }

        html_content = render_to_string('emails/welcome_email.html', context)
        text_content = strip_tags(html_content)

        def send_email_thread():
            try:
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                    to=[user.email],
                )

                email.attach_alternative(html_content, "text/html")
                email.send(fail_silently=False)

                logger.info(f"✅ Приветственное письмо отправлено на {user.email}")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки приветственного письма: {e}")

        thread = threading.Thread(target=send_email_thread)
        thread.daemon = True
        thread.start()

        logger.info(f"📧 Приветственное письмо поставлено в очередь на отправку для {user.email}")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при подготовке приветственного письма: {e}")
        return False