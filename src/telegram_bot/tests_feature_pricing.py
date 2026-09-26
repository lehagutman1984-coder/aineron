"""
ITEM 1 (STATUS_AND_BACKLOG_PLAN_2026-09-25.md): цена Agent / Deep Research зависит от
выбранной модели, возвраты идут строго по леджеру, шаги агента урезаются, секретарь не
использует слишком дорогую модель. Всё за флагом FEATURE_MODEL_PRICING_ENABLED.
"""
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from aitext.models import Category, Chat, DeepResearch, Message, NeuralNetwork
from core import feature_pricing as fp
from telegram_bot.models import AgentRun, TelegramUser
from users.models import BalanceTransaction

User = get_user_model()
LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
ON = dict(FEATURE_MODEL_PRICING_ENABLED=True, AGENT_PRICE_KOPECKS=500, RESEARCH_PRICE_KOPECKS=1000,
          AGENT_MODEL_MULTIPLIER=5, RESEARCH_MODEL_MULTIPLIER=2, AGENT_STEP_MAX_TOKENS=700,
          AGENT_OBSERVATION_CHARS=3000, BUSINESS_MAX_MODEL_KOPECKS=300, MIN_CHARGE_KOPECKS=10)
OFF = dict(ON, FEATURE_MODEL_PRICING_ENABLED=False)


def _net(slug, cost, **kw):
    cat, _ = Category.objects.get_or_create(name='T', defaults={'slug': 't'})
    d = dict(name=slug.upper(), slug=slug, model_name=slug, category=cat, cost_per_message=1,
             cost_kopecks=cost, provider='openrouter', is_active=True)
    d.update(kw)
    return NeuralNetwork.objects.create(**d)


def _user(balance=100000, email='u@t.ru'):
    u = User.objects.create_user(username=email, email=email, password='x')
    u.email_verified = True
    u.save(update_fields=['email_verified'])
    u.set_kopecks(balance)
    return u


class PriceFormulaTests(TestCase):
    def setUp(self):
        self.cheap = _net('flash', 8)
        self.mid = _net('sonnet', 284)
        self.opus = _net('opus', 709)

    @override_settings(**OFF)
    def test_flag_off_is_flat(self):
        self.assertEqual(fp.feature_price_kopecks('agent', self.opus), 500)
        self.assertEqual(fp.feature_price_kopecks('research', self.opus), 1000)

    @override_settings(**ON)
    def test_cheap_model_stays_at_flat_price(self):
        self.assertEqual(fp.feature_price_kopecks('agent', self.cheap), 500)
        self.assertEqual(fp.feature_price_kopecks('research', self.cheap), 1000)

    @override_settings(**ON)
    def test_expensive_model_scales(self):
        self.assertEqual(fp.feature_price_kopecks('agent', self.opus), 3545)      # ceil(5 * 709)
        self.assertEqual(fp.feature_price_kopecks('research', self.opus), 1418)   # 2 * 709
        self.assertEqual(fp.feature_price_kopecks('agent', self.mid), 1420)
        self.assertEqual(fp.feature_price_kopecks('research', self.mid), 1000)    # 568 < flat

    @override_settings(**ON)
    def test_resolve_uses_default_network_else_cheapest(self):
        u = _user()
        tg = TelegramUser.objects.create(user=u, telegram_id=111, default_network=self.opus)
        net, price = fp.resolve_feature('agent', tg)
        self.assertEqual((net.pk, price), (self.opus.pk, 3545))
        tg.default_network = None
        net, price = fp.resolve_feature('agent', tg)
        self.assertEqual(net.pk, self.cheap.pk)  # самая дешёвая
        self.assertEqual(price, 500)

    @override_settings(**ON)
    def test_inactive_default_network_falls_back(self):
        u = _user()
        NeuralNetwork.objects.filter(pk=self.opus.pk).update(is_active=False)
        self.opus.refresh_from_db()
        tg = TelegramUser.objects.create(user=u, telegram_id=112, default_network=self.opus)
        net, _ = fp.resolve_feature('agent', tg)
        self.assertEqual(net.pk, self.cheap.pk)

    @override_settings(**ON)
    def test_agent_params_switch_with_flag(self):
        self.assertEqual(fp.agent_step_max_tokens(), 700)
        self.assertEqual(fp.agent_observation_chars(), 3000)
        with override_settings(**OFF):
            self.assertEqual(fp.agent_step_max_tokens(), 1800)
            self.assertEqual(fp.agent_observation_chars(), 4000)


