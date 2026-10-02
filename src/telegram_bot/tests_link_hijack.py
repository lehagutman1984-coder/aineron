"""
2026-10-01 (аудит безопасности, API_SECURITY_AUDIT_2026-10-01.md, пункт 22):
регрессионный тест — переход по чужой ссылке привязки больше не угоняет
Telegram, уже привязанный к ДРУГОМУ аккаунту, без подтверждения.

Запуск: python manage.py test telegram_bot.tests_link_hijack
"""
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase

from telegram_bot.handlers.start import TelegramAlreadyLinkedElsewhere, _create_tg_user
from telegram_bot.models import TelegramUser

User = get_user_model()


def _from_user(tg_id, username='victim_tg', first_name='Victim'):
    return SimpleNamespace(id=tg_id, username=username, first_name=first_name)


class TelegramLinkHijackTests(TestCase):
    def test_relink_to_different_account_raises_instead_of_silently_switching(self):
        victim = User.objects.create_user(username='victim@t.ru', email='victim@t.ru', password='x')
        attacker = User.objects.create_user(username='attacker@t.ru', email='attacker@t.ru', password='x')
        tg = _from_user(123456789)

        # Жертва уже привязала СВОЙ Telegram к своему аккаунту.
        _create_tg_user(victim, tg)
        existing = TelegramUser.objects.get(telegram_id=123456789)
        self.assertEqual(existing.user_id, victim.id)

        # Жертва переходит по ссылке с токеном АТАКУЮЩЕГО (link_token.user=attacker).
        with self.assertRaises(TelegramAlreadyLinkedElsewhere):
            _create_tg_user(attacker, tg)

        # Привязка НЕ должна была смениться.
        existing.refresh_from_db()
        self.assertEqual(existing.user_id, victim.id)

    def test_fresh_telegram_id_links_normally(self):
        user = User.objects.create_user(username='fresh@t.ru', email='fresh@t.ru', password='x')
        tg = _from_user(987654321)
        tg_user = _create_tg_user(user, tg)
        self.assertEqual(tg_user.user_id, user.id)

    def test_relinking_same_account_is_idempotent_not_an_error(self):
        user = User.objects.create_user(username='same@t.ru', email='same@t.ru', password='x')
        tg = _from_user(111222333)
        _create_tg_user(user, tg)
        # Тот же аккаунт повторно (например, переход по собственной ссылке снова) — не ошибка.
        tg_user = _create_tg_user(user, tg)
        self.assertEqual(tg_user.user_id, user.id)
