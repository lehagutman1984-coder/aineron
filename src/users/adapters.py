from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.exceptions import ImmediateHttpResponse
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
import logging
import secrets
import string

logger = logging.getLogger(__name__)


class CustomAccountAdapter(DefaultAccountAdapter):
    """Кастомный адаптер для аккаунтов"""

    def save_user(self, request, user, form, commit=True):
        """
        Сохраняет пользователя, устанавливает дополнительные поля
        """
        user = super().save_user(request, user, form, commit=False)

        # Устанавливаем username из email если не задан
        if not user.username:
            user.username = user.email.split('@')[0]

        # Email не подтвержден при регистрации
        user.email_verified = False

        # Генерация реферального кода
        if not user.referral_code:
            alphabet = string.ascii_uppercase + string.digits
            user.referral_code = ''.join(secrets.choice(alphabet) for _ in range(8))

        # Реферальный код: из сессии (legacy) или cookie (ставит Next.js middleware)
        ref_code = request.session.get('ref_code') or request.COOKIES.get('ref_code')
        if ref_code:
            try:
                from .models import CustomUser
                referrer = CustomUser.objects.get(referral_code__iexact=ref_code)
                user.referrer = referrer
                referrer.referral_clicks += 1
                referrer.save(update_fields=['referral_clicks'])
                request.session.pop('ref_code', None)
            except CustomUser.DoesNotExist:
                pass

        if commit:
            user.save()

        return user

    def get_login_redirect_url(self, request):
        """
        Куда перенаправлять после входа
        """
        # Проверяем, находится ли пользователь в теневом бане
        if request.user.is_authenticated and request.user.shadow_banned:
            return '/blocked/'

        # Проверяем, подтвержден ли email
        if request.user.is_authenticated and not request.user.email_verified:
            return '/verify-email/'

        # Добавляем сообщение об успешном входе
        if not messages.get_messages(request):
            messages.success(request, 'Вы успешно вошли в систему!')

        return super().get_login_redirect_url(request)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Кастомный адаптер для социальных аккаунтов"""

    def pre_social_login(self, request, sociallogin):
        """
        Действия перед входом через социальную сеть
        """
        try:
            # Автоматически подтверждаем email для социальных аккаунтов
            user = sociallogin.user
            user.email_verified = True

            # Устанавливаем username из email если не задан
            if not user.username:
                # Для VK может не быть email, создаем username из provider + uid
                if not user.email and sociallogin.account.provider == 'vk':
                    uid = sociallogin.account.uid
                    user.username = f"vk_{uid[:8]}"
                elif user.email:
                    user.username = user.email.split('@')[0]
                else:
                    random_str = ''.join(secrets.choice(string.ascii_lowercase) for _ in range(8))
                    user.username = f"user_{random_str}"

            logger.info(f"Социальный вход: {user.username} через {sociallogin.account.provider}")
        except Exception as e:
            logger.error(f"Ошибка в pre_social_login: {e}")

    def save_user(self, request, sociallogin, form=None):
        """
        Сохраняет пользователя из социальной сети
        """
        user = super().save_user(request, sociallogin, form)

        # Автоматически подтверждаем email (если он есть)
        if user.email:
            user.email_verified = True
        else:
            user.email_verified = True

        # Генерация реферального кода
        if not user.referral_code:
            alphabet = string.ascii_uppercase + string.digits
            user.referral_code = ''.join(secrets.choice(alphabet) for _ in range(8))

        # Реферальный код: из сессии (legacy) или cookie (ставит Next.js middleware)
        ref_code = request.session.get('ref_code') or request.COOKIES.get('ref_code')
        if ref_code:
            try:
                from .models import CustomUser
                referrer = CustomUser.objects.get(referral_code__iexact=ref_code)
                user.referrer = referrer
                referrer.referral_clicks += 1
                referrer.save(update_fields=['referral_clicks'])
                request.session.pop('ref_code', None)
            except CustomUser.DoesNotExist:
                pass

        user.save()

        logger.info(f"Создан социальный пользователь: {user.username} через {sociallogin.account.provider}")

        return user

    def populate_user(self, request, sociallogin, data):
        """
        Заполняет данные пользователя из социального аккаунта
        """
        user = super().populate_user(request, sociallogin, data)

        provider = sociallogin.account.provider

        if provider == 'vk':
            extra_data = sociallogin.account.extra_data

            if not user.first_name:
                user.first_name = extra_data.get('first_name', '')
            if not user.last_name:
                user.last_name = extra_data.get('last_name', '')

            if not user.email:
                uid = sociallogin.account.uid
                user.email = f"vk_{uid}@temp.erogent.com"
                user.username = f"vk_{uid[:8]}"

        return user