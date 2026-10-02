"""
2026-10-01 (аудит безопасности, API_SECURITY_AUDIT_2026-10-01.md, пункт 17):
регрессионные тесты на api.tasks.reconcile_stuck_api_reservations.

Запуск: python manage.py test api.tests_reconcile_stuck_api_reservations
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from api.models import TokenUsage
from api.tasks import reconcile_stuck_api_reservations
from users.models import BalanceTransaction

User = get_user_model()


def _user(email):
    u = User.objects.create_user(username=email, email=email, password='x')
    u.set_kopecks(100000)
    return u


def _old_spend(user, reference, minutes_ago=60):
    user.spend_kopecks(500, type='spend', reference=reference)
    tx = BalanceTransaction.objects.get(user=user, type=BalanceTransaction.Type.SPEND, reference=reference)
    BalanceTransaction.objects.filter(pk=tx.pk).update(
        created_at=timezone.now() - timedelta(minutes=minutes_ago),
    )
    return tx


class ReconcileStuckApiReservationsTests(TestCase):
    @mock.patch('telegram_bot.notify.notify_admins')
    def test_stuck_reservation_without_refund_or_usage_is_flagged(self, mock_notify):
        user = _user('stuck@t.ru')
        _old_spend(user, 'api:aaaaaaaaaaaa')
        reconcile_stuck_api_reservations()
        mock_notify.assert_called_once()
        self.assertIn('api:aaaaaaaaaaaa', mock_notify.call_args[0][0])

    @mock.patch('telegram_bot.notify.notify_admins')
    def test_reservation_with_refund_is_not_flagged(self, mock_notify):
        user = _user('refunded@t.ru')
        _old_spend(user, 'api:bbbbbbbbbbbb')
        user.add_kopecks(500, type='refund', reference='api:bbbbbbbbbbbb')
        reconcile_stuck_api_reservations()
        mock_notify.assert_not_called()

    @mock.patch('telegram_bot.notify.notify_admins')
    def test_reservation_with_matching_token_usage_is_not_flagged(self, mock_notify):
        # diff=0 между резервом и фактом -> нет refund-транзакции, но есть
        # TokenUsage - это НЕ аномалия (запрос реально завершился штатно).
        user = _user('exact@t.ru')
        _old_spend(user, 'api:cccccccccccc')
        TokenUsage.objects.create(
            user=user, prompt_tokens=10, completion_tokens=10, total_tokens=20,
            stars_charged=5, cost_kopecks=500, request_id='cccccccc',
        )
        reconcile_stuck_api_reservations()
        mock_notify.assert_not_called()

    @mock.patch('telegram_bot.notify.notify_admins')
    def test_fresh_reservation_within_grace_window_not_flagged(self, mock_notify):
        user = _user('fresh@t.ru')
        _old_spend(user, 'api:dddddddddddd', minutes_ago=5)  # моложе 20 минут
        reconcile_stuck_api_reservations()
        mock_notify.assert_not_called()

    @mock.patch('telegram_bot.notify.notify_admins')
    def test_too_old_reservation_outside_window_not_flagged(self, mock_notify):
        user = _user('ancient@t.ru')
        _old_spend(user, 'api:eeeeeeeeeeee', minutes_ago=500)  # старше 6 часов
        reconcile_stuck_api_reservations()
        mock_notify.assert_not_called()
