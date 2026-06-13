from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from allauth.socialaccount.models import SocialAccount
from allauth.account.models import EmailAddress
from .models import CustomUser, UserActivityLog, UserIPAddress
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CustomUser)
def handle_user_saved(sender, instance, created, **kwargs):
    """
    Обработчик сохранения пользователя
    """
    try:
        if created:
            logger.info(f"[OK] Создан новый пользователь: {instance.email} (ID: {instance.id})")

            # [ERR] УДАЛЕНО: создание EmailAddress здесь
            # Allauth сам создаст EmailAddress при социальном входе или регистрации
            # Это предотвращает конфликт с AssertionError в allauth

    except Exception as e:
        logger.error(f"[ERR] Ошибка в handle_user_saved: {e}")


@receiver(post_save, sender=SocialAccount)
def handle_social_account_saved(sender, instance, created, **kwargs):
    """
    Обработчик сохранения социального аккаунта
    """
    try:
        if created:
            user = instance.user
            provider = instance.provider

            # Автоматически подтверждаем email для социальных аккаунтов
            if not user.email_verified:
                user.email_verified = True
                user.save(update_fields=['email_verified'])

                logger.info(f"[OK] Email автоматически подтвержден для {user.email} (соц. аккаунт: {provider})")

            # Также подтверждаем EmailAddress для allauth (только если он существует)
            email_address = EmailAddress.objects.filter(user=user, email=user.email).first()
            if email_address and not email_address.verified:
                email_address.verified = True
                email_address.save()
                logger.info(f"[OK] EmailAddress подтвержден для {user.email}")
            elif not email_address:
                logger.debug(f"ℹ️ EmailAddress для {user.email} еще не создан allauth, пропускаем")

    except Exception as e:
        logger.error(f"[ERR] Ошибка в handle_social_account_saved: {e}")


@receiver(post_save, sender=UserIPAddress)
def handle_user_ip_saved(sender, instance, created, **kwargs):
    """
    Обработчик сохранения IP-адреса пользователя
    """
    try:
        if created:
            # Проверяем, есть ли другие пользователи с этого IP
            other_users_count = UserIPAddress.objects.filter(
                ip_address=instance.ip_address
            ).exclude(
                user=instance.user
            ).values('user').distinct().count()

            if other_users_count > 0:
                logger.warning(f"[WARN] Обнаружено несколько пользователей с IP {instance.ip_address}: "
                               f"{instance.user.email} и еще {other_users_count} пользователь(я)")

    except Exception as e:
        logger.error(f"[ERR] Ошибка в handle_user_ip_saved: {e}")


@receiver(pre_save, sender=CustomUser)
def handle_user_pre_save(sender, instance, **kwargs):
    """
    Обработчик перед сохранением пользователя
    """
    try:
        # Если это существующий пользователь
        if instance.pk:
            try:
                old_instance = CustomUser.objects.get(pk=instance.pk)

                # Проверяем изменение статуса теневого бана
                if old_instance.shadow_banned != instance.shadow_banned:
                    if instance.shadow_banned:
                        logger.warning(f"[WARN] Пользователю {instance.email} назначен теневой бан")
                    else:
                        logger.info(f"[OK] С пользователя {instance.email} снят теневой бан")

                # Проверяем подтверждение email
                if not old_instance.email_verified and instance.email_verified:
                    logger.info(f"[OK] Email {instance.email} подтвержден")

            except CustomUser.DoesNotExist:
                pass

    except Exception as e:
        logger.error(f"[ERR] Ошибка в handle_user_pre_save: {e}")


# Сигнал для обновления last_login в UserActivityLog
@receiver(pre_save, sender=CustomUser)
def handle_user_login(sender, instance, **kwargs):
    """
    Обработчик входа пользователя (обновляет last_login в UserActivityLog)
    """
    try:
        if instance.pk:
            try:
                old_instance = CustomUser.objects.get(pk=instance.pk)

                # Если last_login изменился (пользователь вошел)
                if old_instance.last_login != instance.last_login and instance.last_login:
                    # Обновляем или создаем запись в активности
                    today = timezone.now().date()

                    activity_log, created = UserActivityLog.objects.get_or_create(
                        user=instance,
                        date=today,
                        defaults={
                            'login_count': 1,
                            'last_login_time': instance.last_login
                        }
                    )

                    if not created:
                        activity_log.increment_login(instance.last_login)

                    logger.debug(f"[STAT] Зафиксирован вход пользователя {instance.email}")

            except CustomUser.DoesNotExist:
                pass

    except Exception as e:
        logger.error(f"[ERR] Ошибка в handle_user_login: {e}")