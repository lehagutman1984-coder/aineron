"""
ITEM 1, часть B — интеграция free_tier_guard в реальный путь генерации (Celery-путь
aitext.tasks.generate_ai_response). Инцидент 2026-09-27 воспроизведён буквально:
огромный промт на claude-opus-5 на пробном балансе 10 руб.
"""
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from aitext.billing import record_message_billing
from aitext.models import Category, Chat, Message, NeuralNetwork
from users.models import BalanceTransaction, PaymentHistory, Tariff

User = get_user_model()

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
ON = dict(CACHES=LOCMEM, FREE_TIER_GUARD_ENABLED=True, TOKEN_OVERAGE_USD_RUB=100.0, TOKEN_OVERAGE_MARKUP=1.6,
          PRICING_K_RETAIL=105, TOKEN_METERING_ENABLED=False, TOKEN_OVERAGE_ENABLED=False)


def _network(model_name, cost_kopecks, **kw):
    cat, _ = Category.objects.get_or_create(name='T', defaults={'slug': 't'})
    d = dict(name=model_name, slug=model_name, model_name=model_name, category=cat,
             cost_per_message=1, cost_kopecks=cost_kopecks, provider='openrouter', is_active=True)
    d.update(kw)
    return NeuralNetwork.objects.create(**d)


def _trial_user(balance, email='trial@t.ru'):
    u = User.objects.create_user(username=email, email=email, password='x')
    u.email_verified = True
    u.tariff = Tariff.get_default_tariff()
    u.set_kopecks(balance)
    u.save(update_fields=['tariff', 'email_verified'])
    return u


def _paying_user(balance, email='paid@t.ru'):
    u = _trial_user(balance, email)
    PaymentHistory.objects.create(user=u, payment_type='pages', amount=100, status='success')
    return u


def _pre_charged_chat(user, network, text, cost_kopecks):
    """Тот же паттерн, что api/views/chats.py: pre-charge ДО постановки в очередь,
    billing_reference/billing_kopecks записаны в settings ассистентского сообщения."""
    chat = Chat.objects.create(user=user, network=network, title='t')
    Message.objects.create(chat=chat, role='user', content=text, status='completed')
    assistant = Message.objects.create(chat=chat, role='assistant', content='', status='pending')
    assert user.spend_kopecks(cost_kopecks, type='spend', reference=f'chat:{assistant.id}')
    record_message_billing(assistant, f'chat:{assistant.id}', cost_kopecks)
    return chat, assistant


def _fake_completion(text='ok'):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=None), finish_reason='stop')],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


@override_settings(**ON)
class GenerateAiResponseFreeTierGuardTests(TestCase):
    def test_incident_replay_blocks_before_any_upstream_call(self):
        """opus-5, ~50к промт-токенов, баланс 10 руб. - ровно параметры реального инцидента."""
        from aitext.tasks import generate_ai_response
        net = _network('claude-opus-5', 709)
        u = _trial_user(1000)
        huge_text = 'lorem ipsum dolor sit amet ' * 8000  # ~224k ASCII символов ~ 56k токенов
        chat, assistant = _pre_charged_chat(u, net, huge_text, 709)

        fake_client = mock.MagicMock()
        with mock.patch('aitext.tasks.get_client_for_network', return_value=fake_client):
            generate_ai_response(assistant.id)

        fake_client.chat.completions.create.assert_not_called()
        assistant.refresh_from_db()
        u.refresh_from_db()
        self.assertEqual(assistant.status, Message.Status.FAILED)
        self.assertIn('стартового баланса', assistant.error_message)
        self.assertEqual(u.balance_kopecks, 1000)  # 709 списано и полностью возвращено

    def test_small_prompt_on_expensive_model_is_clamped_and_completes(self):
        from aitext.tasks import generate_ai_response
        net = _network('claude-opus-5', 709)
        u = _trial_user(1000)
        chat, assistant = _pre_charged_chat(u, net, 'привет, как дела?', 709)

        fake_client = mock.MagicMock()
        fake_client.chat.completions.create.return_value = _fake_completion('всё хорошо')
        with mock.patch('aitext.tasks.get_client_for_network', return_value=fake_client):
            generate_ai_response(assistant.id)

        fake_client.chat.completions.create.assert_called_once()
        sent_kwargs = fake_client.chat.completions.create.call_args.kwargs
        self.assertLess(sent_kwargs['max_tokens'], 4096)  # заведомо урезано
        assistant.refresh_from_db()
        self.assertEqual(assistant.status, Message.Status.COMPLETED)
        self.assertTrue(assistant.settings.get('balance_clamp'))

    def test_paying_user_is_never_guarded(self):
        from aitext.tasks import generate_ai_response
        net = _network('claude-opus-5', 709)
        u = _paying_user(1000)
        huge_text = 'lorem ipsum dolor sit amet ' * 8000
        chat, assistant = _pre_charged_chat(u, net, huge_text, 709)

        fake_client = mock.MagicMock()
        fake_client.chat.completions.create.return_value = _fake_completion('ok')
        with mock.patch('aitext.tasks.get_client_for_network', return_value=fake_client):
            generate_ai_response(assistant.id)

        fake_client.chat.completions.create.assert_called_once()  # НЕ заблокировано
        assistant.refresh_from_db()
        self.assertEqual(assistant.status, Message.Status.COMPLETED)

    def test_flag_off_never_blocks(self):
        from aitext.tasks import generate_ai_response
        net = _network('claude-opus-5', 709)
        u = _trial_user(1000)
        huge_text = 'lorem ipsum dolor sit amet ' * 8000
        chat, assistant = _pre_charged_chat(u, net, huge_text, 709)

        fake_client = mock.MagicMock()
        fake_client.chat.completions.create.return_value = _fake_completion('ok')
        with self.settings(FREE_TIER_GUARD_ENABLED=False, CACHES=LOCMEM), \
                mock.patch('aitext.tasks.get_client_for_network', return_value=fake_client):
            generate_ai_response(assistant.id)

        fake_client.chat.completions.create.assert_called_once()
        assistant.refresh_from_db()
        self.assertEqual(assistant.status, Message.Status.COMPLETED)

    def test_cheap_model_same_huge_prompt_not_blocked(self):
        from aitext.tasks import generate_ai_response
        net = _network('deepseek-v4-flash', 8)
        u = _trial_user(1000)
        huge_text = 'lorem ipsum dolor sit amet ' * 8000
        chat, assistant = _pre_charged_chat(u, net, huge_text, 8)

        fake_client = mock.MagicMock()
        fake_client.chat.completions.create.return_value = _fake_completion('ok')
        with mock.patch('aitext.tasks.get_client_for_network', return_value=fake_client):
            generate_ai_response(assistant.id)

        fake_client.chat.completions.create.assert_called_once()
        assistant.refresh_from_db()
        self.assertIn(assistant.status, (Message.Status.COMPLETED,))
