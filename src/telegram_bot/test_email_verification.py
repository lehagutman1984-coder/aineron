"""
2026-08-30: зеркало api/permissions.py::IsEmailVerified для бота — прямой
обход веб/API-проверки через aiogram-хендлеры, которые вызывают
spend_kopecks/has_enough_kopecks напрямую, минуя DRF. Bot-standalone
аккаунты (BUG-I self-serve /start, placeholder tg{id}@telegram.local)
никогда не смогут подтвердить email и намеренно исключены — иначе фикс
разлогинил бы большинство органических пользователей бота.

Django TestCase (SQLite): python manage.py test telegram_bot.test_email_verification
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from telegram_bot.utils import needs_email_verification

User = get_user_model()


class NeedsEmailVerificationTests(TestCase):
    def test_real_email_unverified_blocked(self):
        user = User.objects.create_user(username='real', email='real@example.com', password='x')
        self.assertFalse(user.email_verified)
        self.assertTrue(needs_email_verification(user))

    def test_real_email_verified_allowed(self):
        user = User.objects.create_user(username='verified', email='verified@example.com', password='x')
        user.email_verified = True
        user.save(update_fields=['email_verified'])
        self.assertFalse(needs_email_verification(user))

    def test_bot_standalone_placeholder_email_allowed(self):
        """BUG-I: _create_standalone_account даёт tg{id}@telegram.local без
        пароля и без email_verified=True — это штатное состояние для
        большинства пользователей бота, не абьюз."""
        user = User.objects.create_user(
            username='tg123456', email='tg123456@telegram.local', password=None,
        )
        self.assertFalse(user.email_verified)
        self.assertFalse(needs_email_verification(user))
