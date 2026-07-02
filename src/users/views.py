import urllib.parse
import json
import hashlib
import logging
import secrets
from django.contrib.sites.models import Site
import string
from aitext.models import Chat
from decimal import Decimal
from .models import ReferralEarning, WithdrawalRequest
from .models import PromoCode, UsedPromoCode, UserSpending
import uuid
import random
from django.db.models import Sum
from datetime import datetime, timedelta
import calendar
from aitext.models import Chat
import time
from datetime import datetime, timedelta
import random
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import login, authenticate, logout, get_user_model  # Добавлен get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from ipware import get_client_ip
from .models import LegalDocument

from .models import (
    CustomUser, UserIPAddress, UserActivityLog, Tariff,
    UserSubscription, PaymentHistory, PageSaleSettings
)
from .forms import CustomUserCreationForm, CustomAuthenticationForm
from .email_service import (
    send_verification_email, verify_email_token,
    send_password_reset_email, generate_random_password
)
from django.conf import settings

logger = logging.getLogger(__name__)
User = get_user_model()  # Теперь это работает


# ========== AJAX API АУТЕНТИФИКАЦИИ ==========

@csrf_exempt
@require_POST
def ajax_login(request):
    """AJAX вход пользователя"""
    try:
        data = json.loads(request.body)
        next_url = data.get('next', '/')
        form = CustomAuthenticationForm(data=data)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)

                client_ip, is_routable = get_client_ip(request)
                if client_ip:
                    UserIPAddress.objects.get_or_create(
                        user=user,
                        ip_address=client_ip
                    )

                today = timezone.now().date()
                activity_log, created = UserActivityLog.objects.get_or_create(
                    user=user,
                    date=today,
                    defaults={
                        'login_count': 1,
                        'last_login_time': timezone.now()
                    }
                )
                if not created:
                    activity_log.increment_login(timezone.now())

                if user.shadow_banned:
                    return JsonResponse({
                        'success': True,
                        'message': 'Ваш аккаунт заблокирован',
                        'shadow_banned': True,
                        'redirect': '/blocked/',
                    })

                if not user.email_verified:
                    return JsonResponse({
                        'success': True,
                        'message': 'Вход выполнен! Подтвердите email.',
                        'redirect': '/verify-email/',
                    })

                return JsonResponse({
                    'success': True,
                    'message': 'Вход выполнен успешно!',
                    'redirect': next_url
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Неверный email или пароль'
                })
        else:
            errors = {}
            for field, field_errors in form.errors.items():
                field_name = 'username' if field == 'username' else 'password'
                errors[field_name] = field_errors[0]

            return JsonResponse({
                'success': False,
                'message': 'Исправьте ошибки в форме',
                'errors': errors
            })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Неверный формат данных'
        })
    except Exception as e:
        logger.error(f"Ошибка в ajax_login: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        })


@csrf_exempt
@require_POST
def ajax_register(request):
    """AJAX регистрация пользователя"""
    try:
        data = json.loads(request.body)
        next_url = data.get('next', '/')
        form_data = {
            'email': data.get('email'),
            'password1': data.get('password'),
            'password2': data.get('confirm_password')
        }

        form = CustomUserCreationForm(form_data)

        if form.is_valid():
            user = form.save()

            # Генерация реферального кода
            import secrets
            import string
            alphabet = string.ascii_uppercase + string.digits
            referral_code = ''.join(secrets.choice(alphabet) for _ in range(8))
            user.referral_code = referral_code

            ref_code = request.session.get('ref_code')
            if ref_code:
                try:
                    referrer = CustomUser.objects.get(referral_code=ref_code)
                    user.referrer = referrer
                    referrer.referral_clicks += 1
                    referrer.save(update_fields=['referral_clicks'])
                    del request.session['ref_code']
                except CustomUser.DoesNotExist:
                    pass

            client_ip, is_routable = get_client_ip(request)
            shadow_banned = False

            if client_ip:
                existing_users_count = UserIPAddress.objects.filter(
                    ip_address=client_ip
                ).values('user').distinct().count()

                if existing_users_count > 0:
                    shadow_banned = True
                    user.shadow_banned = True
                    logger.warning(f"[WARN] Теневой бан для {user.email} - множественные аккаунты с IP {client_ip}")

            if client_ip:
                UserIPAddress.objects.create(user=user, ip_address=client_ip)

            user.save()

            login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            try:
                send_verification_email(user, request)
                email_sent = True
            except Exception as e:
                logger.error(f"[WARN] Ошибка отправки письма: {e}")
                email_sent = False

            if shadow_banned:
                redirect_url = '/blocked/'
                message = 'Регистрация прошла успешно! Ваш аккаунт заблокирован.'
            else:
                # Если требуется подтверждение email, отправляем на страницу верификации
                if settings.ACCOUNT_EMAIL_VERIFICATION == 'mandatory':
                    redirect_url = '/verify-email/'
                    message = 'Регистрация прошла успешно! Проверьте почту для подтверждения.'
                else:
                    redirect_url = next_url
                    message = 'Регистрация прошла успешно!'

            return JsonResponse({
                'success': True,
                'message': message,
                'shadow_banned': shadow_banned,
                'email_sent': email_sent,
                'redirect': redirect_url,
            })
        else:
            errors = {}
            for field, field_errors in form.errors.items():
                field_name = field.replace('password1', 'password').replace('password2', 'confirm_password')
                errors[field_name] = field_errors[0]

            return JsonResponse({
                'success': False,
                'message': 'Исправьте ошибки в форме',
                'errors': errors
            })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Неверный формат данных'
        })
    except Exception as e:
        logger.error(f"Ошибка в ajax_register: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        })

@csrf_exempt
@require_POST
def ajax_password_reset(request):
    """AJAX восстановление пароля"""
    try:
        data = json.loads(request.body)
        email = data.get('email')

        if not email:
            return JsonResponse({
                'success': False,
                'message': 'Введите email'
            })

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Пользователь с таким email не найден'
            })

        new_password = generate_random_password()
        user.set_password(new_password)
        user.save()

        try:
            send_password_reset_email(user, new_password, request)
            return JsonResponse({
                'success': True,
                'message': 'Новый пароль отправлен на вашу почту'
            })
        except Exception as e:
            logger.error(f"Ошибка отправки письма: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Ошибка при отправке письма'
            })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Неверный формат данных'
        })
    except Exception as e:
        logger.error(f"Ошибка в ajax_password_reset: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        })


@csrf_exempt
def ajax_logout(request):
    """Выход пользователя"""
    logout(request)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': 'Вы вышли из системы'
        })
    else:
        messages.success(request, 'Вы вышли из системы.')
        return redirect('/')


