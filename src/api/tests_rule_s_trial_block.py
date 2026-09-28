"""
ITEM 1 часть B, Rule S: дорогая модель вообще не предлагается пробному (никогда не
плативше­му) пользователю - на всех текстовых точках входа (chats.py create/send/
stream/regenerate, compare.py). Rule D (динамический блок/клэмп) для этих же путей
проверен отдельно: aitext/test_generate_ai_response_free_tier.py (Celery-путь) и
здесь же для StreamMessageView (единственный путь со своим инлайн-вызовом апстрима).
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from aitext.models import Category, Chat, Message, NeuralNetwork
from users.models import BalanceTransaction, PaymentHistory, Tariff

User = get_user_model()
LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
ON = dict(CACHES=LOCMEM, FREE_TIER_GUARD_ENABLED=True, FREE_TIER_MIN_MESSAGES=3,
          TOKEN_OVERAGE_USD_RUB=100.0, TOKEN_OVERAGE_MARKUP=1.6, PRICING_K_RETAIL=105)


def _network(cost_kopecks, model_name='claude-opus-5', **kw):
    cat, _ = Category.objects.get_or_create(name='T', defaults={'slug': 't'})
    d = dict(name=model_name, slug=model_name, model_name=model_name, category=cat,
             cost_per_message=1, cost_kopecks=cost_kopecks, provider='openrouter', is_active=True)
    d.update(kw)
    return NeuralNetwork.objects.create(**d)


def _trial(balance=1000, email='trial@t.ru'):
    u = User.objects.create_user(username=email, email=email, password='x')
    u.email_verified = True
    u.tariff = Tariff.get_default_tariff()
    u.set_kopecks(balance)
    u.save(update_fields=['tariff', 'email_verified'])
    return u


def _paying(balance=1000, email='paid@t.ru'):
    u = _trial(balance, email)
    PaymentHistory.objects.create(user=u, payment_type='pages', amount=100, status='success')
    return u


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@override_settings(**ON)
class CreateChatRuleSTests(TestCase):
    def test_trial_user_blocked_on_expensive_model(self):
        net = _network(709)  # грант 1000 / 3 = 333 < 709
        u = _trial()
        r = _client(u).post('/api/v1/chats/', {'network_slug': net.slug, 'message': 'hi'}, format='json')
        self.assertEqual(r.status_code, 402)
        self.assertEqual(r.json()['error']['code'], 'requires_paid_plan')
        self.assertEqual(Chat.objects.count(), 0)
        u.refresh_from_db()
        self.assertEqual(u.balance_kopecks, 1000)  # ничего не списано

    def test_trial_user_allowed_on_cheap_model(self):
        net = _network(8, model_name='deepseek-v4-flash')
        u = _trial()
        with mock.patch('api.views.chats.generate_ai_response'):
            r = _client(u).post('/api/v1/chats/', {'network_slug': net.slug, 'message': 'hi'}, format='json')
        self.assertEqual(r.status_code, 201)

    def test_paying_user_not_blocked_on_expensive_model(self):
        net = _network(709)
        u = _paying()
        with mock.patch('api.views.chats.generate_ai_response'):
            r = _client(u).post('/api/v1/chats/', {'network_slug': net.slug, 'message': 'hi'}, format='json')
        self.assertEqual(r.status_code, 201)

    def test_flag_off_never_blocks(self):
        net = _network(709)
        u = _trial()
        with self.settings(FREE_TIER_GUARD_ENABLED=False), \
                mock.patch('api.views.chats.generate_ai_response'):
            r = _client(u).post('/api/v1/chats/', {'network_slug': net.slug, 'message': 'hi'}, format='json')
        self.assertEqual(r.status_code, 201)


@override_settings(**ON)
class SendMessageRuleSTests(TestCase):
    def test_trial_user_blocked(self):
        net = _network(709)
        u = _trial()
        chat = Chat.objects.create(user=u, network=net, title='c')
        r = _client(u).post(f'/api/v1/chats/{chat.id}/messages/', {'message': 'hi'}, format='json')
        self.assertEqual(r.status_code, 402)
        self.assertEqual(r.json()['error']['code'], 'requires_paid_plan')


@override_settings(**ON)
class RegenerateRuleSTests(TestCase):
    def test_trial_user_blocked(self):
        net = _network(709)
        u = _trial()
        chat = Chat.objects.create(user=u, network=net, title='c')
        Message.objects.create(chat=chat, role='user', content='hi', status='completed')
        Message.objects.create(chat=chat, role='assistant', content='hey', status='completed')
        r = _client(u).post(f'/api/v1/chats/{chat.id}/regenerate/', {}, format='json')
        self.assertEqual(r.status_code, 402)
        self.assertEqual(r.json()['error']['code'], 'requires_paid_plan')


@override_settings(**ON)
class CompareRuleSTests(TestCase):
    def test_trial_user_blocked_when_any_selected_model_is_expensive(self):
        cheap = _network(8, model_name='deepseek-v4-flash')
        expensive = _network(709, model_name='claude-opus-5-b')
        u = _trial()
        r = _client(u).post('/api/v1/compare/', {
            'message': 'hi', 'network_slugs': [cheap.slug, expensive.slug],
        }, format='json')
        self.assertEqual(r.status_code, 402)
        self.assertEqual(Chat.objects.count(), 0)


@override_settings(**ON)
class StreamMessageViewFreeTierTests(TestCase):
    """Единственный путь, где апстрим вызывается ИНЛАЙН (не через Celery) - Rule D
    проверяется здесь напрямую, не только через generate_ai_response."""

    def _chat(self, user, net):
        return Chat.objects.create(user=user, network=net, title='c')

    def test_incident_replay_blocks_before_streaming_response(self):
        # cost_kopecks=284 (< грант/3=333) - проходит Rule S; блокировать должен именно
        # Rule D (динамический, по размеру промта), не статическая блокировка модели.
        net = _network(284, model_name='claude-sonnet-5')
        u = _trial()
        chat = self._chat(u, net)
        huge_text = 'lorem ipsum dolor sit amet ' * 8000
        with mock.patch('api.views.chats.get_client_for_network') as get_client:
            r = _client(u).post(f'/api/v1/chats/{chat.id}/messages/stream/',
                                {'message': huge_text}, format='json')
        self.assertEqual(r.status_code, 402)
        self.assertEqual(r.json()['error']['code'], 'trial_request_too_large')
        get_client.assert_not_called()
        u.refresh_from_db()
        self.assertEqual(u.balance_kopecks, 1000)  # списано и полностью возвращено
        self.assertEqual(Message.objects.filter(chat=chat).count(), 0)

    def test_small_prompt_streams_with_clamped_tokens(self):
        from types import SimpleNamespace

        net = _network(284, model_name='claude-sonnet-5')
        u = _trial()
        chat = self._chat(u, net)

        chunk = SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content='hi', tool_calls=None), finish_reason='stop')],
            usage=None,
        )
        fake_client = mock.MagicMock()
        fake_client.chat.completions.create.return_value = iter([chunk])  # НЕ context manager - код делает plain `for chunk in stream:`
        with mock.patch('api.views.chats.get_client_for_network', return_value=fake_client):
            r = _client(u).post(f'/api/v1/chats/{chat.id}/messages/stream/',
                                {'message': 'hi'}, format='json')
            self.assertEqual(r.status_code, 200)
            list(r.streaming_content)  # материализуем генератор (лениво вызывает get_client_for_network)

        sent_kwargs = fake_client.chat.completions.create.call_args.kwargs
        assistant = Message.objects.filter(chat=chat, role='assistant').first()
        self.assertIsNotNone(assistant)
        clamp = assistant.settings.get('balance_clamp')
        self.assertTrue(clamp)
        self.assertEqual(sent_kwargs['max_tokens'], clamp)  # ушло в апстрим ровно то, что заклэмплено
        # Итоговая (клэмпнутая) стоимость не превышает баланс пробного пользователя.
        from core.model_pricing import estimated_cost_kopecks
        est = estimated_cost_kopecks(net, 1, clamp)
        self.assertLessEqual(round(est * 1.6), 1000)


@override_settings(**dict(ON, TOKEN_OVERAGE_ENABLED=True, TOKEN_OVERAGE_DRY_RUN=False, TOKEN_METERING_ENABLED=True))
class StreamMessageViewPayingUserClampNoticeTests(TestCase):
    """2026-09-28: preflight_max_tokens для ПЛАТЯЩИХ на веб-SSE молчал так же тихо,
    как в Celery-пути (уже исправлено там). Проверяем ту же починку здесь."""

    def test_paying_user_clamp_is_recorded_and_surfaced_in_done_event(self):
        from types import SimpleNamespace

        net = _network(709, model_name='claude-opus-5')
        u = _paying(750)  # хватает на flat (709), остаток головы 41 коп.
        chat = Chat.objects.create(user=u, network=net, title='c')

        chunk = SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content='hi', tool_calls=None), finish_reason='stop')],
            usage=None,
        )
        fake_client = mock.MagicMock()
        fake_client.chat.completions.create.return_value = iter([chunk])
        with mock.patch('api.views.chats.get_client_for_network', return_value=fake_client):
            r = _client(u).post(f'/api/v1/chats/{chat.id}/messages/stream/',
                                {'message': 'hi'}, format='json')
            self.assertEqual(r.status_code, 200)
            body = b''.join(r.streaming_content).decode()

        assistant = Message.objects.filter(chat=chat, role='assistant').first()
        self.assertTrue(assistant.settings.get('balance_clamp'))
        self.assertIn('"balance_truncated": true', body)