class LedgerRefundTests(TestCase):
    def test_refund_is_exact_ledger_amount_and_idempotent(self):
        u = _user(10000)
        u.spend_kopecks(1418, type='spend', reference='research:1')
        self.assertEqual(fp.spent_kopecks(u, 'research:1'), 1418)
        self.assertTrue(fp.refund_spend_by_reference(u, 'research:1'))
        self.assertTrue(fp.refund_spend_by_reference(u, 'research:1'))  # повтор - no-op
        u.refresh_from_db()
        self.assertEqual(u.balance_kopecks, 10000)
        self.assertEqual(BalanceTransaction.objects.filter(user=u, type='refund', reference='research:1').count(), 1)

    def test_no_spend_no_refund(self):
        u = _user(10000)
        self.assertFalse(fp.refund_spend_by_reference(u, 'research:404'))
        u.refresh_from_db()
        self.assertEqual(u.balance_kopecks, 10000)


class ResearchEngineTests(TestCase):
    def test_plan_queries_truncated_to_n(self):
        from aitext import tasks as t
        many = '[' + ','.join(f'"q{i}"' for i in range(10)) + ']'
        client = mock.MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=many))])
        with mock.patch.object(t, 'get_laozhang_client', return_value=client):
            self.assertEqual(len(t._plan_research_queries('q', 'm', n=5)), 5)

    def test_synthesis_failure_raises_instead_of_fake_report(self):
        from aitext import tasks as t
        client = mock.MagicMock()
        client.chat.completions.create.side_effect = RuntimeError('boom')
        with mock.patch.object(t, 'get_laozhang_client', return_value=client):
            with self.assertRaises(RuntimeError):
                t._synthesize_report('q', [], 'm')
        client.chat.completions.create.side_effect = None
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='   '))])
        with mock.patch.object(t, 'get_laozhang_client', return_value=client):
            with self.assertRaises(RuntimeError):
                t._synthesize_report('q', [], 'm')

    @override_settings(**ON)
    def test_task_synthesis_error_marks_error_and_refunds_exact_amount(self):
        from aitext import tasks as t
        u = _user(50000)
        net = _net('opus', 709)
        chat = Chat.objects.create(user=u, network=net, title='r')
        msg = Message.objects.create(chat=chat, role='assistant', content='', status='pending')
        research = DeepResearch.objects.create(chat=chat, message=msg, question='why')
        u.spend_kopecks(1418, type='spend', reference=f'research:{msg.id}')
        with mock.patch.object(t, '_plan_research_queries', return_value=['a']), \
                mock.patch.object(t, '_kb_search_chunks', return_value=[]), \
                mock.patch.object(t, '_web_search_chunks', return_value=[{'text': 'x', 'source': 's', 'kind': 'web'}]), \
                mock.patch.object(t, '_synthesize_report', side_effect=RuntimeError('boom')):
            t.deep_research_task.apply(args=[research.pk])
        research.refresh_from_db()
        u.refresh_from_db()
        self.assertEqual(research.status, 'error')
        self.assertEqual(u.balance_kopecks, 50000)  # возвращено ровно 1418


@override_settings(CACHES=LOCMEM, **ON)
class WebResearchPricingTests(TestCase):
    def setUp(self):
        self.opus = _net('opus', 709)
        self.u = _user(100000)
        self.chat = Chat.objects.create(user=self.u, network=self.opus, title='c')
        self.c = APIClient()
        self.c.force_authenticate(self.u)

    def test_quote_matches_charge(self):
        q = self.c.get(f'/api/v1/chats/{self.chat.id}/research/quote/').json()
        self.assertEqual(q['price_kopecks'], 1418)
        with mock.patch('aitext.tasks.deep_research_task') as task:
            r = self.c.post(f'/api/v1/chats/{self.chat.id}/research/', {'question': 'why'}, format='json')
        self.assertEqual(r.status_code, 201)
        task.delay.assert_called_once()
        row = BalanceTransaction.objects.get(user=self.u, type='spend', reference__startswith='research:')
        self.assertEqual(-row.amount_kopecks, q['price_kopecks'])  # цена в котировке == списанная

    def test_402_on_model_price_not_flat(self):
        self.u.set_kopecks(1200)  # хватило бы на плоские 1000, но не на 1418
        with mock.patch('aitext.tasks.deep_research_task') as task:
            r = self.c.post(f'/api/v1/chats/{self.chat.id}/research/', {'question': 'why'}, format='json')
        self.assertEqual(r.status_code, 402)
        self.assertEqual(r.json()['error']['required_kopecks'], 1418)
        task.delay.assert_not_called()