# ========== ВЕРИФИКАЦИЯ EMAIL ==========

@login_required
def verify_email_page(request, token=None):
    """Перенаправляет на Next.js-страницу верификации"""
    if request.user.email_verified:
        return redirect('/account/')

    if token:
        return verify_email(request, token)

    return redirect('/verify-email/')


def verify_email(request, token):
    """Подтверждение email через ссылку"""
    user = verify_email_token(token)

    if user:
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Email подтвержден!'})
        return redirect('/account/?verified=1')
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Неверная ссылка'})
        return redirect('/verify-email/?error=invalid_link')


@csrf_exempt
@require_POST
@login_required
def ajax_verify_email_code(request):
    """AJAX проверка кода подтверждения"""
    try:
        data = json.loads(request.body)
        code = data.get('token')

        if not code or len(code) != 6:
            return JsonResponse({
                'success': False,
                'message': 'Введите 6 цифр'
            })

        try:
            user = CustomUser.objects.get(email_verification_code=code)
        except CustomUser.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Неверный код'
            })

        user.verify_email()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        return JsonResponse({
            'success': True,
            'message': 'Email подтвержден!'
        })

    except Exception as e:
        logger.error(f"Ошибка в ajax_verify_email_code: {e}")
        return JsonResponse({'success': False, 'message': 'Ошибка сервера'})


@csrf_exempt
@require_POST
@login_required
def resend_verification_email(request):
    """Повторная отправка письма"""
    try:
        if request.user.email_verified:
            return JsonResponse({
                'success': False,
                'message': 'Email уже подтвержден'
            })

        success = send_verification_email(request.user, request)

        if success:
            return JsonResponse({
                'success': True,
                'message': 'Письмо отправлено'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Ошибка отправки'
            })

    except Exception as e:
        logger.error(f"Ошибка в resend_verification_email: {e}")
        return JsonResponse({'success': False, 'message': 'Ошибка сервера'})


# ========== ПРОВЕРКА СТАТУСА ==========

@login_required
def check_auth_status(request):
    """Проверка статуса авторизации"""
    return JsonResponse({
        'success': True,
        'is_authenticated': request.user.is_authenticated,
        'email_verified': request.user.email_verified,
        'username': request.user.username,
        'email': request.user.email,
        'shadow_banned': request.user.shadow_banned,
        'user_id': request.user.id,
    })


