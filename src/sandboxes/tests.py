"""
Тесты Sandbox API: биллинг (резерв/settle/идемпотентность), квоты, reconcile.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from users.models import BalanceTransaction

from . import billing
from .models import SandboxSession

User = get_user_model()

_LOCMEM_CACHE = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
}


def make_user(email='sbx@test.ru', kopecks=100_000):
    user = User.objects.create(email=email, username=email.split('@')[0])
    # Новый пользователь получает стартовый грант сигналом — для детерминизма
    # тестов выставляем баланс точно.
    User.objects.filter(pk=user.pk).update(
        balance_kopecks=kopecks, pages_count=kopecks // 100,
    )
    user.refresh_from_db()
    return user


def make_session(user, size='standard', ttl=300, **kwargs):
    return SandboxSession.objects.create(
        user=user, template='base', size=size, ttl_seconds=ttl, **kwargs,
    )


@override_settings(CACHES=_LOCMEM_CACHE)
class BillingTests(TestCase):
    def test_reserve_charges_max_cost(self):
        user = make_user()
        session = make_session(user, size='standard', ttl=300)  # 5 мин × 100 коп.
        before = user.balance_kopecks
        self.assertTrue(billing.reserve(user, session))
        user.refresh_from_db()
        self.assertEqual(before - user.balance_kopecks, 500)
        session.refresh_from_db()
        self.assertEqual(session.reserved_kopecks, 500)

    def test_settle_refunds_unused_minutes(self):
        user = make_user()
        session = make_session(user, size='standard', ttl=300)
        billing.reserve(user, session)
        # Работала 90 секунд → биллим 2 минуты (округление вверх), возврат 300
        charged = billing.settle(session, 90)
        self.assertEqual(charged, 200)
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 100_000 - 200)

    def test_settle_is_idempotent(self):
        user = make_user()
        session = make_session(user, size='standard', ttl=300)
        billing.reserve(user, session)
        billing.settle(session, 60)
        balance_after_first = User.objects.get(pk=user.pk).balance_kopecks
        # Повтор (гонка DELETE и reconcile) — возврат по тому же reference не задваивается
        billing.settle(session, 60)
        self.assertEqual(User.objects.get(pk=user.pk).balance_kopecks, balance_after_first)
        refunds = BalanceTransaction.objects.filter(
            user=user, reference=f'sandbox:{session.pk}:settle',
        ).count()
        self.assertEqual(refunds, 1)

    def test_settle_minimum_one_minute(self):
        user = make_user()
        session = make_session(user, size='small', ttl=120)  # 2 мин × 50
        billing.reserve(user, session)
        charged = billing.settle(session, 3)  # 3 секунды → минимум 1 минута
        self.assertEqual(charged, 50)

    def test_settle_never_exceeds_reserve(self):
        user = make_user()
        session = make_session(user, size='standard', ttl=60)
        billing.reserve(user, session)  # 100 коп.
        charged = billing.settle(session, 3600)  # аномальная длительность
        self.assertEqual(charged, 100)

    def test_refund_full_on_failed_start(self):
        user = make_user()
        session = make_session(user, size='standard', ttl=600)
        billing.reserve(user, session)
        billing.refund_full(session)
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 100_000)
        session.refresh_from_db()
        self.assertEqual(session.state, SandboxSession.State.FAILED)

    def test_reserve_insufficient_balance(self):
        user = make_user(kopecks=100)  # 1 ₽ < 5 ₽ резерва
        session = make_session(user, size='standard', ttl=300)
        self.assertFalse(billing.reserve(user, session))
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 100)


@override_settings(CACHES=_LOCMEM_CACHE)
class ReconcileTests(TestCase):
    def test_reconcile_closes_expired_sessions(self):
        from .tasks import reconcile_sandbox_billing

        user = make_user()
        session = make_session(user, size='standard', ttl=300)
        billing.reserve(user, session)
        session.state = SandboxSession.State.RUNNING
        session.started_at = timezone.now() - timedelta(seconds=400)
        session.expires_at = timezone.now() - timedelta(seconds=100)
        session.save()

        with mock.patch('sandboxes.client.kill') as kill_mock:
            from sandboxes.client import PreviewServiceError
            kill_mock.side_effect = PreviewServiceError('gone', status=404)
            closed = reconcile_sandbox_billing()

        self.assertEqual(closed, 1)
        session.refresh_from_db()
        self.assertEqual(session.state, SandboxSession.State.EXPIRED)
        # kill не ответил длительностью → биллим полный TTL (5 мин = весь резерв)
        self.assertEqual(session.charged_kopecks, 500)

    def test_reconcile_uses_service_duration(self):
        from .tasks import reconcile_sandbox_billing

        user = make_user()
        session = make_session(user, size='standard', ttl=600)
        billing.reserve(user, session)  # 10 мин = 1000 коп.
        session.state = SandboxSession.State.RUNNING
        session.expires_at = timezone.now() - timedelta(seconds=10)
        session.save()

        with mock.patch('sandboxes.client.kill', return_value={'ok': True, 'duration_seconds': 130}):
            reconcile_sandbox_billing()

        session.refresh_from_db()
        self.assertEqual(session.charged_kopecks, 300)  # ceil(130/60)=3 мин
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 100_000 - 300)

    def test_reconcile_skips_active_sessions(self):
        from .tasks import reconcile_sandbox_billing

        user = make_user()
        session = make_session(user)
        session.state = SandboxSession.State.RUNNING
        session.expires_at = timezone.now() + timedelta(seconds=300)
        session.save()
        self.assertEqual(reconcile_sandbox_billing(), 0)


class QuotaTests(TestCase):
    def test_concurrent_limit(self):
        from .quotas import check_concurrent

        user = make_user(kopecks=0)
        for _ in range(3):
            s = make_session(user)
            s.state = SandboxSession.State.RUNNING
            s.save()
        allowed, active, limit = check_concurrent(user)
        self.assertFalse(allowed)
        self.assertEqual(active, 3)

    def test_stopped_sessions_do_not_count(self):
        from .quotas import check_concurrent

        user = make_user(kopecks=0)
        for _ in range(3):
            s = make_session(user)
            s.state = SandboxSession.State.STOPPED
            s.save()
        allowed, active, _ = check_concurrent(user)
        self.assertTrue(allowed)
        self.assertEqual(active, 0)


class PublicIdTests(TestCase):
    def test_roundtrip(self):
        user = make_user(kopecks=0)
        session = make_session(user)
        parsed = SandboxSession.parse_public_id(session.public_id)
        self.assertEqual(parsed, session.id)

    def test_invalid_ids(self):
        self.assertIsNone(SandboxSession.parse_public_id('sbx_zzz'))
        self.assertIsNone(SandboxSession.parse_public_id('abc'))
        self.assertIsNone(SandboxSession.parse_public_id('sbx_'))