@override_settings(**ON)
class BotResearchStartTests(TestCase):
    def test_spend_equals_shown_price_and_uses_selected_network(self):
        from telegram_bot.handlers.research_cmd import _start_research
        opus, cheap = _net('opus', 709), _net('flash', 8)
        u = _user(100000)
        tg = TelegramUser.objects.create(user=u, telegram_id=201, default_network=cheap)
        with mock.patch('aitext.tasks.deep_research_task') as task:
            rid, msg_id = _start_research(tg, 'why', opus.pk, 1418)
        self.assertIsNotNone(rid)
        self.assertEqual(Chat.objects.get(deep_researches__pk=rid).network_id, opus.pk)  # не default_network
        row = BalanceTransaction.objects.get(user=u, type='spend', reference=f'research:{msg_id}')
        self.assertEqual(-row.amount_kopecks, 1418)
        task.delay.assert_called_once()

    def test_insufficient_balance_creates_nothing(self):
        from telegram_bot.handlers.research_cmd import _start_research
        opus = _net('opus', 709)
        u = _user(500)
        tg = TelegramUser.objects.create(user=u, telegram_id=202, default_network=opus)
        with mock.patch('aitext.tasks.deep_research_task') as task:
            rid, reason = _start_research(tg, 'why', opus.pk, 1418)
        self.assertIsNone(rid)
        self.assertEqual(reason, 'no_balance')
        self.assertEqual(Chat.objects.count(), 0)
        task.delay.assert_not_called()


def _completion(content, finish='stop'):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish)])


class RunAgentTests(TestCase):
    def _run(self, user, price, net, responses):
        from telegram_bot import tasks
        run = AgentRun.objects.create(user=user, goal='goal')
        client = mock.MagicMock()
        client.chat.completions.create.side_effect = responses
        with mock.patch('aitext.tasks.get_laozhang_client', return_value=client):
            tasks.run_agent.apply(args=[run.pk, price, net.pk if net else None])
        run.refresh_from_db()
        return run, client

    @override_settings(**ON)
    def test_uses_passed_network_and_price_and_step_cap(self):
        opus, cheap = _net('opus', 709), _net('flash', 8)
        u = _user(100000)
        finish = '{"action": "finish", "input": "REPORT", "reason": "ok"}'
        run, client = self._run(u, 3545, opus, [_completion(finish)])
        self.assertEqual(run.status, 'done')
        call = client.chat.completions.create.call_args.kwargs
        self.assertEqual(call['model'], 'opus')       # выбранная на экране модель
        self.assertEqual(call['max_tokens'], 700)     # урезанный cap шага
        row = BalanceTransaction.objects.get(user=u, type='spend', reference=f'agent:{run.pk}')
        self.assertEqual(-row.amount_kopecks, 3545)

    @override_settings(**ON)
    def test_truncated_finish_is_retried_with_full_limit(self):
        opus = _net('opus', 709)
        u = _user(100000)
        cut = _completion('{"action": "finish", "input": "REPORT beg', finish='length')
        full = _completion('{"action": "finish", "input": "FULL REPORT", "reason": "ok"}')
        run, client = self._run(u, 3545, opus, [cut, full])
        self.assertEqual(run.result_md, 'FULL REPORT')  # а не обрезок
        caps = [c.kwargs['max_tokens'] for c in client.chat.completions.create.call_args_list]
        self.assertEqual(caps, [700, 1800])

    @override_settings(**ON)
    def test_error_refunds_exact_charged_amount(self):
        opus = _net('opus', 709)
        u = _user(100000)
        run, _ = self._run(u, 3545, opus, [RuntimeError('boom')])
        self.assertEqual(run.status, 'error')
        u.refresh_from_db()
        self.assertEqual(u.balance_kopecks, 100000)

    @override_settings(**ON)
    def test_no_balance_for_model_price(self):
        opus = _net('opus', 709)
        u = _user(1000)  # хватило бы на плоские 500
        run, client = self._run(u, 3545, opus, [_completion('x')])
        self.assertEqual(run.status, 'error')
        self.assertEqual(run.error, 'no_balance')
        client.chat.completions.create.assert_not_called()

    @override_settings(**ON)
    def test_redelivery_does_not_run_twice(self):
        opus = _net('opus', 709)
        u = _user(100000)
        finish = '{"action": "finish", "input": "R", "reason": "ok"}'
        run, _ = self._run(u, 3545, opus, [_completion(finish)])
        from telegram_bot import tasks
        client = mock.MagicMock()
        with mock.patch('aitext.tasks.get_laozhang_client', return_value=client):
            tasks.run_agent.apply(args=[run.pk, 3545, opus.pk])
        client.chat.completions.create.assert_not_called()  # повторная доставка - без второго прогона
        self.assertEqual(BalanceTransaction.objects.filter(user=u, type='spend', reference=f'agent:{run.pk}').count(), 1)

    @override_settings(**OFF)
    def test_flag_off_keeps_legacy_behaviour(self):
        cheap = _net('flash', 8)
        u = _user(100000)
        finish = '{"action": "finish", "input": "R", "reason": "ok"}'
        run, client = self._run(u, None, None, [_completion(finish)])  # старая постановка: без параметров
        self.assertEqual(run.status, 'done')
        self.assertEqual(client.chat.completions.create.call_args.kwargs['max_tokens'], 1800)
        row = BalanceTransaction.objects.get(user=u, type='spend', reference=f'agent:{run.pk}')
        self.assertEqual(-row.amount_kopecks, 500)