@csrf_exempt
@require_POST
def check_email_exists(request):
    """Проверка существования email"""
    try:
        data = json.loads(request.body)
        email = data.get('email')
        exists = User.objects.filter(email=email).exists()

        return JsonResponse({
            'success': True,
            'exists': exists
        })

    except Exception as e:
        logger.error(f"Ошибка в check_email_exists: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


# ========== СТРАНИЦЫ ==========


# ========== ТАРИФЫ И ПОДПИСКИ ==========

@login_required
def get_tariffs(request):
    try:
        free_tariff = Tariff.objects.filter(is_free=True, is_active=True).first()
        paid_tariffs = Tariff.objects.filter(is_free=False, is_active=True)

        tariffs_data = {
            'free': {
                'id': free_tariff.id if free_tariff else None,
                'name': free_tariff.display_name if free_tariff else 'Бесплатный',
                'pages': free_tariff.pages_count if free_tariff else 10,
                'price': 0,
                'is_free': True
            } if free_tariff else None,
            'paid': [{
                'id': t.id,
                'display_name': t.display_name,
                'pages': t.pages_count,
                'price': float(t.price),
                'description': t.description,
                'duration_days': t.duration_days,
                'is_trial': t.is_trial,
                'next_tariff': {
                    'id': t.next_tariff.id,
                    'display_name': t.next_tariff.display_name,
                    'price': float(t.next_tariff.price)
                } if t.next_tariff else None,
                'unlimited_networks': t.get_unlimited_networks(),
            } for t in paid_tariffs]
        }

        current_tariff = None
        if request.user.tariff:
            current_tariff = {
                'id': request.user.tariff.id,
                'name': request.user.tariff.display_name,
                'pages': request.user.tariff.pages_count,
                'is_free': request.user.tariff.is_free,
                'expires_at': request.user.active_subscription.expires_at.isoformat() if request.user.active_subscription else None,
                'days_left': request.user.active_subscription.days_until_expiration() if request.user.active_subscription else None
            }

        return JsonResponse({
            'success': True,
            'tariffs': tariffs_data,
            'current_tariff': current_tariff
        })
    except Exception as e:
        logger.error(f"Ошибка получения тарифов: {e}")
        return JsonResponse({'success': False, 'message': 'Не удалось загрузить тарифы'}, status=500)

@login_required
def get_subscription_status(request):
    """Статус подписки пользователя"""
    try:
        user = request.user
        subscription = user.active_subscription

        data = {
            'success': True,
            'pages_count': user.pages_count,
            'tariff_name': user.tariff.display_name if user.tariff else 'Бесплатный',
            'is_free': user.tariff.is_free if user.tariff else True,
        }

        if subscription:
            data.update({
                'has_subscription': True,
                'expires_at': subscription.expires_at.isoformat() if subscription.expires_at else None,
                'days_left': subscription.days_until_expiration(),
                'auto_renew': subscription.auto_renew,
                'status': subscription.status
            })
        else:
            data['has_subscription'] = False

        return JsonResponse(data)

    except Exception as e:
        logger.error(f"Ошибка получения статуса: {e}")
        return JsonResponse({'success': False, 'message': 'Не удалось загрузить статус'}, status=500)


# ========== ИНТЕГРАЦИЯ С ROBOKASSA ==========

@login_required
@require_POST
def create_robokassa_payment(request):
    """
    Создание платежа в Robokassa для покупки тарифа
    """
    try:
        data = json.loads(request.body)
        tariff_id = data.get('tariff_id')

        tariff = Tariff.objects.get(id=tariff_id, is_active=True, is_free=False)

        inv_id = int(time.time() * 1000) % 10000000 + random.randint(1, 1000)

        merchant_login = settings.ROBOKASSA_LOGIN
        password_1 = settings.ROBOKASSA_PASS1

        out_sum = f"{float(tariff.price):.2f}"
        description = f"Оплата тарифа {tariff.display_name}"

        # Формируем чек (без пробелов и лишних символов)
        receipt_data = {
            "items": [
                {
                    "name": tariff.display_name[:128],
                    "quantity": 1,
                    "sum": float(tariff.price),
                    "tax": "none"
                }
            ]
        }
        receipt_json = json.dumps(receipt_data, separators=(',', ':'), ensure_ascii=False)
        # НЕ URL-кодируем Receipt для подписи (для POST-запроса)
        signature_str = f"{merchant_login}:{out_sum}:{inv_id}:{receipt_json}:{password_1}"
        signature = hashlib.md5(signature_str.encode('cp1251')).hexdigest()

        logger.info(f"[PAY] Создание платежа: InvId={inv_id}, сумма={out_sum}, подпись={signature}")
        logger.info(f"[DATA] Receipt JSON: {receipt_json}")

        from core.money import rub_to_kopecks
        payment = PaymentHistory.objects.create(
            user=request.user,
            payment_type='subscription',
            tariff=tariff,
            invoice_id=str(inv_id),
            amount=tariff.price,
            amount_kopecks=rub_to_kopecks(tariff.price),
            pages_count=tariff.pages_count,
            status='pending',
            description=description,
            parent_payment=None
        )

        robokassa_url = "https://auth.robokassa.ru/Merchant/Index.aspx"
        success_url = f"{settings.SITE_URL}/users/pages/payment-success/"
        fail_url = f"{settings.SITE_URL}/users/pages/payment-fail/"

        form_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Оплата через Robokassa</title>
        </head>
        <body>
            <form id="robokassa_form" action="{robokassa_url}" method="POST">
                <input type="hidden" name="MerchantLogin" value="{merchant_login}">
                <input type="hidden" name="OutSum" value="{out_sum}">
                <input type="hidden" name="InvId" value="{inv_id}">
                <input type="hidden" name="Description" value="{description}">
                <input type="hidden" name="SignatureValue" value="{signature}">
                <input type="hidden" name="IsTest" value="{settings.ROBOKASSA_TEST_MODE}">
                <input type="hidden" name="Culture" value="ru">
                <input type="hidden" name="Encoding" value="utf-8">
                <input type="hidden" name="SuccessURL" value="{success_url}">
                <input type="hidden" name="FailURL" value="{fail_url}">
                <input type="hidden" name="Recurring" value="true">
                <input type="hidden" name="Receipt" value='{receipt_json}'>
            </form>
            <script type="text/javascript">
                document.getElementById('robokassa_form').submit();
            </script>
        </body>
        </html>
        """

        return JsonResponse({
            'success': True,
            'form_html': form_html,
            'invoice_id': inv_id,
            'payment_id': payment.id
        })

    except Exception as e:
        logger.error(f"[ERR] Ошибка создания платежа: {e}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
def payment_success(request):
    """Обработка успешного платежа (Result URL)"""
    logger.info("=" * 50)
    logger.info("[RECV] RESULT URL CALLED")

    if request.method == 'POST':
        out_sum = request.POST.get('OutSum')
        inv_id = request.POST.get('InvId')
        signature = request.POST.get('SignatureValue')

        password_2 = settings.ROBOKASSA_PASS2
        signature_str = f"{out_sum}:{inv_id}:{password_2}"
        expected_signature = hashlib.md5(signature_str.encode()).hexdigest().upper()

        if signature.upper() == expected_signature:
            try:
                payment = PaymentHistory.objects.get(invoice_id=inv_id)

                if payment.status == 'success':
                    logger.info(f"[WARN] Платеж {inv_id} уже был обработан")
                    return HttpResponse(f"OK{inv_id}")

                payment.status = 'success'
                payment.paid_at = datetime.now()
                payment.save()

                user = payment.user

                if payment.payment_type == 'subscription':
                    tariff = payment.tariff
                    if not tariff:
                        logger.error(f"[ERR] Для платежа {inv_id} не указан тариф")
                        return HttpResponse(f"OK{inv_id}")

                    if user.active_subscription:
                        subscription = user.active_subscription
                        subscription.expires_at = datetime.now() + timedelta(days=tariff.duration_days)
                        subscription.tariff = tariff
                        subscription.robokassa_invoice_id = inv_id
                        subscription.status = 'active'
                        subscription.is_active = True
                        subscription.save()
                        logger.info(f"[RENEW] Продление подписки для {user.email} +{tariff.pages_count} страниц")
                    else:
                        subscription = UserSubscription.objects.create(
                            user=user,
                            tariff=tariff,
                            expires_at=datetime.now() + timedelta(days=tariff.duration_days),
                            auto_renew=True,
                            robokassa_invoice_id=inv_id,
                            status='active',
                            is_active=True
                        )
                        user.active_subscription = subscription

                    user.tariff = tariff
                    user.save()

                    # Начисляем баланс атомарно, идемпотентно по invoice_id (защита от повтора вебхука)
                    user.add_kopecks(tariff.balance_grant_kopecks, type='subscription', reference=inv_id)
                    user.refresh_from_db(fields=['balance_kopecks', 'pages_count'])
                    logger.info(f"[PAY] У пользователя {user.email} теперь {user.pages_count} страниц")

                    # ========== РЕФЕРАЛЬНЫЙ БОНУС ==========
                    if user.referrer:
                        referrer = user.referrer
                        if referrer.can_convert_to_rub and tariff.referral_bonus > 0:
                            referrer.rub_balance += Decimal(str(tariff.referral_bonus))
                            referrer.save(update_fields=['rub_balance'])
                            amount_rub = tariff.referral_bonus
                            amount_stars = 0
                            logger.info(f"[PAY] Рефералу {referrer.email} начислено {tariff.referral_bonus} руб за покупку {tariff.display_name} пользователем {user.email}")
                        else:
                            referrer.add_kopecks(
                                tariff.referral_bonus_kopecks, type='referral',
                                reference=f'{inv_id}:referral',
                            )
                            amount_rub = 0
                            amount_stars = tariff.referral_bonus_stars
                            logger.info(f" зв. Рефералу {referrer.email} начислено {tariff.referral_bonus_stars} звёзд за покупку {tariff.display_name} пользователем {user.email}")

                        if amount_rub > 0 or amount_stars > 0:
                            ReferralEarning.objects.create(
                                user=referrer,
                                amount_rub=amount_rub,
                                amount_stars=amount_stars,
                                tariff=tariff,
                                description=f'Бонус за приглашение {user.email} (тариф {tariff.display_name})'
                            )

                elif payment.payment_type == 'pages':
                    user.add_kopecks(payment.pages_count * 100, type='topup', reference=inv_id)
                    user.refresh_from_db(fields=['balance_kopecks', 'pages_count'])
                    logger.info(f"[OK] Пользователь {user.email} купил {payment.pages_count} страниц, теперь всего: {user.pages_count}")

                # ── Telegram-уведомление об успешной оплате ──
                try:
                    from telegram_bot.notify import notify_user
                    from core.money import format_rub
                    tg = getattr(user, 'telegram', None)
                    if tg:
                        if payment.payment_type == 'pages':
                            msg = (
                                f"<b>Оплата прошла успешно!</b>\n\n"
                                f"Начислено: <b>{format_rub(payment.pages_count * 100)}</b>\n"
                                f"Баланс: <b>{format_rub(user.balance_kopecks)}</b>"
                            )
                        else:
                            tname = payment.tariff.display_name if payment.tariff else '—'
                            msg = (
                                f"<b>Подписка активирована!</b>\n\n"
                                f"Тариф: <b>{tname}</b>\n"
                                f"Баланс: <b>{format_rub(user.balance_kopecks)}</b>"
                            )
                        notify_user(tg.telegram_id, msg)
                except Exception as tg_err:
                    logger.warning(f"[WARN] Telegram notify failed: {tg_err}")

                return HttpResponse(f"OK{inv_id}")

            except PaymentHistory.DoesNotExist:
                logger.error(f"[ERR] Платеж {inv_id} не найден")
                return HttpResponse(f"Payment {inv_id} not found", status=404)
            except Exception as e:
                logger.error(f"[ERR] Ошибка: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return HttpResponse("Error", status=500)
        else:
            logger.error("[ERR] Неверная подпись")
            return HttpResponse("Invalid signature", status=400)

    return HttpResponse("Invalid request method", status=400)


def payment_fail(request):
    """Обработка неуспешного платежа"""
    inv_id = request.GET.get('InvId') or request.POST.get('InvId')

    logger.info(f"[ERR] Платеж отменен: InvId={inv_id}")

    if inv_id:
        try:
            payment = PaymentHistory.objects.get(invoice_id=inv_id)
            payment.status = 'failed'
            payment.save()
        except PaymentHistory.DoesNotExist:
            pass

    return redirect('/users/pages/pricing/?payment=failed')


def payment_fail_page(request):
    """
    Страница неуспешной оплаты (GET редирект от Robokassa)
    """
    inv_id = request.GET.get('InvId')

    logger.info(f"[RECV] Fail page: GET запрос, InvId={inv_id}")

    if inv_id:
        try:
            payment = PaymentHistory.objects.get(invoice_id=inv_id)
            payment.status = 'failed'
            payment.save()

            if payment.payment_type == 'subscription':
                messages.error(request, f'Оплата тарифа {payment.tariff.display_name} не прошла. Попробуйте снова.')
            elif payment.payment_type == 'pages':
                messages.error(request, f'Оплата {payment.pages_count} страниц не прошла. Попробуйте снова.')
            else:
                messages.error(request, 'Оплата не прошла. Попробуйте снова.')
        except PaymentHistory.DoesNotExist:
            messages.error(request, 'Оплата не прошла. Попробуйте снова или выберите другой способ оплаты.')
    else:
        messages.error(request, 'Оплата не прошла. Попробуйте снова или выберите другой способ оплаты.')

    redirect_url = '/payment-fail/'
    if inv_id:
        redirect_url += f'?InvId={inv_id}'
    return redirect(redirect_url)


# ========== РАБОТА СО СТРАНИЦАМИ ==========

@login_required
def get_page_sale_settings(request):
    """Настройки продажи страниц"""
    try:
        settings = PageSaleSettings.get_settings()
        return JsonResponse({
            'success': True,
            'price_per_page': str(settings.price_per_page),
            'min_pages': settings.min_pages_for_purchase,
            'max_pages': settings.max_pages_for_purchase,
            'is_active': settings.is_active
        })
    except Exception as e:
        logger.error(f"Ошибка получения настроек: {e}")
        return JsonResponse({'success': False, 'message': 'Не удалось загрузить настройки'}, status=500)

@login_required
@require_POST
def buy_pages(request):
    """
    Покупка дополнительных страниц через Robokassa
    """
    try:
        data = json.loads(request.body)
        pages_to_buy = int(data.get('pages', 0))

        if pages_to_buy <= 0:
            return JsonResponse({
                'success': False,
                'message': 'Укажите количество звезд'
            }, status=400)

        page_settings = PageSaleSettings.get_settings()

        if not page_settings.is_active:
            return JsonResponse({
                'success': False,
                'message': 'Продажа звезд временно недоступна'
            }, status=400)

        if pages_to_buy < page_settings.min_pages_for_purchase:
            return JsonResponse({
                'success': False,
                'message': f'Минимальное количество: {page_settings.min_pages_for_purchase} звезд.'
            }, status=400)

        if pages_to_buy > page_settings.max_pages_for_purchase:
            return JsonResponse({
                'success': False,
                'message': f'Максимальное количество: {page_settings.max_pages_for_purchase} звезд.'
            }, status=400)

        total_price = pages_to_buy * page_settings.price_per_page

        inv_id = int(time.time() * 1000) % 10000000 + random.randint(1, 1000)

        merchant_login = settings.ROBOKASSA_LOGIN
        password_1 = settings.ROBOKASSA_PASS1

        out_sum = f"{float(total_price):.2f}"
        description = f"Покупка {pages_to_buy} звезд"

        # [OK] Формируем чек
        receipt_data = {
            "items": [
                {
                    "name": f"Покупка звезд в кол-ве: ({pages_to_buy} шт.)"[:128],
                    "quantity": pages_to_buy,
                    "sum": float(total_price),
                    "tax": "none"
                }
            ]
        }

        receipt_json = json.dumps(
            receipt_data,
            separators=(',', ':'),
            ensure_ascii=False
        )

        # [OK] ВАЖНО: подпись с Receipt и UTF-8
        signature_str = f"{merchant_login}:{out_sum}:{inv_id}:{receipt_json}:{password_1}"
        signature = hashlib.md5(signature_str.encode('utf-8')).hexdigest()

        logger.info(f"[PAY] Создание платежа: InvId={inv_id}, сумма={out_sum}")
        logger.info(f"[DATA] Receipt: {receipt_json}")
        logger.info(f"[SEC] Signature: {signature_str}")

        from core.money import rub_to_kopecks
        payment = PaymentHistory.objects.create(
            user=request.user,
            payment_type='pages',
            invoice_id=str(inv_id),
            amount=total_price,
            amount_kopecks=rub_to_kopecks(total_price),
            pages_count=pages_to_buy,
            status='pending',
            description=description,
            tariff=None,
            subscription=None,
            parent_payment=None
        )

        robokassa_url = "https://auth.robokassa.ru/Merchant/Index.aspx"

        success_url = f"{settings.SITE_URL}/users/pages/payment-success/"
        fail_url = f"{settings.SITE_URL}/users/pages/payment-fail/"

        form_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Оплата через Robokassa</title>
        </head>
        <body>
            <form id="robokassa_form" action="{robokassa_url}" method="POST">
                <input type="hidden" name="MerchantLogin" value="{merchant_login}">
                <input type="hidden" name="OutSum" value="{out_sum}">
                <input type="hidden" name="InvId" value="{inv_id}">
                <input type="hidden" name="Description" value="{description}">
                <input type="hidden" name="SignatureValue" value="{signature}">
                <input type="hidden" name="IsTest" value="{settings.ROBOKASSA_TEST_MODE}">
                <input type="hidden" name="Culture" value="ru">
                <input type="hidden" name="Encoding" value="utf-8">
                <input type="hidden" name="SuccessURL" value="{success_url}">
                <input type="hidden" name="FailURL" value="{fail_url}">
                <input type="hidden" name="Receipt" value='{receipt_json}'>
            </form>
            <script>
                document.getElementById('robokassa_form').submit();
            </script>
        </body>
        </html>
        """

        return JsonResponse({
            'success': True,
            'form_html': form_html,
            'invoice_id': inv_id,
            'payment_id': payment.id,
            'total_price': float(total_price),
            'pages_bought': pages_to_buy
        })

    except Exception as e:
        logger.error(f"[ERR] Ошибка создания платежа: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


# ========== УПРАВЛЕНИЕ АВТОПРОДЛЕНИЕМ ==========

@login_required
@require_POST
def send_renewal_confirmation_code(request):
    """
    Отправка кода подтверждения для изменения автопродления
    """
    try:
        data = json.loads(request.body)
        action = data.get('action')  # 'enable' или 'disable'

        if action not in ['enable', 'disable']:
            return JsonResponse({
                'success': False,
                'message': 'Некорректное действие'
            }, status=400)

        user = request.user

        # Генерируем 6-значный код
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])

        # Сохраняем код в сессии
        request.session['renewal_code'] = code
        request.session['renewal_action'] = action
        request.session['renewal_code_expires'] = (timezone.now() + timedelta(minutes=10)).isoformat()

        # Получаем имя сайта из модели Site
        current_site = Site.objects.get_current()
        site_name = current_site.name

        # Отправляем код на почту
        subject = 'Код подтверждения для изменения автопродления'

        context = {
            'username': user.username or user.email.split('@')[0],
            'code': code,
            'action': 'включения' if action == 'enable' else 'отключения',
            'site_name': site_name,
            'site_url': settings.SITE_URL,
        }

        html_content = render_to_string('neuro/emails/renewal_code.html', context)
        text_content = strip_tags(html_content)

        send_mail(
            subject=subject,
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_content,
            fail_silently=False,
        )

        logger.info(f"[EMAIL] Код подтверждения для {action} отправлен пользователю {user.email}")

        return JsonResponse({
            'success': True,
            'message': 'Код подтверждения отправлен на вашу почту'
        })

    except Exception as e:
        logger.error(f"[ERR] Ошибка отправки кода: {e}")
        return JsonResponse({
            'success': False,
            'message': 'Ошибка при отправке кода'
        }, status=500)


