from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from users.models import BalanceTransaction, PromoCode, Tariff

User = get_user_model()


class BalanceAtomicityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='balance', email='balance@t.ru', password='x')
        self.user.set_kopecks(1000)  # 10 ₽, без записи в ledger важной для этого теста

    def test_spend_kopecks_insufficient_returns_false(self):
        ok = self.user.spend_kopecks(5000, type='spend', reference='order:1')
        self.assertFalse(ok)
        self.user.refresh_from_db(fields=['balance_kopecks'])
        self.assertEqual(self.user.balance_kopecks, 1000)
        self.assertFalse(BalanceTransaction.objects.filter(reference='order:1').exists())

    def test_spend_kopecks_success_creates_ledger_entry(self):
        ok = self.user.spend_kopecks(300, type='spend', reference='order:2')
        self.assertTrue(ok)
        self.user.refresh_from_db(fields=['balance_kopecks'])
        self.assertEqual(self.user.balance_kopecks, 700)
        txn = BalanceTransaction.objects.get(reference='order:2')
        self.assertEqual(txn.amount_kopecks, -300)
        self.assertEqual(txn.balance_after, 700)
        self.assertEqual(txn.type, 'spend')

    def test_add_kopecks_idempotent_by_reference(self):
        self.user.add_kopecks(500, type='topup', reference='invoice:42')
        self.user.add_kopecks(500, type='topup', reference='invoice:42')  # повтор вебхука
        self.user.refresh_from_db(fields=['balance_kopecks'])
        self.assertEqual(self.user.balance_kopecks, 1500)  # начислено только один раз
        self.assertEqual(BalanceTransaction.objects.filter(reference='invoice:42').count(), 1)

    def test_spend_kopecks_idempotent_by_reference(self):
        self.user.spend_kopecks(100, type='spend', reference='req:abc')
        self.user.spend_kopecks(100, type='spend', reference='req:abc')  # повтор celery retry
        self.user.refresh_from_db(fields=['balance_kopecks'])
        self.assertEqual(self.user.balance_kopecks, 900)  # списано только один раз
        self.assertEqual(BalanceTransaction.objects.filter(reference='req:abc').count(), 1)

    def test_different_types_same_reference_do_not_collide(self):
        self.user.spend_kopecks(200, type='spend', reference='media:7')
        self.user.add_kopecks(200, type='refund', reference='media:7')
        self.user.refresh_from_db(fields=['balance_kopecks'])
        self.assertEqual(self.user.balance_kopecks, 1000)  # списано и полностью возвращено
        self.assertEqual(BalanceTransaction.objects.filter(reference='media:7').count(), 2)

    def test_set_kopecks_writes_delta_ledger(self):
        self.user.set_kopecks(5000, reference='admin:grant')
        self.user.refresh_from_db(fields=['balance_kopecks'])
        self.assertEqual(self.user.balance_kopecks, 5000)
        txn = BalanceTransaction.objects.get(reference='admin:grant')
        self.assertEqual(txn.amount_kopecks, 4000)  # 5000 - 1000
        self.assertEqual(txn.type, 'admin')

    def test_legacy_pages_wrappers_still_work(self):
        self.user.spend_pages(3)  # 3 звезды = 300 коп.
        self.user.refresh_from_db(fields=['balance_kopecks', 'pages_count'])
        self.assertEqual(self.user.balance_kopecks, 700)
        self.user.add_pages(2)  # 200 коп.
        self.user.refresh_from_db(fields=['balance_kopecks'])
        self.assertEqual(self.user.balance_kopecks, 900)
        self.assertTrue(self.user.has_enough_pages(9))
        self.assertFalse(self.user.has_enough_pages(10))

    def test_spend_zero_or_negative_is_noop_success(self):
        self.assertTrue(self.user.spend_kopecks(0))
        self.user.refresh_from_db(fields=['balance_kopecks'])
        self.assertEqual(self.user.balance_kopecks, 1000)

    def test_fractional_spends_do_not_drift_pages_count(self):
        # Дельта с floor давала бы pages_count=10 после двух списаний по 0,50 ₽;
        # пересчёт от фактического баланса — корректные 9.
        self.user.spend_kopecks(50, type='spend', reference='frac:1')
        self.user.spend_kopecks(50, type='spend', reference='frac:2')
        self.user.refresh_from_db(fields=['balance_kopecks', 'pages_count'])
        self.assertEqual(self.user.balance_kopecks, 900)
        self.assertEqual(self.user.pages_count, 9)


class DualWriteSyncTests(TestCase):
    """Проверяет авто-синхронизацию kopecks-полей в save() для справочников."""

    def test_tariff_save_syncs_kopecks(self):
        tariff = Tariff.objects.create(
            display_name='Test', pages_count=50, price=490,
            referral_bonus_stars=5,
        )
        self.assertEqual(tariff.balance_grant_kopecks, 5000)
        self.assertEqual(tariff.referral_bonus_kopecks, 500)

    def test_promocode_save_syncs_kopecks(self):
        promo = PromoCode.objects.create(code='WELCOME10', stars=10)
        self.assertEqual(promo.kopecks, 1000)

    def test_free_tariff_grant_matches_default_pages(self):
        free = Tariff.get_default_tariff()
        user = User.objects.create_user(username='free', email='free@t.ru', password='x')
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, free.balance_grant_kopecks)
        self.assertEqual(user.balance_kopecks, free.pages_count * 100)


