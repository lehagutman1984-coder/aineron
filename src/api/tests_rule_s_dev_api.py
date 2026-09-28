"""
ITEM 1 часть B, Rule S на dev-API (ревью, раунд 3): дорогая модель, заблокированная
для пробного пользователя на вебе/боте (core.model_pricing.is_model_blocked_for_trial),
раньше была полностью доступна тому же пользователю через /api/v1/chat/completions,
/api/v1/messages и batch — эндпоинты защищали только реальные деньги (атомарный
reserve_for_request), но не политику "не предлагать". Org-биллинг (api_key.organization)
исключён из Rule S — платит организация, не личный баланс пользователя.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from aitext.models import Category, NeuralNetwork
from api.models import APIKey, BatchJob, BatchJobItem
from teams.models import Organization
from users.models import PaymentHistory, Tariff

User = get_user_model()
LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
ON = dict(CACHES=LOCMEM, FREE_TIER_GUARD_ENABLED=True, FREE_TIER_MIN_MESSAGES=3)

BODY = {'model': 'claude-opus-5', 'messages': [{'role': 'user', 'content': 'hi'}]}


def _network(cost_kopecks=709, model_name='claude-opus-5', **kw):
    """709 > грант(1000)/3 = 333 -> заблокирована для пробного (см. tests_rule_s_trial_block.py)."""
    cat, _ = Category.objects.get_or_create(name='T', defaults={'slug': 't'})
    d = dict(name=model_name, slug=model_name, model_name=model_name, category=cat,
             cost_per_message=1, cost_kopecks=cost_kopecks, provider='openrouter', is_active=True)
    d.update(kw)
    return NeuralNetwork.objects.create(**d)


def _trial(balance=100000, email='trial@t.ru'):
    u = User.objects.create_user(username=email, email=email, password='x')
    u.email_verified = True
    u.tariff = Tariff.get_default_tariff()
    u.save(update_fields=['tariff', 'email_verified'])
    u.set_kopecks(balance)
    return u


def _paying(balance=100000, email='paid@t.ru'):
    u = _trial(balance, email)
    PaymentHistory.objects.create(user=u, payment_type='pages', amount=100, status='success')
    return u


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def _org_key_client(user, organization):
    """Клиент, аутентифицированный реальным API-ключом с organization - проходит
    через APIKeyAuthentication по-настоящему (в отличие от force_authenticate),
    чтобы request.api_key.organization был реально заполнен."""
    key, raw = APIKey.generate(user, 'org-key')
    key.organization = organization
    key.save(update_fields=['organization'])
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {raw}')
    return c


@override_settings(**ON)
class ChatCompletionsRuleSTests(TestCase):
    @mock.patch('api.views.chat.get_laozhang_client')
    def test_trial_user_blocked_on_expensive_model(self, get_client):
        _network()
        u = _trial()
        resp = _client(u).post('/api/v1/chat/completions', BODY, format='json')
        self.assertEqual(resp.status_code, 402)
        self.assertEqual(resp.json()['error']['code'], 'requires_paid_plan')
        get_client.return_value.chat.completions.create.assert_not_called()
        u.refresh_from_db()
        self.assertEqual(u.balance_kopecks, 100000)  # ничего не списано и не зарезервировано

    @mock.patch('api.views.chat.get_laozhang_client')
    def test_paying_user_not_blocked(self, get_client):
        from types import SimpleNamespace
        get_client.return_value.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='hi', tool_calls=None), finish_reason='stop')],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        )
        _network()
        u = _paying()
        resp = _client(u).post('/api/v1/chat/completions', BODY, format='json')
        self.assertEqual(resp.status_code, 200)

    @mock.patch('api.views.chat.get_laozhang_client')
    def test_org_billed_key_not_blocked(self, get_client):
        from types import SimpleNamespace
        get_client.return_value.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='hi', tool_calls=None), finish_reason='stop')],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        )
        _network()
        owner = _trial(balance=0, email='owner@t.ru')
        org = Organization.objects.create(name='Acme', owner=owner, balance_rub=1000)
        trial_member = _trial(balance=0, email='member@t.ru')  # пробный, но платит организация
        resp = _org_key_client(trial_member, org).post('/api/v1/chat/completions', BODY, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)


@override_settings(**ON)
class AnthropicRuleSTests(TestCase):
    @mock.patch('api.views.anthropic.get_laozhang_client')
    def test_trial_user_blocked_on_expensive_model(self, get_client):
        _network()
        u = _trial()
        resp = _client(u).post('/api/v1/messages', BODY, format='json')
        self.assertEqual(resp.status_code, 402)
        self.assertEqual(resp.json()['error']['type'], 'insufficient_permissions')
        get_client.return_value.chat.completions.create.assert_not_called()


@override_settings(**ON)
class BatchRuleSTests(TestCase):
    @mock.patch('aitext.tasks.get_laozhang_client')
    def test_blocked_item_fails_without_upstream_others_unaffected(self, get_client):
        from types import SimpleNamespace
        get_client.return_value.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='ok'), finish_reason='stop')],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        )
        expensive = _network(cost_kopecks=709, model_name='claude-opus-5')
        cheap = _network(cost_kopecks=8, model_name='deepseek-v4-flash')
        u = _trial()
        job = BatchJob.objects.create(user=u, endpoint='/v1/chat/completions', request_counts_total=2)
        BatchJobItem.objects.create(
            job=job, custom_id='blocked', method='POST', url='/v1/chat/completions',
            body={'model': expensive.model_name, 'messages': [{'role': 'user', 'content': 'hi'}]},
        )
        BatchJobItem.objects.create(
            job=job, custom_id='allowed', method='POST', url='/v1/chat/completions',
            body={'model': cheap.model_name, 'messages': [{'role': 'user', 'content': 'hi'}]},
        )

        from api.tasks import process_batch_job
        process_batch_job(job.pk)

        job.refresh_from_db()
        blocked_item = job.items.get(custom_id='blocked')
        allowed_item = job.items.get(custom_id='allowed')
        self.assertEqual(blocked_item.status, BatchJobItem.Status.FAILED)
        self.assertIn('requires_paid_plan', blocked_item.error_message)
        self.assertEqual(allowed_item.status, BatchJobItem.Status.COMPLETED)
        get_client.return_value.chat.completions.create.assert_called_once()  # только за allowed