@login_required
@require_POST
def verify_renewal_code(request):
    """
    Проверка кода подтверждения и изменение автопродления
    """
    try:
        data = json.loads(request.body)
        code = data.get('code')

        if not code or len(code) != 6:
            return JsonResponse({
                'success': False,
                'message': 'Введите 6-значный код'
            }, status=400)

        # Проверяем код из сессии
        saved_code = request.session.get('renewal_code')
        expires = request.session.get('renewal_code_expires')
        action = request.session.get('renewal_action')

        if not saved_code or not expires or not action:
            return JsonResponse({
                'success': False,
                'message': 'Код не найден или истек. Запросите новый код.'
            }, status=400)

        # Проверяем срок действия
        expires_dt = datetime.fromisoformat(expires)
        if timezone.now() > expires_dt:
            # Очищаем сессию
            request.session.pop('renewal_code', None)
            request.session.pop('renewal_action', None)
            request.session.pop('renewal_code_expires', None)

            return JsonResponse({
                'success': False,
                'message': 'Срок действия кода истек. Запросите новый код.'
            }, status=400)

        # Проверяем код
        if code != saved_code:
            return JsonResponse({
                'success': False,
                'message': 'Неверный код подтверждения'
            }, status=400)

        # Код верный - применяем изменение
        user = request.user
        subscription = user.active_subscription

        if not subscription:
            return JsonResponse({
                'success': False,
                'message': 'У вас нет активной подписки'
            }, status=400)

        if action == 'enable':
            subscription.auto_renew = True
            message = 'Автопродление включено'
        else:  # disable
            subscription.auto_renew = False
            message = 'Автопродление отключено'

        subscription.save()

        # Очищаем сессию
        request.session.pop('renewal_code', None)
        request.session.pop('renewal_action', None)
        request.session.pop('renewal_code_expires', None)

        logger.info(f"[OK] Автопродление {action} для пользователя {user.email}")

        return JsonResponse({
            'success': True,
            'message': message,
            'auto_renew': subscription.auto_renew
        })

    except Exception as e:
        logger.error(f"[ERR] Ошибка проверки кода: {e}")
        return JsonResponse({
            'success': False,
            'message': 'Ошибка при проверке кода'
        }, status=500)