@override_settings(CACHES=LOCMEM, **ON)
class WebAgentTests(TestCase):
    def setUp(self):
        self.opus = _net('opus', 709)
        self.u = _user(100000)
        self.c = APIClient()
        self.c.force_authenticate(self.u)

    def test_quote_and_start_share_the_price(self):
        TelegramUser.objects.create(user=self.u, telegram_id=301, default_network=self.opus)
        q = self.c.get('/api/v1/agent/quote/').json()
        self.assertEqual(q['price_kopecks'], 3545)
        with mock.patch('telegram_bot.tasks.run_agent') as task:
            r = self.c.post('/api/v1/agent/', {'goal': 'do it'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['price_kopecks'], 3545)
        args = task.delay.call_args.args
        self.assertEqual(args[1:], (3545, self.opus.pk))

    def test_402_reports_model_price(self):
        TelegramUser.objects.create(user=self.u, telegram_id=302, default_network=self.opus)
        self.u.set_kopecks(1000)
        with mock.patch('telegram_bot.tasks.run_agent') as task:
            r = self.c.post('/api/v1/agent/', {'goal': 'do it'}, format='json')
        self.assertEqual(r.status_code, 402)
        self.assertEqual(r.json()['error']['required_kopecks'], 3545)
        task.delay.assert_not_called()


class SecretaryModelTests(TestCase):
    def setUp(self):
        self.cheap = _net('flash', 8)
        self.opus = _net('opus', 709)
        self.haiku = _net('haiku', 142)
        u = _user()
        self.tg = TelegramUser.objects.create(user=u, telegram_id=401, default_network=self.opus)

    @override_settings(**ON)
    def test_expensive_default_is_replaced(self):
        self.assertEqual(fp.resolve_business_network(self.tg).pk, self.cheap.pk)

    @override_settings(BUSINESS_FALLBACK_MODEL_SLUG='haiku', **ON)
    def test_fallback_slug_used(self):
        self.assertEqual(fp.resolve_business_network(self.tg).pk, self.haiku.pk)

    @override_settings(**ON)
    def test_model_within_threshold_kept(self):
        self.tg.default_network = self.haiku
        self.assertEqual(fp.resolve_business_network(self.tg).pk, self.haiku.pk)

    @override_settings(**OFF)
    def test_flag_off_keeps_owner_model(self):
        self.assertEqual(fp.resolve_business_network(self.tg).pk, self.opus.pk)


@override_settings(**ON)
class ReapStuckResearchTests(TestCase):
    def _make(self, age_minutes, spend=True):
        from datetime import timedelta
        from django.utils import timezone
        u = _user(50000)
        net = _net('opus', 709)
        chat = Chat.objects.create(user=u, network=net, title='r')
        msg = Message.objects.create(chat=chat, role='assistant', content='', status='pending')
        research = DeepResearch.objects.create(chat=chat, message=msg, question='q', status='running')
        DeepResearch.objects.filter(pk=research.pk).update(created_at=timezone.now() - timedelta(minutes=age_minutes))
        if spend:
            u.spend_kopecks(1418, type='spend', reference=f'research:{msg.id}')
        return u, research, msg

    def test_old_stuck_research_is_closed_and_refunded_exactly(self):
        from aitext.tasks import reap_stuck_researches
        u, research, msg = self._make(30)
        self.assertEqual(reap_stuck_researches(), 1)
        research.refresh_from_db()
        msg.refresh_from_db()
        u.refresh_from_db()
        self.assertEqual(research.status, 'error')
        self.assertEqual(msg.status, 'failed')
        self.assertEqual(u.balance_kopecks, 50000)
        self.assertEqual(reap_stuck_researches(), 0)  # повтор - ничего лишнего

    def test_fresh_research_untouched(self):
        from aitext.tasks import reap_stuck_researches
        u, research, _ = self._make(5)
        self.assertEqual(reap_stuck_researches(), 0)
        research.refresh_from_db()
        self.assertEqual(research.status, 'running')

    def test_old_unpaid_research_is_closed_without_refund(self):
        from aitext.tasks import reap_stuck_researches
        u, research, _ = self._make(30, spend=False)  # запущено до введения оплаты
        reap_stuck_researches()
        u.refresh_from_db()
        self.assertEqual(u.balance_kopecks, 50000)
