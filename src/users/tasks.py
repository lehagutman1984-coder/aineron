from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import UserSubscription, CustomUser, PaymentHistory, Tariff
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import hashlib
import requests
import logging
import json
import time

logger = logging.getLogger(__name__)


@shared_task
def check_expired_subscriptions():
    logger.info("⚠️ Эта задача устарела, используйте process_pending_renewals")
    return "Deprecated"


def build_receipt_for_renewal(tariff, amount, description):
    """Формирует чек для recurring-платежа (тариф или переход)"""
    receipt_data = {
        "items": [
            {
                "name": description[:128],
                "quantity": 1,
                "sum": float(amount),
                "tax": "none"
            }
        ]
    }
    return receipt_data


@shared_task
def process_pending_renewals():
    """
    Проверяет подписки, у которых скоро истекает срок, и пытается продлить их
    Запускается каждые 12 часов
    """
    logger.info("🔄 Проверка подписок, требующих продления...")

    renew_window_start = timezone.now()
    renew_window_end = timezone.now() + timedelta(days=3)

    pending_subscriptions = UserSubscription.objects.filter(
        is_active=True,
        status='active',
        expires_at__gte=renew_window_start,
        expires_at__lte=renew_window_end,
        tariff__is_free=False,
        auto_renew=True,
    ).select_related('user', 'tariff')

    logger.info(f"📊 Найдено подписок для проверки: {pending_subscriptions.count()}")

    success_count = 0
    failed_count = 0

    for subscription in pending_subscriptions:
        try:
            user = subscription.user
            days_left = subscription.days_until_expiration()

            logger.info(f"📋 Проверка подписки пользователя {user.email}:")
            logger.info(f"  - Истекает через: {days_left} дн.")
            logger.info(f"  - Попыток продления: {subscription.renewal_attempts}/{subscription.max_renewal_attempts}")
            logger.info(f"  - Последняя попытка: {subscription.last_renewal_attempt}")

            if subscription.renewal_attempts >= subscription.max_renewal_attempts:
                logger.warning(f"❌ Достигнут лимит попыток продления для {user.email}")
                user.return_to_free_tariff()
                failed_count += 1
                continue

            if subscription.last_renewal_attempt and \
                    subscription.last_renewal_attempt.date() == timezone.now().date():
                logger.info(f"⏸️ Сегодня уже была попытка для {user.email}, пропускаем")
                continue

            logger.info(f"🔄 Попытка продления #{subscription.renewal_attempts + 1} для {user.email}")

            subscription.renewal_attempts += 1
            subscription.last_renewal_attempt = timezone.now()
            subscription.save(update_fields=['renewal_attempts', 'last_renewal_attempt'])

            success = attempt_auto_renewal(subscription)

            if success:
                logger.info(f"✅ Подписка пользователя {user.email} успешно продлена")
                success_count += 1
            else:
                logger.warning(f"❌ Не удалось продлить подписку пользователя {user.email} (попытка {subscription.renewal_attempts})")
                failed_count += 1

                if days_left <= 1 and subscription.renewal_attempts >= subscription.max_renewal_attempts:
                    logger.warning(f"⚠️ Последний день подписки, возвращаем {user.email} на бесплатный")
                    user.return_to_free_tariff()

        except Exception as e:
            logger.error(f"❌ Ошибка при обработке подписки {subscription.id}: {e}")
            import traceback
            logger.error(traceback.format_exc())

    logger.info(f"📊 Итоги проверки: {success_count} успешно, {failed_count} неудачно")
    return f"Processed: {success_count} success, {failed_count} failed"