@login_required
@require_POST
def resend_renewal_code(request):
    """
    Повторная отправка кода подтверждения
    """
    try:
        # Проверяем, есть ли активная сессия с кодом
        action = request.session.get('renewal_action')

        if not action:
            return JsonResponse({
                'success': False,
                'message': 'Сначала запросите код'
            }, status=400)

        # Генерируем новый код
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])

        # Обновляем в сессии
        request.session['renewal_code'] = code
        request.session['renewal_code_expires'] = (timezone.now() + timedelta(minutes=10)).isoformat()

        # Отправляем новый код
        user = request.user
        subject = 'Новый код подтверждения для изменения автопродления'

        context = {
            'username': user.username or user.email.split('@')[0],
            'code': code,
            'action': 'включения' if action == 'enable' else 'отключения',
            'site_name': getattr(settings, 'SITE_NAME', 'StudyLuck'),
        }

        html_content = render_to_string('emails/renewal_code.html', context)
        text_content = strip_tags(html_content)

        send_mail(
            subject=subject,
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_content,
            fail_silently=False,
        )

        logger.info(f"[EMAIL] Новый код подтверждения отправлен пользователю {user.email}")

        return JsonResponse({
            'success': True,
            'message': 'Новый код отправлен на вашу почту'
        })

    except Exception as e:
        logger.error(f"[ERR] Ошибка повторной отправки кода: {e}")
        return JsonResponse({
            'success': False,
            'message': 'Ошибка при отправке кода'
        }, status=500)


