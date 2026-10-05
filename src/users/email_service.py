from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from django.contrib.sites.models import Site
from django.conf import settings
import uuid
import secrets
import string
import threading  # ДОБАВЛЕНО для асинхронности
from .models import CustomUser
from .email_i18n import get_email_context, is_rtl
import logging

logger = logging.getLogger(__name__)


def generate_verification_token():
    """Генерирует уникальный токен для подтверждения email"""
    return str(uuid.uuid4())


def generate_verification_code():
    """Генерирует 6-значный код подтверждения.

    2026-10-01 (аудит безопасности): secrets.choice вместо random.choice —
    random — не криптографический PRNG, не предназначен для кода, от
    которого зависит доступ к аккаунту. Само по себе это не закрывало
    уязвимость (см. verify_email_token выше) — защита от перебора даётся
    привязкой проверки кода к request.user в ajax_verify_email_code, это —
    отдельное, независимое усиление (defense in depth)."""
    return ''.join(secrets.choice('0123456789') for _ in range(6))


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

        t, lang_code = get_email_context('verification', user.get_language())
        subject = t['subject']
        username = user.username or user.email.split('@')[0]

        # Контекст для шаблона
        context = {
            'username': username,
            'verification_code': verification_code,
            'verification_url': verification_url,
            'email': user.email,
            'domain': domain,
            'site_name': site_name,
            'site_url': site_url,
            't': t,
            'lang_code': lang_code,
            'is_rtl': is_rtl(lang_code),
            'greeting_title': t['greeting_title'].format(username=username),
            'footer_copyright': t['footer_copyright'].format(site_name=site_name),
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
                logger.info(f"[OK] Письмо подтверждения отправлено на {user.email}")
                logger.debug(f"[LINK] Ссылка: {verification_url}")
                logger.debug(f"[CODE] Код: {verification_code}")
            except Exception as e:
                logger.error(f"[ERR] Ошибка отправки письма подтверждения: {e}")

        thread = threading.Thread(target=send_email_thread)
        thread.daemon = True
        thread.start()

        logger.info(f"[EMAIL] Письмо подтверждения поставлено в очередь на отправку для {user.email}")
        return True

    except Exception as e:
        logger.error(f"[ERR] Ошибка при подготовке письма подтверждения: {e}")
        return False

def send_password_reset_email(user, new_password, request):
    """
    Отправляет email с новым паролем (асинхронно)
    """
    try:
        # Получаем текущий сайт
        current_site = Site.objects.get_current()
        site_name = current_site.name

        # Строим URL для входа
        protocol = 'https' if request.is_secure() else 'http'
        domain = request.get_host()
        site_url = f"{protocol}://{domain}"
        login_url = f"{site_url}/users/pages/auth/"

        t, lang_code = get_email_context('password_reset', user.get_language())
        subject = t['subject']
        username = user.username or user.email.split('@')[0]

        # Контекст для шаблона
        context = {
            'username': username,
            'new_password': new_password,
            'login_url': login_url,
            'site_url': site_url,
            'site_name': site_name,
            'email': user.email,
            'domain': domain,
            't': t,
            'lang_code': lang_code,
            'is_rtl': is_rtl(lang_code),
            'greeting_title': t['greeting_title'].format(username=username),
            'greeting_text': t['greeting_text'].format(site_name=site_name),
            'footer_copyright': t['footer_copyright'].format(site_name=site_name),
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

                logger.info(f"[OK] Письмо с новым паролем отправлено на {user.email}")
            except Exception as e:
                logger.error(f"[ERR] Ошибка отправки письма с паролем: {e}")

        # Запускаем отправку в отдельном потоке
        thread = threading.Thread(target=send_email_thread)
        thread.daemon = True
        thread.start()

        logger.info(f"[EMAIL] Письмо с паролем поставлено в очередь на отправку для {user.email}")
        return True

    except Exception as e:
        logger.error(f"[ERR] Ошибка при подготовке письма с паролем: {e}")
        return False


def send_password_changed_notification(user, request):
    """
    Уведомляет о смене пароля из личного кабинета (security-уведомление,
    асинхронно). В отличие от send_password_reset_email — не содержит пароль,
    только предупреждение "это были не вы — свяжитесь с поддержкой".
    """
    try:
        current_site = Site.objects.get_current()
        site_name = current_site.name
        protocol = 'https' if request.is_secure() else 'http'
        domain = request.get_host()
        site_url = f"{protocol}://{domain}"

        t, lang_code = get_email_context('password_changed', user.get_language())
        subject = t['subject']
        username = user.username or user.email.split('@')[0]

        context = {
            'username': username,
            'site_url': site_url,
            'site_name': site_name,
            'email': user.email,
            'changed_at': timezone.now().strftime('%d.%m.%Y %H:%M'),
            't': t,
            'lang_code': lang_code,
            'is_rtl': is_rtl(lang_code),
            'greeting_title': t['greeting_title'].format(username=username),
            'footer_copyright': t['footer_copyright'].format(site_name=site_name),
        }

        html_content = render_to_string('neuro/emails/password_changed_email.html', context)
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
                logger.info(f"[OK] Уведомление о смене пароля отправлено на {user.email}")
            except Exception as e:
                logger.error(f"[ERR] Ошибка отправки уведомления о смене пароля: {e}")

        thread = threading.Thread(target=send_email_thread)
        thread.daemon = True
        thread.start()

        logger.info(f"[EMAIL] Уведомление о смене пароля поставлено в очередь для {user.email}")
        return True

    except Exception as e:
        logger.error(f"[ERR] Ошибка при подготовке уведомления о смене пароля: {e}")
        return False


def send_payment_confirmation_email(user, kind, amount_kopecks, method, tariff_name=None, balance_kopecks=None):
    """
    Подтверждение успешной оплаты/пополнения (асинхронно). Вызывается ПОСЛЕ
    фиксации зачисления (add_kopecks) — сама функция не бросает исключений
    наружу (см. try/except ниже и в потоке), поэтому безопасна для вызова
    из платёжных webhook'ов и Celery-задач без риска сломать сам платёж.

    kind: 'topup' (пополнение баланса) | 'subscription' (покупка/продление тарифа)
    amount_kopecks: сумма операции в копейках
    method: способ оплаты для отображения в письме, например 'Robokassa',
            'Crypto Pay', 'Автопродление'
    tariff_name: имя тарифа, только для kind='subscription'
    balance_kopecks: баланс пользователя после операции; если не передан — берём текущий
    """
    try:
        # format_money, не format_rub: на aineron.net (INTL_MODE=1) суммы в кредитах,
        # не в рублях — та же точка форматирования, что уже использует сам платёжный
        # код (crypto_payments.py/trybit_payments.py в Telegram-уведомлениях).
        from core.money import format_money

        current_site = Site.objects.get_current()
        site_name = current_site.name
        site_url = settings.SITE_URL.rstrip('/')

        if balance_kopecks is None:
            balance_kopecks = user.balance_kopecks

        t, lang_code = get_email_context('payment_confirmation', user.get_language())
        username = user.username or user.email.split('@')[0]

        if kind == 'subscription':
            subject = t['subject_subscription'].format(tariff_name=tariff_name) if tariff_name else t['subject_subscription_generic']
        else:
            subject = t['subject_topup'].format(amount=format_money(amount_kopecks))

        context = {
            'username': username,
            'kind': kind,
            'amount': format_money(amount_kopecks),
            'balance': format_money(balance_kopecks),
            'method': method,
            'tariff_name': tariff_name,
            'site_name': site_name,
            'site_url': site_url,
            't': t,
            'lang_code': lang_code,
            'is_rtl': is_rtl(lang_code),
            'greeting_title': t['greeting_title'].format(username=username),
            'footer_copyright': t['footer_copyright'].format(site_name=site_name),
        }

        html_content = render_to_string('neuro/emails/payment_confirmation.html', context)
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
                logger.info(f"[OK] Письмо об оплате отправлено на {user.email}")
            except Exception as e:
                logger.error(f"[ERR] Ошибка отправки письма об оплате: {e}")

        thread = threading.Thread(target=send_email_thread)
        thread.daemon = True
        thread.start()

        logger.info(f"[EMAIL] Письмо об оплате поставлено в очередь для {user.email}")
        return True

    except Exception as e:
        logger.error(f"[ERR] Ошибка при подготовке письма об оплате: {e}")
        return False


def send_admin_sale_notification(user, kind, amount_kopecks, method, tariff_name=None):
    """
    Короткое уведомление владельцу сайта (settings.SALE_NOTIFICATION_EMAIL) о каждой
    успешной продаже/продлении — аналог механизма dzgpt (users/email_service.py там же).
    2026-10-04: добавлено после того, как владелец не узнал о реальном автопродлении
    клиента без ручного похода в логи/БД.

    Fail-open и асинхронно (отдельный поток, как send_payment_confirmation_email) —
    сбой этого уведомления никогда не должен влиять на сам платёж.
    """
    try:
        admin_email = getattr(settings, 'SALE_NOTIFICATION_EMAIL', '')
        if not admin_email:
            return False

        from core.money import format_money
        kind_label = {'subscription': 'Подписка/продление', 'topup': 'Пополнение баланса'}.get(kind, kind)
        subject = f"[Продажа] {kind_label} — {user.email} — {format_money(amount_kopecks)}"
        lines = [
            f"Пользователь: {user.email} (id {user.id})",
            f"Тип: {kind_label}",
            f"Сумма: {format_money(amount_kopecks)}",
            f"Способ: {method}",
        ]
        if tariff_name:
            lines.append(f"Тариф: {tariff_name}")
        body = '\n'.join(lines)

        def send_email_thread():
            try:
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                    to=[admin_email],
                )
                email.send(fail_silently=False)
                logger.info(f"[OK] Admin-уведомление о продаже отправлено на {admin_email}")
            except Exception as e:
                logger.error(f"[ERR] Ошибка отправки admin-уведомления о продаже: {e}")

        thread = threading.Thread(target=send_email_thread)
        thread.daemon = True
        thread.start()
        return True

    except Exception as e:
        logger.error(f"[ERR] Ошибка при подготовке admin-уведомления о продаже: {e}")
        return False


def send_admin_new_registration(user, method):
    """
    Короткое уведомление владельцу (settings.SALE_NOTIFICATION_EMAIL) о каждой новой
    регистрации — тот же паттерн, что и send_admin_sale_notification. 2026-10-05:
    перенесено с yurist-center (там такое уведомление уже было).

    method: как зарегистрировался — 'email' | 'Google' | 'Yandex' | 'VK' | 'Mail.ru' | 'GitHub'

    Fail-open и асинхронно — сбой этого уведомления не должен ломать регистрацию.
    """
    try:
        admin_email = getattr(settings, 'SALE_NOTIFICATION_EMAIL', '')
        if not admin_email:
            return False

        subject = f"[Регистрация] {user.email} — {method}"
        body = '\n'.join([
            f"Пользователь: {user.email} (id {user.id})",
            f"Способ: {method}",
        ])

        def send_email_thread():
            try:
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                    to=[admin_email],
                )
                email.send(fail_silently=False)
                logger.info(f"[OK] Admin-уведомление о регистрации отправлено на {admin_email}")
            except Exception as e:
                logger.error(f"[ERR] Ошибка отправки admin-уведомления о регистрации: {e}")

        thread = threading.Thread(target=send_email_thread)
        thread.daemon = True
        thread.start()
        return True

    except Exception as e:
        logger.error(f"[ERR] Ошибка при подготовке admin-уведомления о регистрации: {e}")
        return False


