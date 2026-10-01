"""
2026-10-01 (аудит безопасности, API_SECURITY_AUDIT_2026-10-01.md, пункт 4/15):
регрессионный тест — большой tools/response_format увеличивает резерв на
/v1/chat/completions пропорционально своему размеру, а не остаётся вне оценки.

Запуск: python manage.py test api.tests_chat_tools_reserve
"""
import json
from decimal import Decimal
from unittest import mock
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from aitext.models import Category, NeuralNetwork
from users.models import PaymentHistory

User = get_user_model()

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


def _paying_user(balance, email='toolsuser@t.ru'):
    """Пользователь с реальным платежом — не триггерит Rule S (is_model_blocked_for_trial)."""
    u = User.objects.create_user(username=email, email=email, password='x')
    u.email_verified = True
    u.save(update_fields=['email_verified'])
    u.set_kopecks(balance)
    PaymentHistory.objects.create(
        user=u, payment_type='pages', payment_method='test',
        invoice_id=f'test-{u.id}', amount='1.00', amount_kopecks=100,
        status='success',
    )
    return u


def _network():
    cat, _ = Category.objects.get_or_create(name='TestTools', defaults={'slug': 'testtools'})
    return NeuralNetwork.objects.create(
        name='Tools Test', slug='tools-test', model_name='tools-test', category=cat,
        cost_per_message=30, cost_kopecks=3000, provider='openrouter',
        kopecks_per_1k_tokens=Decimal('1000'), is_active=True,
    )


def _completion(prompt=10, completion=20):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='ok', tool_calls=None), finish_reason='stop')],
        usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion, total_tokens=prompt + completion),
    )


@override_settings(MIN_CHARGE_KOPECKS=10, CACHES=LOCMEM)
class ChatToolsReserveTests(TestCase):
    def setUp(self):
        self.network = _network()

    @mock.patch('api.views.chat.get_laozhang_client')
    def test_huge_tools_schema_is_reflected_in_reserve(self, get_client):
        """Маленький баланс + огромный tools-schema -> 402 ДО вызова апстрима,
        а не 200 с недоплатой после (до фикса: tools не входил в оценку резерва,
        апстриму уходил как есть, недоплата прощалась при неудаче _debit(extra))."""
        user = _paying_user(300)  # хватает на обычное маленькое сообщение, не на 100k токенов
        huge_tools = [{
            'type': 'function',
            'function': {
                'name': 'f',
                'description': 'x' * 400_000,  # ~100k+ токенов по грубой оценке
                'parameters': {'type': 'object', 'properties': {}},
            },
        }]
        resp = APIClient_with_user(user).post('/api/v1/chat/completions', {
            'model': 'tools-test',
            'messages': [{'role': 'user', 'content': 'hi'}],
            'tools': huge_tools,
            'max_tokens': 50,
        }, format='json')
        self.assertEqual(resp.status_code, 402)
        get_client.return_value.chat.completions.create.assert_not_called()
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 300)  # ничего не списано

    @mock.patch('api.views.chat.get_laozhang_client')
    def test_small_tools_with_enough_balance_still_works(self, get_client):
        get_client.return_value.chat.completions.create.return_value = _completion()
        user = _paying_user(100000)
        small_tools = [{'type': 'function', 'function': {'name': 'f', 'description': 'short', 'parameters': {}}}]
        resp = APIClient_with_user(user).post('/api/v1/chat/completions', {
            'model': 'tools-test',
            'messages': [{'role': 'user', 'content': 'hi'}],
            'tools': small_tools,
            'max_tokens': 50,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        # tools реально прокинут апстриму
        call_kwargs = get_client.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs.get('tools'), small_tools)


def APIClient_with_user(user):
    c = APIClient()
    c.force_authenticate(user)
    return c