@login_required
@require_POST
def update_auto_renewal(request):
    """
    Обновление статуса автопродления (без подтверждения для включения)
    """
    try:
        data = json.loads(request.body)
        auto_renew = data.get('auto_renew')

        if auto_renew is None:
            return JsonResponse({
                'success': False,
                'message': 'Не указан статус автопродления'
            }, status=400)

        user = request.user
        subscription = user.active_subscription

        if not subscription:
            return JsonResponse({
                'success': False,
                'message': 'У вас нет активной подписки'
            }, status=400)

        # Обновляем статус
        subscription.auto_renew = auto_renew
        subscription.save()

        logger.info(f"[OK] Автопродление {'включено' if auto_renew else 'отключено'} для {user.email}")

        return JsonResponse({
            'success': True,
            'auto_renew': subscription.auto_renew,
            'message': f'Автопродление {"включено" if auto_renew else "отключено"}'
        })

    except Exception as e:
        logger.error(f"[ERR] Ошибка обновления автопродления: {e}")
        return JsonResponse({
            'success': False,
            'message': 'Ошибка при обновлении автопродления'
        }, status=500)


@login_required
@require_POST
def apply_promo_code(request):
    """Применение промокода"""
    try:
        data = json.loads(request.body)
        code = data.get('code', '').strip()
        if not code:
            return JsonResponse({'success': False, 'message': 'Введите промокод'})

        # Поиск без учёта регистра
        try:
            promo = PromoCode.objects.get(code__iexact=code)
        except PromoCode.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Неверный промокод'})

        if not promo.is_valid():
            return JsonResponse({'success': False, 'message': 'Промокод недействителен'})

        # Проверяем, не использовал ли пользователь этот промокод ранее
        if UsedPromoCode.objects.filter(user=request.user, promo_code=promo).exists():
            return JsonResponse({'success': False, 'message': 'Вы уже использовали этот промокод'})

        # Начисляем звезды
        request.user.add_pages(promo.stars)
        # Сохраняем факт использования
        UsedPromoCode.objects.create(user=request.user, promo_code=promo)
        promo.used_count += 1
        promo.save(update_fields=['used_count'])

        # Создаём запись в истории платежей
        PaymentHistory.objects.create(
            user=request.user,
            payment_type='promo',
            amount=0,
            pages_count=promo.stars,
            status='success',
            paid_at=timezone.now(),
            description=f"Активация промокода {promo.code}"
        )

        return JsonResponse({
            'success': True,
            'message': f'Промокод активирован! +{promo.stars} звёзд',
            'new_balance': request.user.pages_count
        })
    except Exception as e:
        logger.error(f"Ошибка активации промокода: {e}")
        return JsonResponse({'success': False, 'message': 'Ошибка сервера'})


