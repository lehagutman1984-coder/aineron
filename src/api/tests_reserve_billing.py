"""
Тесты схемы «резерв -> генерация -> расчёт» для API-эндпоинтов.

Инцидент 2026-09-25: пользователь с балансом 5,56 ₽ получал ответы Opus/Fable
на 50-800 ₽ — эндпоинты проверяли только `balance <= 0`, списывали после
генерации, а ошибку списания глотали. Здесь фиксируется контракт: без баланса
апстрим НЕ вызывается, а неиспользованная часть резерва возвращается.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from aitext.models import Category, NeuralNetwork
from api.exceptions import InsufficientStarsError
from api.models import TokenUsage
from api.services.billing import (
    release_reservation,
    reserve_for_request,
    settle_reservation,
)
from users.models import BalanceTransaction

User = get_user_model()

# Троттлинг DRF ходит в кэш; в тестах Redis нет.
LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


def _network(rate='1000', **kw):
    cat, _ = Category.objects.get_or_create(name='Test', defaults={'slug': 'test'})
    d = dict(
        name='Opus Test', slug='opus-test', model_name='opus-test', category=cat,
        cost_per_message=30, cost_kopecks=3000, provider='openrouter',
        kopecks_per_1k_tokens=Decimal(rate), is_active=True,
    )
    d.update(kw)
    return NeuralNetwork.objects.create(**d)


def _user(balance, email='u@t.ru'):
    u = User.objects.create_user(username=email, email=email, password='x')
    u.email_verified = True
    u.save(update_fields=['email_verified'])
    u.set_kopecks(balance)
    return u


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def _completion(text='hello', prompt=10, completion=20):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=None), finish_reason='stop')],
        usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion, total_tokens=prompt + completion),
    )


def _chunk(text, usage=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text, tool_calls=None), finish_reason=None)],
        usage=usage,
    )


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __enter__(self):
        return iter(self._chunks)

    def __exit__(self, *a):
        return False


BODY = {'model': 'opus-test', 'messages': [{'role': 'user', 'content': 'hi'}]}


@override_settings(MIN_CHARGE_KOPECKS=10, CACHES=LOCMEM)
class ReserveServiceTests(TestCase):
    def setUp(self):
        self.user = _user(100000)
        self.network = _network()

    def test_reserve_then_settle_refunds_difference(self):
        res = reserve_for_request(self.user, None, self.network, 100, 1000)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 100000 - res.reserved_kopecks)
        charged = settle_reservation(res, {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150})
        self.user.refresh_from_db()
        self.assertEqual(charged, 150)  # 1000 коп/1k * 150 токенов
        self.assertEqual(self.user.balance_kopecks, 100000 - 150)
        self.assertEqual(TokenUsage.objects.get(user=self.user).cost_kopecks, 150)
        self.assertTrue(BalanceTransaction.objects.filter(
            user=self.user, type='refund', reference=f'api:{res.request_id}').exists())

    def test_settle_without_usage_fails_closed(self):
        res = reserve_for_request(self.user, None, self.network, 100, 1000)
        charged = settle_reservation(res, {}, fallback_completion_tokens=200)
        self.assertEqual(charged, 300)  # 100 prompt + 200 оценка ответа, а не 0
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 100000 - 300)

    def test_release_returns_everything(self):
        res = reserve_for_request(self.user, None, self.network, 100, 1000)
        release_reservation(res)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 100000)

    def test_max_tokens_narrowed_to_balance(self):
        self.user.set_kopecks(556)
        res = reserve_for_request(self.user, None, self.network, 10, 4000)
        self.assertLess(res.max_tokens, 4000)
        self.assertGreaterEqual(res.max_tokens, 256)
        self.user.refresh_from_db()
        self.assertGreaterEqual(self.user.balance_kopecks, 0)  # резерв не ушёл в минус

    def test_insufficient_for_minimum_raises(self):
        self.user.set_kopecks(50)
        with self.assertRaises(InsufficientStarsError) as cm:
            reserve_for_request(self.user, None, self.network, 10, 4000)
        self.assertTrue(hasattr(cm.exception, 'required_kopecks'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 50)  # ничего не списано

    def test_overrun_beyond_reserve_charges_what_is_available(self):
        self.user.set_kopecks(300)
        res = reserve_for_request(self.user, None, self.network, 10, 100)
        # фактически апстрим вернул сильно больше, чем резерв, а баланса нет
        self.user.set_kopecks(0)
        charged = settle_reservation(res, {'prompt_tokens': 10, 'completion_tokens': 90, 'total_tokens': 5000})
        self.assertEqual(charged, res.reserved_kopecks)  # не падает, логирует


@override_settings(MIN_CHARGE_KOPECKS=10, CACHES=LOCMEM)
class ChatCompletionsBillingTests(TestCase):
    URL = '/api/v1/chat/completions'

    def setUp(self):
        self.network = _network()

    @mock.patch('api.views.chat.get_laozhang_client')
    def test_no_balance_no_upstream_call(self, get_client):
        """Ровно инцидент: 5,56 ₽ на балансе, дорогая модель, stream=true."""
        user = _user(50)
        resp = _client(user).post(self.URL, {**BODY, 'stream': True, 'max_tokens': 4000}, format='json')
        self.assertEqual(resp.status_code, 402)
        err = resp.json()['error']
        self.assertEqual(err['code'], 'insufficient_quota')
        self.assertIn('top_up_url', err)
        get_client.return_value.chat.completions.create.assert_not_called()
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 50)

    @mock.patch('api.views.chat.get_laozhang_client')
    def test_non_stream_no_balance_no_upstream_call(self, get_client):
        user = _user(50, 'b@t.ru')
        resp = _client(user).post(self.URL, {**BODY, 'max_tokens': 4000}, format='json')
        self.assertEqual(resp.status_code, 402)
        get_client.return_value.chat.completions.create.assert_not_called()

    @mock.patch('api.views.chat.get_laozhang_client')
    def test_non_stream_settles_and_refunds_unused(self, get_client):
        get_client.return_value.chat.completions.create.return_value = _completion(prompt=10, completion=20)
        user = _user(100000, 'c@t.ru')
        resp = _client(user).post(self.URL, {**BODY, 'max_tokens': 500}, format='json')
        self.assertEqual(resp.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 100000 - 30)  # 30 токенов * 1 коп
        self.assertEqual(TokenUsage.objects.filter(user=user).count(), 1)

    @mock.patch('api.views.chat.get_laozhang_client')
    def test_max_tokens_is_clamped_to_affordable(self, get_client):
        get_client.return_value.chat.completions.create.return_value = _completion()
        user = _user(556, 'd@t.ru')
        resp = _client(user).post(self.URL, {**BODY, 'max_tokens': 4000}, format='json')
        self.assertEqual(resp.status_code, 200)
        sent = get_client.return_value.chat.completions.create.call_args.kwargs
        self.assertLess(sent['max_tokens'], 4000)
        self.assertEqual(resp['X-Aineron-Low-Balance'], '1')

    @mock.patch('api.views.chat.get_laozhang_client')
    def test_upstream_error_releases_reserve(self, get_client):
        get_client.return_value.chat.completions.create.side_effect = RuntimeError('boom')
        user = _user(100000, 'e@t.ru')
        resp = _client(user).post(self.URL, {**BODY, 'max_tokens': 500}, format='json')
        self.assertEqual(resp.status_code, 502)
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 100000)

    @mock.patch('api.views.chat.get_laozhang_client')
    def test_stream_without_usage_does_not_become_free(self, get_client):
        """Апстрим не вернул usage (напр. резервный провайдер) - fail-closed."""
        get_client.return_value.chat.completions.create.return_value = _FakeStream(
            [_chunk('word ' * 200), _chunk('more ' * 200)]
        )
        user = _user(100000, 'f@t.ru')
        resp = _client(user).post(self.URL, {**BODY, 'stream': True, 'max_tokens': 2000}, format='json')
        self.assertEqual(resp.status_code, 200)
        body = b''.join(resp.streaming_content).decode()
        self.assertIn('[DONE]', body)
        user.refresh_from_db()
        self.assertLess(user.balance_kopecks, 100000)  # списано по оценке, не 0
        self.assertEqual(TokenUsage.objects.filter(user=user).count(), 1)

    @mock.patch('api.views.chat.get_laozhang_client')
    def test_stream_with_usage_charges_actual(self, get_client):
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        get_client.return_value.chat.completions.create.return_value = _FakeStream(
            [_chunk('hi'), SimpleNamespace(choices=[], usage=usage)]
        )
        user = _user(100000, 'g@t.ru')
        resp = _client(user).post(self.URL, {**BODY, 'stream': True, 'max_tokens': 2000}, format='json')
        b''.join(resp.streaming_content)
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 100000 - 30)
        sent = get_client.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(sent['stream_options'], {'include_usage': True})

    @mock.patch('api.views.chat.get_laozhang_client')
    def test_stream_error_before_output_releases_reserve(self, get_client):
        get_client.return_value.chat.completions.create.side_effect = RuntimeError('boom')
        user = _user(100000, 'h@t.ru')
        resp = _client(user).post(self.URL, {**BODY, 'stream': True, 'max_tokens': 500}, format='json')
        b''.join(resp.streaming_content)
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 100000)


@override_settings(MIN_CHARGE_KOPECKS=10, CACHES=LOCMEM)
class AnthropicBillingTests(TestCase):
    @mock.patch('api.views.anthropic.get_laozhang_client')
    def test_no_balance_no_upstream_call(self, get_client):
        _network()
        user = _user(50)
        resp = _client(user).post(
            '/api/v1/messages',
            {'model': 'opus-test', 'max_tokens': 4000, 'messages': [{'role': 'user', 'content': 'hi'}]},
            format='json',
        )
        self.assertEqual(resp.status_code, 402)
        get_client.return_value.chat.completions.create.assert_not_called()

    @mock.patch('api.views.anthropic.get_laozhang_client')
    def test_charges_actual_usage(self, get_client):
        _network()
        get_client.return_value.chat.completions.create.return_value = _completion(prompt=10, completion=20)
        user = _user(100000)
        resp = _client(user).post(
            '/api/v1/messages',
            {'model': 'opus-test', 'max_tokens': 500, 'messages': [{'role': 'user', 'content': 'hi'}]},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 100000 - 30)


@override_settings(MIN_CHARGE_KOPECKS=10, CACHES=LOCMEM)
class EmbeddingsBillingTests(TestCase):
    URL = '/api/v1/embeddings'

    @mock.patch('api.views.embeddings.get_embedding_client')
    def test_unknown_paid_model_rejected_without_upstream(self, get_client):
        user = _user(100000)
        resp = _client(user).post(self.URL, {'model': 'some-expensive-model', 'input': 'x'}, format='json')
        self.assertEqual(resp.status_code, 400)
        get_client.return_value.embeddings.create.assert_not_called()

    @mock.patch('api.views.embeddings.get_embedding_client')
    def test_no_balance_no_upstream_call(self, get_client):
        user = _user(0)
        resp = _client(user).post(self.URL, {'model': 'text-embedding-3-small', 'input': 'x'}, format='json')
        self.assertEqual(resp.status_code, 402)
        get_client.return_value.embeddings.create.assert_not_called()

    @mock.patch('api.views.embeddings.get_embedding_client')
    def test_paid_embedding_is_billed(self, get_client):
        """Раньше (network is None) эмбеддинги были бесплатными для любой модели."""
        get_client.return_value.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2])],
            usage=SimpleNamespace(total_tokens=50),
        )
        user = _user(100000)
        resp = _client(user).post(self.URL, {'model': 'text-embedding-3-small', 'input': 'hello'}, format='json')
        self.assertEqual(resp.status_code, 200)
        user.refresh_from_db()
        self.assertLess(user.balance_kopecks, 100000)
        self.assertEqual(TokenUsage.objects.filter(user=user).count(), 1)


@override_settings(MIN_CHARGE_KOPECKS=10, CACHES=LOCMEM)
class AudioBillingTests(TestCase):
    def test_tts_no_balance_no_upstream_call(self):
        user = _user(0)
        with mock.patch('api.views.audio.get_utility_client') as get_client:
            resp = _client(user).post('/api/v1/audio/speech', {'input': 'hello'}, format='json')
        self.assertEqual(resp.status_code, 402)
        get_client.return_value.audio.speech.create.assert_not_called()

    def test_tts_upstream_error_refunds(self):
        user = _user(1000)
        with mock.patch('api.views.audio.get_utility_client') as get_client:
            get_client.return_value.audio.speech.create.side_effect = RuntimeError('boom')
            resp = _client(user).post('/api/v1/audio/speech', {'input': 'hello'}, format='json')
        self.assertEqual(resp.status_code, 502)
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 1000)

    def test_tts_success_charges_once(self):
        user = _user(1000)
        with mock.patch('api.views.audio.get_utility_client') as get_client:
            get_client.return_value.audio.speech.create.return_value = SimpleNamespace(content=b'abc')
            resp = _client(user).post('/api/v1/audio/speech', {'input': 'hello'}, format='json')
        self.assertEqual(resp.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 900)


@override_settings(MIN_CHARGE_KOPECKS=10, CACHES=LOCMEM)
class BatchBillingTests(TestCase):
    def _job(self, user, model):
        from api.models import BatchJob, BatchJobItem
        job = BatchJob.objects.create(user=user, endpoint='/v1/chat/completions', request_counts_total=1)
        item = BatchJobItem.objects.create(
            job=job, custom_id='1', method='POST', url='/v1/chat/completions',
            body={'model': model, 'messages': [{'role': 'user', 'content': 'hi'}], 'max_tokens': 300},
        )
        return job, item

    @mock.patch('aitext.tasks.get_laozhang_client')
    def test_unknown_model_is_not_generated_for_free(self, get_client):
        from api.tasks import process_batch_job
        user = _user(100000)
        job, item = self._job(user, 'gpt-4o-mini-not-in-catalog')
        process_batch_job(job.pk)
        item.refresh_from_db()
        self.assertEqual(item.status, 'failed')
        get_client.return_value.chat.completions.create.assert_not_called()

    @mock.patch('aitext.tasks.get_laozhang_client')
    def test_no_balance_item_fails_without_upstream_call(self, get_client):
        from api.tasks import process_batch_job
        _network()
        user = _user(20)
        job, item = self._job(user, 'opus-test')
        process_batch_job(job.pk)
        item.refresh_from_db()
        self.assertEqual(item.status, 'failed')
        self.assertIn('insufficient_quota', item.error_message)
        get_client.return_value.chat.completions.create.assert_not_called()

    @mock.patch('aitext.tasks.get_laozhang_client')
    def test_batch_item_billed(self, get_client):
        from api.tasks import process_batch_job
        _network()
        get_client.return_value.chat.completions.create.return_value = _completion(prompt=10, completion=20)
        user = _user(100000)
        job, item = self._job(user, 'opus-test')
        process_batch_job(job.pk)
        item.refresh_from_db()
        self.assertEqual(item.status, 'completed')
        user.refresh_from_db()
        self.assertEqual(user.balance_kopecks, 100000 - 30)


@override_settings(MIN_CHARGE_KOPECKS=10, CACHES=LOCMEM)
class ParameterAbuseTests(TestCase):
    """n <= 0 / n > лимита не должны давать нулевую цену или необеспеченный расход."""

    @mock.patch('api.views.chat.get_laozhang_client')
    def test_chat_n_out_of_range_rejected(self, get_client):
        _network()
        user = _user(100000)
        resp = _client(user).post('/api/v1/chat/completions', {**BODY, 'n': 50}, format='json')
        self.assertEqual(resp.status_code, 400)
        get_client.return_value.chat.completions.create.assert_not_called()

    @mock.patch('api.views.chat.get_laozhang_client')
    def test_chat_n_reserves_for_all_choices(self, get_client):
        _network()
        get_client.return_value.chat.completions.create.return_value = _completion(prompt=10, completion=20)
        user = _user(556)
        resp = _client(user).post('/api/v1/chat/completions', {**BODY, 'n': 2, 'max_tokens': 4000}, format='json')
        self.assertEqual(resp.status_code, 200)
        sent = get_client.return_value.chat.completions.create.call_args.kwargs
        # 546 токенов на двоих => не больше ~273 на вариант, а не 546 на каждый
        self.assertLessEqual(sent['max_tokens'] * 2, 556)

    def test_images_n_zero_rejected(self):
        user = _user(100000)
        resp = _client(user).post('/api/v1/images/generations', {'prompt': 'cat', 'n': 0}, format='json')
        self.assertEqual(resp.status_code, 400)
