"""
2026-10-01 (аудит безопасности, API_SECURITY_AUDIT_2026-10-01.md, пункт 7/18):
регрессионные тесты на совместимость /v1/messages с реальным Anthropic SDK —
x-api-key заголовок, честные ошибки на stream/tools вместо тихого дропа,
защита от 500 на не-dict content-блоке, конвертация image-блоков, stop_reason.

Запуск: python manage.py test api.tests_anthropic_compat
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase
from rest_framework import status

from aitext.models import Category, NeuralNetwork
from api.models import APIKey
from api.views.anthropic import _anthropic_to_openai_messages, _anthropic_system_to_text
from users.models import PaymentHistory

User = get_user_model()

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


def _paying_user(email='anthropic@test.ru'):
    u = User.objects.create_user(username=email, email=email, password='x')
    u.email_verified = True
    u.save(update_fields=['email_verified'])
    u.set_kopecks(100000)
    PaymentHistory.objects.create(
        user=u, payment_type='pages', payment_method='test',
        invoice_id=f'test-{u.id}', amount='1.00', amount_kopecks=100, status='success',
    )
    return u


def _network():
    cat, _ = Category.objects.get_or_create(name='TestAnthropic', defaults={'slug': 'testanthropic'})
    return NeuralNetwork.objects.create(
        name='Claude Test', slug='claude-test', model_name='claude-test', category=cat,
        cost_per_message=30, cost_kopecks=3000, provider='openrouter',
        kopecks_per_1k_tokens=Decimal('1000'), is_active=True,
    )


class MessageConversionTests(APITestCase):
    """Юнит-тесты конвертера — без HTTP, без БД."""

    def test_system_as_string_passthrough(self):
        self.assertEqual(_anthropic_system_to_text('be nice'), 'be nice')

    def test_system_as_block_list_extracts_text(self):
        system = [{'type': 'text', 'text': 'be nice'}, {'type': 'text', 'text': 'and short'}]
        self.assertEqual(_anthropic_system_to_text(system), 'be nice\nand short')

    def test_non_dict_content_block_does_not_crash(self):
        messages = [{'role': 'user', 'content': ['just a string, not a dict', {'type': 'text', 'text': 'hi'}]}]
        result = _anthropic_to_openai_messages(messages)
        # не упало — главное; текстовый блок дошёл
        self.assertEqual(result[0]['content'], [{'type': 'text', 'text': 'hi'}])

    def test_image_block_converted_to_openai_image_url(self):
        messages = [{'role': 'user', 'content': [
            {'type': 'text', 'text': 'what is this?'},
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': 'AAAA'}},
        ]}]
        result = _anthropic_to_openai_messages(messages)
        parts = result[0]['content']
        self.assertEqual(parts[0], {'type': 'text', 'text': 'what is this?'})
        self.assertEqual(parts[1]['type'], 'image_url')
        self.assertEqual(parts[1]['image_url']['url'], 'data:image/png;base64,AAAA')


@override_settings(MIN_CHARGE_KOPECKS=10, CACHES=LOCMEM)
class AnthropicEndpointTests(APITestCase):
    def setUp(self):
        self.network = _network()
        self.user = _paying_user()

    def test_x_api_key_header_authenticates(self):
        key_obj, raw = APIKey.generate(self.user, 'sdk-key')
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=raw)
        with mock.patch('api.views.anthropic.get_laozhang_client') as get_client:
            get_client.return_value.chat.completions.create.return_value = SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='hi'), finish_reason='stop')],
                usage=SimpleNamespace(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            )
            resp = client.post('/api/v1/messages', {
                'model': 'claude-test', 'max_tokens': 100,
                'messages': [{'role': 'user', 'content': 'hi'}],
            }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_stream_true_returns_honest_error_not_silent_ignore(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post('/api/v1/messages', {
            'model': 'claude-test', 'max_tokens': 100, 'stream': True,
            'messages': [{'role': 'user', 'content': 'hi'}],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tools_returns_honest_error_not_silent_ignore(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post('/api/v1/messages', {
            'model': 'claude-test', 'max_tokens': 100,
            'tools': [{'name': 'f', 'description': 'x', 'input_schema': {}}],
            'messages': [{'role': 'user', 'content': 'hi'}],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 100000)  # ничего не списано

    def test_stop_reason_reflects_length_truncation(self):
        self.client.force_authenticate(user=self.user)
        with mock.patch('api.views.anthropic.get_laozhang_client') as get_client:
            get_client.return_value.chat.completions.create.return_value = SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='cut off'), finish_reason='length')],
                usage=SimpleNamespace(prompt_tokens=5, completion_tokens=100, total_tokens=105),
            )
            resp = self.client.post('/api/v1/messages', {
                'model': 'claude-test', 'max_tokens': 100,
                'messages': [{'role': 'user', 'content': 'hi'}],
            }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['stop_reason'], 'max_tokens')
