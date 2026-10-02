"""
2026-10-02 (аудит безопасности, №28): add_kopecks()/PaymentHistory раньше
выполнялись ПОСЛЕ коммита atomic-блока, где промокод уже помечался
использованным (UsedPromoCode + used_count++). Падение между коммитом блока
и add_kopecks() (обрыв соединения с БД, необработанное исключение) сжигало
код без начисления денег НАВСЕГДА, без возможности повтора. Теперь начисление
внутри того же atomic-блока: либо оба шага коммитятся, либо оба откатываются.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TestCase, override_settings

from users.models import PaymentHistory, PromoCode, UsedPromoCode
from users.promo import redeem_promo_code

User = get_user_model()
LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


def _user(balance=0, email='promoatomic@t.ru'):
    u = User.objects.create_user(username=email, email=email, password='x')
    u.set_kopecks(balance)
    return u


@override_settings(CACHES=LOCMEM)
class PromoAtomicityTests(TestCase):
    def test_happy_path_credits_and_marks_used(self):
        promo = PromoCode.objects.create(code='HAPPY', stars=5, kopecks=500, usage_limit=1)
        user = _user()
        result = redeem_promo_code(user, 'HAPPY')
        self.assertTrue(result['ok'])
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 500)
        self.assertTrue(UsedPromoCode.objects.filter(user=user, promo_code=promo).exists())
        self.assertEqual(PromoCode.objects.get(pk=promo.pk).used_count, 1)

    def test_crash_during_credit_rolls_back_usage_too(self):
        """Ровно баг из аудита: имитируем падение ПОСЛЕ отметки использования,
        но ДО успешного начисления (add_kopecks бросает исключение) - раньше
        это было ФИЗИЧЕСКИ невозможно откатить (разные транзакции), теперь
        обе стороны в одном atomic-блоке - код должен остаться неиспользованным,
        деньги не должны пропасть."""
        promo = PromoCode.objects.create(code='CRASH', stars=5, kopecks=500, usage_limit=1)
        user = _user()

        with mock.patch.object(User, 'add_kopecks', side_effect=DatabaseError('connection lost')):
            with self.assertRaises(DatabaseError):
                redeem_promo_code(user, 'CRASH')

        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 0)  # не списано в никуда
        self.assertFalse(UsedPromoCode.objects.filter(user=user, promo_code=promo).exists())
        self.assertEqual(PromoCode.objects.get(pk=promo.pk).used_count, 0)
        self.assertFalse(PaymentHistory.objects.filter(user=user, payment_type='promo').exists())

        # Код не сгорел - пользователь может погасить его заново (mock.patch
        # выше уже вышел из контекста, add_kopecks снова ведёт себя нормально).
        retry = redeem_promo_code(user, 'CRASH')
        self.assertTrue(retry['ok'])
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 500)

    def test_crash_during_payment_history_also_rolls_back(self):
        """Тот же принцип для второго шага внутри блока (PaymentHistory)."""
        promo = PromoCode.objects.create(code='CRASH2', stars=5, kopecks=500, usage_limit=1)
        user = _user()

        with mock.patch('users.promo.PaymentHistory.objects.create', side_effect=DatabaseError('boom')):
            with self.assertRaises(DatabaseError):
                redeem_promo_code(user, 'CRASH2')

        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 0)
        self.assertFalse(UsedPromoCode.objects.filter(user=user, promo_code=promo).exists())
        self.assertEqual(PromoCode.objects.get(pk=promo.pk).used_count, 0)
