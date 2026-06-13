from allauth.socialaccount.signals import social_account_added, pre_social_login
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from allauth.exceptions import ImmediateHttpResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(social_account_added)
def handle_social_account_added(request, sociallogin, **kwargs):
    """
    Обработчик добавления нового социального аккаунта
    """
    try:
        user = sociallogin.user
        provider = sociallogin.account.provider

        provider_names = {
            'google': 'Google',
            'yandex': 'Яндекс',
            'vk': 'ВКонтакте'
        }

        provider_display = provider_names.get(provider, provider.capitalize())

        logger.info(f"[SEC] Социальный аккаунт добавлен: {provider} для {user.username}")

        # Автоматически подтверждаем email для соц. аккаунтов
        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=['email_verified'])

        # Добавляем сообщение пользователю
        messages.success(
            request,
            f'Вы успешно вошли через {provider_display}!'
        )

    except Exception as e:
        logger.error(f"[ERR] Ошибка в handle_social_account_added: {e}")


@receiver(pre_social_login)
def handle_pre_social_login(request, sociallogin, **kwargs):
    """
    Обработчик перед социальным входом
    Выполняет проверки и автоматическое связывание аккаунтов
    """
    try:
        user = sociallogin.user
        provider = sociallogin.account.provider

        provider_names = {
            'google': 'Google',
            'yandex': 'Яндекс',
            'vk': 'ВКонтакте'
        }

        provider_display = provider_names.get(provider, provider.capitalize())

        # Если пользователь уже авторизован (добавление соц. аккаунта к существующему аккаунту)
        if request.user.is_authenticated:
            # Проверяем, не привязан ли уже этот соц. аккаунт к другому пользователю
            existing_account = sociallogin.account
            if existing_account.user != request.user:
                # Привязываем к текущему пользователю
                existing_account.user = request.user
                existing_account.save()
                logger.info(f"[LINK] Социальный аккаунт {provider} привязан к {request.user.username}")
                messages.success(request, f'Аккаунт {provider_display} успешно привязан!')

        else:
            # Если пользователь не авторизован - это вход
            logger.info(f"[SEC] Попытка входа через {provider}: {sociallogin.user.username}")

            # Для VK может не быть email
            if provider == 'vk' and not user.email:
                logger.info(f"[EMAIL] VK аккаунт без email: {user.username}")
                # Создаем временный email если нужно
                if not user.email:
                    uid = sociallogin.account.uid
                    user.email = f"vk_{uid}@temp.erogent.com"

            # Проверяем, существует ли пользователь с таким email
            email = user.email
            if email and not email.startswith('vk_'):
                try:
                    existing_user = User.objects.get(email=email)

                    # Если пользователь существует, но не подтвердил email
                    if not existing_user.email_verified:
                        logger.info(f"[EMAIL] Автоматическое подтверждение email для {email}")
                        existing_user.email_verified = True
                        existing_user.save(update_fields=['email_verified'])

                except User.DoesNotExist:
                    pass

    except Exception as e:
        logger.error(f"[ERR] Ошибка в handle_pre_social_login: {e}")


def social_login_error_handler(request, error, **kwargs):
    """
    Обработчик ошибок социальной авторизации
    """
    logger.error(f"[ERR] Ошибка социальной авторизации: {error}")

    messages.error(
        request,
        'Произошла ошибка при входе через социальную сеть. Пожалуйста, попробуйте еще раз или используйте email.'
    )

    return redirect(reverse('users_pages:auth_page'))