@login_required
def profile_data(request):
    """Возвращает данные пользователя для страницы профиля"""
    user = request.user
    # Количество дней с регистрации
    days_with_us = (timezone.now().date() - user.date_joined.date()).days

    # Проверяем, есть ли у пользователя платная подписка
    has_paid_subscription = user.active_subscription and not user.tariff.is_free
    trial_tariff = None

    if not has_paid_subscription:
        # Показываем пробный тариф (например, Lite) – берём из БД по is_trial=True
        trial_tariff = Tariff.objects.filter(is_trial=True, is_active=True).first()
        if trial_tariff:
            trial_tariff_data = {
                'id': trial_tariff.id,
                'display_name': trial_tariff.display_name,
                'price': float(trial_tariff.price),
                'duration_days': trial_tariff.duration_days,
                'pages': trial_tariff.pages_count,
                'description': trial_tariff.description,
                'is_trial': trial_tariff.is_trial,
                'next_tariff': {
                    'display_name': trial_tariff.next_tariff.display_name,
                    'price': float(trial_tariff.next_tariff.price)
                } if trial_tariff.next_tariff else None
            }
        else:
            trial_tariff_data = None
    else:
        trial_tariff_data = None

    # История пополнений (успешные платежи: покупка страниц, оплата подписки, активация промокода)
    payments = PaymentHistory.objects.filter(
        user=user,
        status='success',
        payment_type__in=['pages', 'subscription', 'promo']
    ).order_by('-paid_at')[:20]

    history = []
    for p in payments:
        if p.payment_type == 'promo':
            description = p.description or f"Активация промокода (+{p.pages_count} зв.)"
        elif p.payment_type == 'pages':
            description = p.description or f"Покупка {p.pages_count} страниц"
        else:  # subscription
            description = p.description or f"Оплата тарифа {p.tariff.display_name if p.tariff else ''}"

        history.append({
            'date': p.paid_at.strftime('%d.%m.%Y') if p.paid_at else p.created_at.strftime('%d.%m.%Y'),
            'description': description,
            'amount': p.pages_count
        })

    # История списаний (расходы)
    spendings = UserSpending.objects.filter(user=user).order_by('-created_at')[:20]
    spending_history = []
    for s in spendings:
        spending_history.append({
            'date': s.created_at.strftime('%d.%m.%Y'),
            'description': s.description,
            'amount': s.amount
        })

    return JsonResponse({
        'success': True,
        'user': {
            'name': user.get_full_name() or user.username,
            'email': user.email,
            'days': days_with_us,
            'tariff': user.tariff.display_name if user.tariff else 'Бесплатный',
            'stars': user.pages_count,
            'avatar_url': f"https://ui-avatars.com/api/?name={user.username}&background=f0a38a&color=fff&size=128"
        },
        'trial_tariff': trial_tariff_data,
        'history': history,  # пополнения
        'spendings': spending_history  # списания
    })


@login_required
@require_POST
def request_withdrawal(request):
    try:
        data = json.loads(request.body)
        amount = Decimal(data['amount'])
        card_number = data['card_number']
        user = request.user
        if not user.can_convert_to_rub:
            return JsonResponse({'success': False, 'message': 'Вывод недоступен'})
        if user.rub_balance < amount:
            return JsonResponse({'success': False, 'message': 'Недостаточно средств'})
        user.rub_balance -= amount
        user.save()
        WithdrawalRequest.objects.create(user=user, amount=amount, card_number=card_number)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
