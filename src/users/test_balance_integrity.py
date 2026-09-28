"""Регрессионные тесты для двух денежных багов, найденных 2026-09-28 (ревью,
раунд 3): (1) промокод не должен считаться реальной оплатой (has_made_real_payment)
и открывать медиа-гейт бесплатно; (2) CustomUser.save() не должен обнулять
реальный баланс до гранта при обычном ре-сохранении пользователя, у которого
tariff оказался None (например, после SET_NULL при удалении Tariff админом)."""
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from users.models import PaymentHistory

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}

User = get_user_model()


@override_settings(CACHES=LOCMEM)
class PromoNotRealPaymentTests(TestCase):
    def test_promo_alone_does_not_unlock_media(self):
        u = User.objects.create_user(username='promov', email='promov@t.ru', password='x')
        self.assertFalse(u.has_made_real_payment())
        self.assertTrue(u.is_unpaid_free_user())
        self.assertFalse(u.can_generate_media())

        PaymentHistory.objects.create(
            user=u, payment_type='promo', invoice_id='promo-1',
            amount=0, amount_kopecks=0, pages_count=100, status='success',
            description='promo',
        )
        u.refresh_from_db()
        self.assertFalse(u.has_made_real_payment(), "промокод не должен считаться реальной оплатой")
        self.assertTrue(u.is_unpaid_free_user())
        self.assertFalse(u.can_generate_media(), "медиа-гейт не должен открываться промокодом")

    def test_real_subscription_payment_unlocks(self):
        u = User.objects.create_user(username='realpay', email='realpay@t.ru', password='x')
        PaymentHistory.objects.create(
            user=u, payment_type='subscription', invoice_id='real-1',
            amount=500, amount_kopecks=50000, pages_count=500, status='success',
            description='real',
        )
        u.refresh_from_db()
        self.assertTrue(u.has_made_real_payment())
        self.assertTrue(u.can_generate_media())


@override_settings(CACHES=LOCMEM)
class SaveDoesNotWipeBalanceTests(TestCase):
    def test_ordinary_resave_with_null_tariff_keeps_balance(self):
        u = User.objects.create_user(username='tnone', email='tnone@t.ru', password='x')
        u.refresh_from_db()
        self.assertGreater(u.balance_kopecks, 0)

        # даём пользователю реальный баланс
        u.balance_kopecks = 999999
        u.save(update_fields=['balance_kopecks'])

        # симулируем bulk UPDATE tariff_id=NULL, как делает SET_NULL при удалении Tariff
        User.objects.filter(pk=u.pk).update(tariff=None)
        u.refresh_from_db()
        self.assertIsNone(u.tariff)
        self.assertEqual(u.balance_kopecks, 999999)

        # обычный save() (как update_last_login при логине)
        u.last_login = timezone.now()
        u.save(update_fields=['last_login'])
        u.refresh_from_db()

        self.assertEqual(u.balance_kopecks, 999999, "обычный save() не должен обнулять реальный баланс")
        self.assertIsNotNone(u.tariff, "тариф всё равно должен быть назначен")

    def test_new_user_gets_grant_balance(self):
        u = User.objects.create_user(username='newg', email='newg@t.ru', password='x')
        u.refresh_from_db()
        from users.models import Tariff
        free_tariff = Tariff.get_default_tariff()
        self.assertEqual(u.balance_kopecks, free_tariff.balance_grant_kopecks)
