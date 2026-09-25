"""
Регрессионные тесты по итогам аудита денег 2026-09-25 (после инцидента с бесплатными
ответами Opus через API): каждый тест фиксирует закрытую дыру.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from aitext.models import Category, Chat, GeneratedImage, NeuralNetwork, NeuralNetworkDailyUsage
from users.models import BalanceTransaction, PaymentHistory, PromoCode, WithdrawalRequest

User = get_user_model()
LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


def _user(balance=100000, email='u@t.ru', **extra):
    u = User.objects.create_user(username=email, email=email, password='x')
    u.email_verified = True
    u.save(update_fields=['email_verified'])
    if balance:
        u.set_kopecks(balance)
    for k, v in extra.items():
        setattr(u, k, v)
    if extra:
        u.save(update_fields=list(extra))
    return u


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def _network(**kw):
    cat, _ = Category.objects.get_or_create(name='Test', defaults={'slug': 'test'})
    d = dict(name='M', slug='m', model_name='m', category=cat, cost_per_message=30,
             cost_kopecks=3000, provider='openrouter', is_active=True)
    d.update(kw)
    return NeuralNetwork.objects.create(**d)


@override_settings(MIN_CHARGE_KOPECKS=10, CACHES=LOCMEM, RESEARCH_PRICE_KOPECKS=1000)
class DeepResearchBillingTests(TestCase):
    """Веб Deep Research раньше был полностью бесплатным (платил только бот)."""

    def _chat(self, user):
        return Chat.objects.create(user=user, network=_network(), title='t')

    @mock.patch('aitext.tasks.deep_research_task')
    def test_no_balance_not_enqueued(self, task):
        user = _user(500)
        chat = self._chat(user)
        resp = _client(user).post(f'/api/v1/chats/{chat.id}/research/', {'question': 'why?'}, format='json')
        self.assertEqual(resp.status_code, 402)
        self.assertEqual(resp.json()['error']['code'], 'insufficient_quota')
        task.delay.assert_not_called()
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 500)

    @mock.patch('aitext.tasks.deep_research_task')
    def test_paid_and_enqueued(self, task):
        user = _user(5000)
        chat = self._chat(user)
        resp = _client(user).post(f'/api/v1/chats/{chat.id}/research/', {'question': 'why?'}, format='json')
        self.assertEqual(resp.status_code, 201)
        task.delay.assert_called_once()
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 4000)

    @mock.patch('aitext.tasks.deep_research_task')
    def test_question_length_capped(self, task):
        user = _user(5000)
        chat = self._chat(user)
        resp = _client(user).post(f'/api/v1/chats/{chat.id}/research/', {'question': 'x' * 5000}, format='json')
        self.assertEqual(resp.status_code, 400)
        task.delay.assert_not_called()

    @mock.patch('aitext.tasks.deep_research_task')
    def test_enqueue_failure_refunds(self, task):
        task.delay.side_effect = RuntimeError('broker down')
        user = _user(5000)
        chat = self._chat(user)
        resp = _client(user).post(f'/api/v1/chats/{chat.id}/research/', {'question': 'why?'}, format='json')
        self.assertEqual(resp.status_code, 502)
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 5000)


@override_settings(MIN_CHARGE_KOPECKS=10, CACHES=LOCMEM, UPSCALE_MIN_PRICE_KOPECKS=200)
class UpscaleBillingTests(TestCase):
    """Апскейл картинки из /images/generations (message=null) стоил 0 -> бесплатный апстрим."""

    @mock.patch('aitext.tasks.upscale_generation_task')
    @mock.patch('users.models.CustomUser.has_made_real_payment', return_value=True)
    def test_api_generated_image_has_price_floor(self, _paid, task):
        task.delay.return_value = SimpleNamespace(id='t1')
        user = _user(100000)
        gen = GeneratedImage.objects.create(user=user, image='x.png', media_type='image', message=None)
        resp = _client(user).post(f'/api/v1/generations/{gen.id}/upscale/', {'factor': 2}, format='json')
        self.assertEqual(resp.status_code, 202)
        cost_arg = task.delay.call_args.args[4]
        self.assertGreaterEqual(cost_arg, 200)

    @mock.patch('aitext.tasks.upscale_generation_task')
    @mock.patch('users.models.CustomUser.has_made_real_payment', return_value=True)
    def test_no_balance_blocked_for_api_image(self, _paid, task):
        user = _user(50)
        gen = GeneratedImage.objects.create(user=user, image='x.png', media_type='image', message=None)
        resp = _client(user).post(f'/api/v1/generations/{gen.id}/upscale/', {'factor': 2}, format='json')
        self.assertEqual(resp.status_code, 402)
        task.delay.assert_not_called()


@override_settings(CACHES=LOCMEM)
class WithdrawalTests(TestCase):
    """Отрицательная сумма повышала rub_balance; read-modify-write давал двойной вывод."""

    def _partner(self, rub='100.00'):
        return _user(0, 'p@t.ru', can_convert_to_rub=True, rub_balance=Decimal(rub))

    def test_api_rejects_non_positive(self):
        u = self._partner()
        for bad in ('-50', '0', 'NaN', 'Infinity'):
            r = _client(u).post('/api/v1/referral/withdraw/', {'amount': bad, 'payout_destination': 'wallet'}, format='json')
            self.assertEqual(r.status_code, 400, bad)
        u.refresh_from_db()
        self.assertEqual(u.rub_balance, Decimal('100.00'))
        self.assertEqual(WithdrawalRequest.objects.count(), 0)

    def test_api_cannot_withdraw_more_than_balance_twice(self):
        u = self._partner('100.00')
        c = _client(u)
        r1 = c.post('/api/v1/referral/withdraw/', {'amount': '80', 'payout_destination': 'w'}, format='json')
        r2 = c.post('/api/v1/referral/withdraw/', {'amount': '80', 'payout_destination': 'w'}, format='json')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 400)
        u.refresh_from_db()
        self.assertEqual(u.rub_balance, Decimal('20.00'))
        self.assertEqual(WithdrawalRequest.objects.count(), 1)

    def test_legacy_endpoint_rejects_negative_and_keeps_kopecks(self):
        u = self._partner()
        u.set_kopecks(7777)
        c = _client(u)
        c.force_login(u)
        r = c.post('/users/api/request-withdrawal/', {'amount': '-500', 'payout_destination': 'w'}, format='json')
        self.assertFalse(r.json()['success'])
        r = c.post('/users/api/request-withdrawal/', {'amount': '40', 'payout_destination': 'w'}, format='json')
        self.assertTrue(r.json()['success'], r.json())
        u.refresh_from_db()
        self.assertEqual(u.rub_balance, Decimal('60.00'))
        self.assertEqual(u.balance_kopecks, 7777)  # полный save() раньше затирал баланс


@override_settings(CACHES=LOCMEM)
class PromoLimitTests(TestCase):
    def test_usage_limit_is_atomic_across_users(self):
        from users.promo import redeem_promo_code
        PromoCode.objects.create(code='ONCE', stars=5, kopecks=500, usage_limit=1)
        a, b = _user(0, 'a@t.ru'), _user(0, 'b@t.ru')
        b_before = b.balance_kopecks  # стартовый грант free-тарифа не входит в промо
        self.assertTrue(redeem_promo_code(a, 'ONCE')['ok'])
        second = redeem_promo_code(b, 'ONCE')
        self.assertFalse(second['ok'])
        b.refresh_from_db()
        self.assertEqual(b.balance_kopecks, b_before)
        self.assertEqual(PromoCode.objects.get(code='ONCE').used_count, 1)

    def test_slot_released_when_promo_exhausted_rolls_back_used_record(self):
        from users.models import UsedPromoCode
        from users.promo import redeem_promo_code
        PromoCode.objects.create(code='ONE', stars=1, kopecks=100, usage_limit=1)
        a, b = _user(0, 'a@t.ru'), _user(0, 'b@t.ru')
        redeem_promo_code(a, 'ONE')
        redeem_promo_code(b, 'ONE')
        self.assertFalse(UsedPromoCode.objects.filter(user=b).exists())


@override_settings(CACHES=LOCMEM)
class PaymentFailTests(TestCase):
    def test_unauthenticated_fail_cannot_flip_successful_payment(self):
        u = _user(0)
        p = PaymentHistory.objects.create(user=u, payment_type='pages', amount=100, status='success', invoice_id='777')
        self.client.get('/users/api/payment-fail/?InvId=777')
        self.client.get('/users/pages/payment-fail/?InvId=777')
        p.refresh_from_db()
        self.assertEqual(p.status, 'success')
        pending = PaymentHistory.objects.create(user=u, payment_type='pages', amount=100, status='pending', invoice_id='778')
        self.client.get('/users/api/payment-fail/?InvId=778')
        pending.refresh_from_db()
        self.assertEqual(pending.status, 'failed')  # легитимный pending -> failed работает


@override_settings(CACHES=LOCMEM)
class ApiKeyAccountStateTests(TestCase):
    def _key(self, user):
        from api.models import APIKey
        return APIKey.generate(user, 'k')[1]

    def test_inactive_user_key_rejected(self):
        u = _user(1000)
        raw = self._key(u)
        u.is_active = False
        u.save(update_fields=['is_active'])
        c = APIClient()
        r = c.get('/api/v1/models', HTTP_AUTHORIZATION=f'Bearer {raw}')
        self.assertIn(r.status_code, (401, 403))

    def test_shadow_banned_without_payment_rejected(self):
        u = _user(1000, shadow_banned=True)
        raw = self._key(u)
        r = APIClient().get('/api/v1/models', HTTP_AUTHORIZATION=f'Bearer {raw}')
        self.assertIn(r.status_code, (401, 403))

    def test_normal_user_key_accepted(self):
        u = _user(1000)
        raw = self._key(u)
        r = APIClient().get('/api/v1/models', HTTP_AUTHORIZATION=f'Bearer {raw}')
        self.assertEqual(r.status_code, 200)


class FreeSlotTests(TestCase):
    def test_claim_free_slot_respects_limit(self):
        from django.utils import timezone
        from aitext.limits import claim_free_slot
        u = _user(0)
        n = _network()
        usage = NeuralNetworkDailyUsage.objects.create(user=u, network=n, date=timezone.now().date(), count=0)
        self.assertTrue(claim_free_slot(usage, 2))
        self.assertTrue(claim_free_slot(usage, 2))
        self.assertFalse(claim_free_slot(usage, 2))
        usage.refresh_from_db()
        self.assertEqual(usage.count, 2)

    def test_stale_object_cannot_overshoot(self):
        """Два «параллельных» запроса держат устаревшие копии счётчика - лимит не превышается."""
        from django.utils import timezone
        from aitext.limits import claim_free_slot
        u = _user(0)
        n = _network()
        d = timezone.now().date()
        NeuralNetworkDailyUsage.objects.create(user=u, network=n, date=d, count=1)
        s1 = NeuralNetworkDailyUsage.objects.get(user=u, network=n, date=d)
        s2 = NeuralNetworkDailyUsage.objects.get(user=u, network=n, date=d)
        self.assertTrue(claim_free_slot(s1, 2))
        self.assertFalse(claim_free_slot(s2, 2))


class TelegramBackgroundChargeTests(TestCase):
    def test_charge_once_is_idempotent_and_blocks_duplicates(self):
        from telegram_bot.tasks import _charge_once
        u = _user(1000)
        self.assertTrue(_charge_once(u, 300, 'digest:1:2026-09-25'))
        # повторная доставка задачи: LLM звать нельзя и второй раз не списывать
        self.assertFalse(_charge_once(u, 300, 'digest:1:2026-09-25'))
        u.refresh_from_db()
        self.assertEqual(u.balance_kopecks, 700)

    def test_charge_once_insufficient(self):
        from telegram_bot.tasks import _charge_once
        u = _user(100)
        self.assertFalse(_charge_once(u, 300, 'pollsum:9'))
        u.refresh_from_db()
        self.assertEqual(u.balance_kopecks, 100)
        self.assertFalse(BalanceTransaction.objects.filter(reference='pollsum:9').exists())

    def test_group_charge_org_tuple_is_interpreted(self):
        """_charge_org возвращает (ok, cost_rub): кортеж всегда truthy - раньше провал списания
        орг-баланса не замечался и генерация отдавалась бесплатно."""
        from telegram_bot.handlers import group2
        cfg = SimpleNamespace(organization=SimpleNamespace(id=1))
        with mock.patch('telegram_bot.handlers.group._charge_org', return_value=(False, None)), \
                mock.patch.object(group2, '_cheap_network', return_value=SimpleNamespace(cost_kopecks=100)):
            self.assertFalse(group2._charge(cfg, None))
        with mock.patch('telegram_bot.handlers.group._charge_org', return_value=(True, Decimal('1.00'))), \
                mock.patch.object(group2, '_cheap_network', return_value=SimpleNamespace(cost_kopecks=100)):
            self.assertTrue(group2._charge(cfg, None))