def verify_email_token(token):
    """
    Проверяет токен подтверждения email (длинная ссылка из письма).
    Возвращает пользователя или None.

    2026-10-01 (аудит безопасности, CRITICAL): раньше при промахе по длинному
    токену эта функция ПАДАЛА на поиск по короткому 6-значному коду —
    GET /users/api/verify-email/<code>/ анонимный (без login_required), без
    rate-limit где-либо в стеке (ни DRF throttle — это legacy Django view, ни
    nginx limit_req — зон лимитов нет вовсе, ни django-ratelimit). Пространство
    кода 10^6, при ~100 неподтверждённых аккаунтах один хит — это ~10^4
    анонимных GET-запросов без каких-либо ограничений, а находка сразу логинит
    (verify_email() в users/views.py вызывает login() на возвращённом user) —
    практический захват чужого аккаунта перебором. Код теперь проверяется
    ТОЛЬКО через ajax_verify_email_code (users/views.py), который матчит код
    строго на уже залогиненного request.user — там подобрать код для доступа
    к ЧУЖОМУ аккаунту бессмысленно (нужно уже быть залогиненным жертвой).
    Ссылка в письме всегда строится с длинным token, не с кодом (см.
    send_verification_email ниже) — легитимный флоу не затронут.
    """
    # Короткий/пустой token не может быть настоящей ссылкой (UUID4 — 36 симв.)
    # — явно отсекаем, чтобы не словить случайный матч на blank='' у старых
    # записей и не тратить время на заведомо невалидный ввод.
    if not token or len(token) < 32:
        return None
    try:
        user = CustomUser.objects.get(email_verification_token=token)
        user.verify_email()
        logger.info(f"[OK] Email подтвержден по ссылке для {user.email}")
        return user
    except CustomUser.DoesNotExist:
        logger.warning("[ERR] Недействительный токен подтверждения (ссылка)")
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

                logger.info(f"[OK] Тестовое письмо отправлено на {to_email}")
            except Exception as e:
                logger.error(f"[ERR] Ошибка отправки тестового письма: {e}")

        thread = threading.Thread(target=send_email_thread)
        thread.daemon = True
        thread.start()

        logger.info(f"[EMAIL] Тестовое письмо поставлено в очередь на отправку для {to_email}")
        return True

    except Exception as e:
        logger.error(f"[ERR] Ошибка при подготовке тестового письма: {e}")
        return False


def send_welcome_email(user, request):
    """
    Отправляет приветственное письмо после подтверждения email (асинхронно)
    """
    try:
        subject = 'Добро пожаловать!'  # неиспользуемая функция (нигде не вызывается,
        # шаблон 'emails/welcome_email.html' тоже не существует) - не в скоупе
        # локализации 6 реальных писем; строка вместо gettext_lazy только чтобы
        # не тянуть больше неиспользуемый импорт _()

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

                logger.info(f"[OK] Приветственное письмо отправлено на {user.email}")
            except Exception as e:
                logger.error(f"[ERR] Ошибка отправки приветственного письма: {e}")

        thread = threading.Thread(target=send_email_thread)
        thread.daemon = True
        thread.start()

        logger.info(f"[EMAIL] Приветственное письмо поставлено в очередь на отправку для {user.email}")
        return True

    except Exception as e:
        logger.error(f"[ERR] Ошибка при подготовке приветственного письма: {e}")
        return False