def attempt_auto_renewal(subscription):
    """
    Попытка автопродления подписки. Для пробного тарифа с next_tariff – переход на новый тариф.
    """
    try:
        user = subscription.user
        tariff = subscription.tariff

        if not tariff or tariff.is_free:
            return False

        # ----- ЛОГИКА ДЛЯ ПРОБНОГО ТАРИФА С ПЕРЕХОДОМ -----
        if tariff.is_trial and tariff.next_tariff:
            new_tariff = tariff.next_tariff
            amount = float(new_tariff.price)
            description = f"Переход на тариф: {new_tariff.display_name}"
            logger.info(f"🔄 Пробный тариф {tariff.display_name} -> переход на {new_tariff.display_name}, сумма {amount}")

            parent_payment = PaymentHistory.objects.filter(
                user=user,
                tariff=tariff,
                status='success',
                parent_payment__isnull=True
            ).order_by('-paid_at').first()

            if not parent_payment:
                logger.error(f"❌ Не найден материнский платеж для пробного тарифа {tariff.display_name}")
                return False

            # Формируем чек (аналогично успешно работающей функции buy_pages)
            receipt_data = {
                "items": [
                    {
                        "name": description[:128],
                        "quantity": 1,
                        "sum": amount,
                        "tax": "none"
                    }
                ]
            }
            receipt_json = json.dumps(receipt_data, separators=(',', ':'), ensure_ascii=False)

            new_inv_id = int(time.time() * 1000) % 10000000
            merchant_login = settings.ROBOKASSA_LOGIN
            password_1 = settings.ROBOKASSA_PASS1
            out_sum = f"{amount:.2f}"

            signature_str = f"{merchant_login}:{out_sum}:{new_inv_id}:{receipt_json}:{password_1}"
            signature = hashlib.md5(signature_str.encode('utf-8')).hexdigest()

            data = {
                'MerchantLogin': merchant_login,
                'OutSum': out_sum,
                'InvId': new_inv_id,
                'SignatureValue': signature,
                'PreviousInvoiceID': parent_payment.invoice_id,
                'Description': description,
                'Culture': 'ru',
                'Encoding': 'utf-8',
                'Receipt': receipt_json
            }

            response = requests.post("https://auth.robokassa.ru/Merchant/Recurring", data=data, timeout=30)

            if response.status_code == 200 and response.text.strip().startswith('OK'):
                PaymentHistory.objects.create(
                    user=user,
                    tariff=new_tariff,
                    invoice_id=str(new_inv_id),
                    amount=amount,
                    pages_count=new_tariff.pages_count,
                    status='success',
                    payment_type='subscription',
                    description=description,
                    parent_payment=parent_payment
                )

                user.activate_paid_tariff(new_tariff, {'invoice_id': str(new_inv_id)})

                subscription.is_active = False
                subscription.status = 'expired'
                subscription.save()

                logger.info(f"✅ Пользователь {user.email} переведён с {tariff.display_name} на {new_tariff.display_name}")
                return True
            else:
                logger.error(f"❌ Ошибка recurring-запроса для перехода: {response.text}")
                return False

        # ----- ОБЫЧНОЕ ПРОДЛЕНИЕ (без смены тарифа) -----
        parent_payment = PaymentHistory.objects.filter(
            user=user,
            tariff=tariff,
            status='success',
            parent_payment__isnull=True
        ).order_by('-paid_at').first()

        if not parent_payment:
            logger.error(f"❌ Не найден материнский платеж для {tariff.display_name}")
            return False

        description = f"Продление тарифа: {tariff.display_name}"
        amount = float(tariff.price)

        receipt_data = {
            "items": [
                {
                    "name": description[:128],
                    "quantity": 1,
                    "sum": amount,
                    "tax": "none"
                }
            ]
        }
        receipt_json = json.dumps(receipt_data, separators=(',', ':'), ensure_ascii=False)

        new_inv_id = int(time.time() * 1000) % 10000000
        merchant_login = settings.ROBOKASSA_LOGIN
        password_1 = settings.ROBOKASSA_PASS1
        out_sum = f"{amount:.2f}"

        signature_str = f"{merchant_login}:{out_sum}:{new_inv_id}:{receipt_json}:{password_1}"
        signature = hashlib.md5(signature_str.encode('utf-8')).hexdigest()

        data = {
            'MerchantLogin': merchant_login,
            'OutSum': out_sum,
            'InvId': new_inv_id,
            'SignatureValue': signature,
            'PreviousInvoiceID': parent_payment.invoice_id,
            'Description': description,
            'Culture': 'ru',
            'Encoding': 'utf-8',
            'Receipt': receipt_json
        }

        response = requests.post("https://auth.robokassa.ru/Merchant/Recurring", data=data, timeout=30)

        if response.status_code == 200 and response.text.strip().startswith('OK'):
            PaymentHistory.objects.create(
                user=user,
                tariff=tariff,
                invoice_id=str(new_inv_id),
                amount=tariff.price,
                pages_count=tariff.pages_count,
                status='success',
                payment_type='subscription',
                description=description,
                parent_payment=parent_payment
            )

            user.pages_count += tariff.pages_count
            user.save()

            subscription.expires_at = timezone.now() + timedelta(days=tariff.duration_days)
            subscription.robokassa_invoice_id = str(new_inv_id)
            subscription.renewal_attempts = 0
            subscription.save()

            logger.info(f"✅ Подписка {subscription.id} продлена, добавлено {tariff.pages_count} звезд, всего у пользователя: {user.pages_count}")
            return True

        return False

    except Exception as e:
        logger.error(f"❌ Ошибка автопродления: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


from django.contrib.sites.models import Site

def send_expiry_email(subscription):
    try:
        user = subscription.user
        tariff = subscription.tariff
        current_site = Site.objects.get_current()
        site_name = current_site.name
        site_url = settings.SITE_URL.rstrip('/')

        def plural_days(days):
            if days % 10 == 1 and days % 100 != 11:
                return "день"
            elif 2 <= days % 10 <= 4 and (days % 100 < 10 or days % 100 >= 20):
                return "дня"
            else:
                return "дней"

        context = {
            'username': user.username or user.email.split('@')[0],
            'tariff_name': tariff.display_name if tariff else 'Ваш тариф',
            'expires_at': subscription.expires_at.strftime('%d.%m.%Y'),
            'days_left': 3,
            'days_word': plural_days(3),
            'auto_renew': subscription.auto_renew,
            'price': tariff.price if tariff else 0,
            'site_name': site_name,
            'site_url': site_url,
        }

        subject = f'⏰ Подписка {tariff.display_name} истекает через 3 дня'
        html_content = render_to_string('neuro/emails/subscription_expiring_soon.html', context)
        text_content = strip_tags(html_content)

        send_mail(
            subject=subject,
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_content,
            fail_silently=False,
        )

        subscription.last_expiry_notification_sent = timezone.now()
        subscription.save(update_fields=['last_expiry_notification_sent'])

        logger.info(f"📧 Письмо об истечении подписки отправлено {user.email}")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка отправки письма: {e}")
        return False


from datetime import datetime, timezone as dt_timezone

@shared_task
def notify_upcoming_expiration():
    """
    Уведомляет пользователей о скором окончании подписки
    Отправляет письма только за 3 дня до окончания, один раз
    """
    now = timezone.now()
    today = now.date()
    target_date = today + timedelta(days=4)

    start_of_day = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=dt_timezone.utc)
    end_of_day = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=dt_timezone.utc)

    upcoming_expiration = UserSubscription.objects.filter(
        is_active=True,
        status='active',
        expires_at__gte=start_of_day,
        expires_at__lte=end_of_day,
        tariff__is_free=False,
        last_expiry_notification_sent__isnull=True
    )

    sent_count = 0
    for subscription in upcoming_expiration:
        success = send_expiry_email(subscription)
        if success:
            sent_count += 1

    logger.info(f"📊 Отправлено писем об истечении: {sent_count}")
    return f"Sent: {sent_count}"