@override_settings(MIN_CHARGE_KOPECKS=10)
class ActivateTariffTests(TestCase):
    def test_activate_paid_tariff_adds_balance_and_payment_history(self):
        from users.models import PaymentHistory

        user = User.objects.create_user(username='payer', email='payer@t.ru', password='x')
        starting_balance = user.balance_kopecks
        tariff = Tariff.objects.create(display_name='Pro', pages_count=500, price=4990)

        user.activate_paid_tariff(tariff, payment_data={'invoice_id': 'inv-100', 'payment_id': 'p-1'})
        user.refresh_from_db(fields=['balance_kopecks', 'tariff'])

        self.assertEqual(user.balance_kopecks, starting_balance + 50000)  # pages_count=500 -> ×100
        self.assertEqual(user.tariff_id, tariff.id)
        payment = PaymentHistory.objects.get(invoice_id='inv-100')
        self.assertEqual(payment.amount_kopecks, 499000)  # amount_kopecks зеркалит amount (уплаченные ₽), не грант

    def test_activate_paid_tariff_idempotent_on_retry(self):
        user = User.objects.create_user(username='payer2', email='payer2@t.ru', password='x')
        starting_balance = user.balance_kopecks
        tariff = Tariff.objects.create(display_name='Pro2', pages_count=100, price=990)

        user.activate_paid_tariff(tariff, payment_data={'invoice_id': 'inv-200'})
        user.add_kopecks(tariff.balance_grant_kopecks, type='subscription', reference='inv-200')  # ретрай вебхука
        user.refresh_from_db(fields=['balance_kopecks'])

        self.assertEqual(user.balance_kopecks, starting_balance + 10000)  # начислено один раз


@override_settings(
    ROBOKASSA_PASS2='testpass2', MIN_CHARGE_KOPECKS=10,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class RobokassaWebhookIdempotencyTests(TestCase):
    """
    Требует непустой settings.SECRET_KEY (используется для подписи сессионных cookie
    в request-cycle через Client()). В этом окружении SECRET_KEY пуст по умолчанию
    (env-переменная не задана) — override_settings для SECRET_KEY здесь не используется,
    т.к. его teardown-логика сама обращается к settings.SECRET_KEY и падает на пустом
    значении. Раннер должен быть запущен с SECRET_KEY=<любое> в окружении.
    """
    """payment_success (Result URL) должен быть безопасен к повтору вебхука Robokassa."""

    def _signed_post(self, out_sum, inv_id):
        import hashlib
        from django.test import Client
        sig = hashlib.md5(f"{out_sum}:{inv_id}:testpass2".encode()).hexdigest().upper()
        return Client().post('/users/api/payment-success/', {
            'OutSum': out_sum, 'InvId': inv_id, 'SignatureValue': sig,
        })

    def test_pages_purchase_webhook_retry_does_not_double_credit(self):
        from users.models import PaymentHistory

        user = User.objects.create_user(username='rbkbuyer', email='rbkbuyer@t.ru', password='x')
        starting_balance = user.balance_kopecks
        payment = PaymentHistory.objects.create(
            user=user, payment_type='pages', invoice_id='rbk-1',
            amount=500, pages_count=500, status='pending',
        )

        r1 = self._signed_post('500.00', 'rbk-1')
        self.assertEqual(r1.status_code, 200)
        user.refresh_from_db(fields=['balance_kopecks'])
        self.assertEqual(user.balance_kopecks, starting_balance + 50000)

        # Повтор вебхука (Robokassa ретраит при неполучении "OK" вовремя)
        r2 = self._signed_post('500.00', 'rbk-1')
        self.assertEqual(r2.status_code, 200)
        user.refresh_from_db(fields=['balance_kopecks'])
        self.assertEqual(user.balance_kopecks, starting_balance + 50000)  # не задвоилось

    def test_invalid_signature_rejected(self):
        from django.test import Client
        r = Client().post('/users/api/payment-success/', {
            'OutSum': '100.00', 'InvId': 'rbk-2', 'SignatureValue': 'WRONG',
        })
        self.assertEqual(r.status_code, 400)


class LegalDocumentsCommandTests(TestCase):
    """setup_legal_documents: заполнение оферты и политики конфиденциальности."""

    def test_creates_documents(self):
        from django.core.management import call_command
        from users.models import LegalDocument

        call_command('setup_legal_documents')

        terms = LegalDocument.objects.get(document_type='terms')
        privacy = LegalDocument.objects.get(document_type='privacy')

        for doc in (terms, privacy):
            self.assertIn('aineron.ru', doc.content)
            self.assertNotIn('yurist', doc.content)
            self.assertIn('ИВАЩЕНКО', doc.content)
            self.assertIn('220805856949', doc.content)  # ИНН
            self.assertIn('support@aineron.ru', doc.content)

        # Условия Робокассы: рекуррентные платежи и отказ от подписки в оферте
        self.assertIn('рекуррентные платежи', terms.content)
        self.assertIn('автоматическое списание', terms.content)
        self.assertIn('отказаться от подписки', terms.content)

    def test_does_not_overwrite_admin_edits(self):
        from django.core.management import call_command
        from users.models import LegalDocument

        LegalDocument.objects.create(
            document_type='terms', title='Правки из админки', content='<p>Кастом</p>',
        )
        call_command('setup_legal_documents')
        self.assertEqual(LegalDocument.objects.get(document_type='terms').content, '<p>Кастом</p>')

        call_command('setup_legal_documents', '--force')
        self.assertIn('aineron.ru', LegalDocument.objects.get(document_type='terms').content)

    def test_fills_placeholder(self):
        from django.core.management import call_command
        from users.models import LegalDocument

        # get_privacy() создаёт документ с placeholder — команда должна его заполнить
        LegalDocument.get_privacy()
        call_command('setup_legal_documents')
        self.assertIn('aineron.ru', LegalDocument.objects.get(document_type='privacy').content)
