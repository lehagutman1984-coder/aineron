"""
Unit-тесты для FallbackClient (B13 — таймауты + фолбэк на стриме).

Реальные HTTP-запросы не делаются: `_get_raw_client` подменяется на фейковые
клиенты, воспроизводящие релевантное поведение openai SDK — включая
`Stream.__iter__`/`__next__`, читающие из одного закэшированного итератора
(см. openai/_streaming.py), чтобы тест на "peek первого чанка не теряет и не
дублирует данные" был честным, а не тестом против упрощённой заглушки.

Запуск: python manage.py test aitext.test_providers
"""
from unittest.mock import patch
from django.test import TestCase, override_settings

from aitext import providers


class _FakeAPIError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class _FakeStream:
    """Воспроизводит openai.Stream: __iter__/__next__ шарят один _iterator,
    close() закрывается один раз, поддерживает `with ... as s:`."""

    def __init__(self, chunks):
        self._raw_chunks = list(chunks)
        self._iterator = self.__stream__()
        self.closed = False

    def __stream__(self):
        for c in self._raw_chunks:
            if isinstance(c, Exception):
                raise c
            yield c

    def __next__(self):
        return self._iterator.__next__()

    def __iter__(self):
        for item in self._iterator:
            yield item

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self):
        self.closed = True


class _FakeCompletions:
    def __init__(self, behavior):
        # behavior: либо Exception (create() сразу падает), либо list чанков
        # (может содержать Exception внутри — упадёт при итерации), либо
        # callable(**kwargs) -> (Exception | list)
        self._behavior = behavior
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        behavior = self._behavior(**kwargs) if callable(self._behavior) else self._behavior
        if isinstance(behavior, Exception):
            raise behavior
        if kwargs.get('stream'):
            return _FakeStream(behavior)
        return behavior  # non-stream: просто возвращаем объект как есть


class _FakeImages:
    def __init__(self, behavior):
        self._behavior = behavior
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self._behavior, Exception):
            raise self._behavior
        return self._behavior

    def edit(self, **kwargs):
        return self.generate(**kwargs)


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeClient:
    def __init__(self, chat_behavior=None, image_behavior=None):
        self.chat = _FakeChat(_FakeCompletions(chat_behavior))
        self.images = _FakeImages(image_behavior)


def _patched_raw_clients(clients):
    """clients: {'laozhang': _FakeClient(...), 'apimart': _FakeClient(...)}"""
    def _get(provider):
        return clients[provider]
    return _get


@override_settings(AI_PROVIDER_FALLBACK=True, LAOZHANG_API_KEY='x', APIMART_API_KEY='y')
class NonStreamFallbackTests(TestCase):
    def test_primary_success_no_fallback(self):
        primary = _FakeClient(chat_behavior='ok-primary')
        secondary = _FakeClient(chat_behavior='ok-secondary')
        with patch.object(providers, '_get_raw_client', _patched_raw_clients(
            {'laozhang': primary, 'apimart': secondary})):
            client = providers.FallbackClient('laozhang')
            result = client.chat.completions.create(model='x', messages=[])
        self.assertEqual(result, 'ok-primary')
        self.assertEqual(len(secondary.chat.completions.calls), 0)

    def test_availability_error_falls_back(self):
        primary = _FakeClient(chat_behavior=_FakeAPIError('upstream down', status_code=500))
        secondary = _FakeClient(chat_behavior='ok-secondary')
        with patch.object(providers, '_get_raw_client', _patched_raw_clients(
            {'laozhang': primary, 'apimart': secondary})):
            client = providers.FallbackClient('laozhang')
            result = client.chat.completions.create(model='x', messages=[])
        self.assertEqual(result, 'ok-secondary')
        self.assertEqual(len(secondary.chat.completions.calls), 1)

    def test_content_error_does_not_fall_back(self):
        primary = _FakeClient(chat_behavior=_FakeAPIError('bad request: invalid role', status_code=400))
        secondary = _FakeClient(chat_behavior='ok-secondary')
        with patch.object(providers, '_get_raw_client', _patched_raw_clients(
            {'laozhang': primary, 'apimart': secondary})):
            client = providers.FallbackClient('laozhang')
            with self.assertRaises(_FakeAPIError):
                client.chat.completions.create(model='x', messages=[])
        self.assertEqual(len(secondary.chat.completions.calls), 0)

    def test_default_timeout_injected_when_not_specified(self):
        primary = _FakeClient(chat_behavior='ok')
        with patch.object(providers, '_get_raw_client', _patched_raw_clients(
            {'laozhang': primary, 'apimart': _FakeClient(chat_behavior='unused')})):
            client = providers.FallbackClient('laozhang')
            client.chat.completions.create(model='x', messages=[])
        self.assertEqual(primary.chat.completions.calls[0]['timeout'], providers._CHAT_TIMEOUT)

    def test_caller_timeout_is_not_overridden(self):
        primary = _FakeClient(chat_behavior='ok')
        with patch.object(providers, '_get_raw_client', _patched_raw_clients(
            {'laozhang': primary, 'apimart': _FakeClient(chat_behavior='unused')})):
            client = providers.FallbackClient('laozhang')
            client.chat.completions.create(model='x', messages=[], timeout=12.5)
        self.assertEqual(primary.chat.completions.calls[0]['timeout'], 12.5)


@override_settings(AI_PROVIDER_FALLBACK=True, LAOZHANG_API_KEY='x', APIMART_API_KEY='y')
class StreamFallbackTests(TestCase):
    def test_primary_streams_normally_no_fallback(self):
        primary = _FakeClient(chat_behavior=['a', 'b', 'c'])
        secondary = _FakeClient(chat_behavior=['x'])
        with patch.object(providers, '_get_raw_client', _patched_raw_clients(
            {'laozhang': primary, 'apimart': secondary})):
            client = providers.FallbackClient('laozhang')
            with client.chat.completions.create(model='x', messages=[], stream=True) as stream:
                chunks = list(stream)
        self.assertEqual(chunks, ['a', 'b', 'c'])
        self.assertEqual(len(secondary.chat.completions.calls), 0)

    def test_silent_hang_before_first_chunk_falls_back(self):
        """create() не падает (заголовки пришли), но первый next() ловит
        сетевую ошибку — недоступность, должны переключиться на apimart."""
        primary = _FakeClient(chat_behavior=[_FakeAPIError('read timed out')])
        secondary = _FakeClient(chat_behavior=['s1', 's2'])
        with patch.object(providers, '_get_raw_client', _patched_raw_clients(
            {'laozhang': primary, 'apimart': secondary})):
            client = providers.FallbackClient('laozhang')
            with client.chat.completions.create(model='x', messages=[], stream=True) as stream:
                chunks = list(stream)
        self.assertEqual(chunks, ['s1', 's2'])
        self.assertEqual(len(secondary.chat.completions.calls), 1)

    def test_mid_stream_error_after_first_chunk_does_not_fall_back(self):
        """Первый чанк уже дошёл (пользователь что-то увидел) — обрыв
        посередине НЕ должен молча переключать на второй провайдер и
        начинать заново; ошибка должна дойти до вызывающего кода как есть."""
        primary = _FakeClient(chat_behavior=['a', 'b', _FakeAPIError('connection reset')])
        secondary = _FakeClient(chat_behavior=['should-not-be-used'])
        with patch.object(providers, '_get_raw_client', _patched_raw_clients(
            {'laozhang': primary, 'apimart': secondary})):
            client = providers.FallbackClient('laozhang')
            got = []
            with self.assertRaises(_FakeAPIError):
                with client.chat.completions.create(model='x', messages=[], stream=True) as stream:
                    for chunk in stream:
                        got.append(chunk)
        self.assertEqual(got, ['a', 'b'])
        self.assertEqual(len(secondary.chat.completions.calls), 0)

    def test_empty_stream_supports_context_manager(self):
        primary = _FakeClient(chat_behavior=[])
        with patch.object(providers, '_get_raw_client', _patched_raw_clients(
            {'laozhang': primary, 'apimart': _FakeClient(chat_behavior=['unused'])})):
            client = providers.FallbackClient('laozhang')
            with client.chat.completions.create(model='x', messages=[], stream=True) as stream:
                chunks = list(stream)
        self.assertEqual(chunks, [])

    def test_stream_default_timeout_injected(self):
        primary = _FakeClient(chat_behavior=['a'])
        with patch.object(providers, '_get_raw_client', _patched_raw_clients(
            {'laozhang': primary, 'apimart': _FakeClient(chat_behavior=['unused'])})):
            client = providers.FallbackClient('laozhang')
            with client.chat.completions.create(model='x', messages=[], stream=True) as stream:
                list(stream)
        self.assertEqual(primary.chat.completions.calls[0]['timeout'], providers._CHAT_TIMEOUT)


@override_settings(AI_PROVIDER_FALLBACK=True, LAOZHANG_API_KEY='x', APIMART_API_KEY='y')
class ImageFallbackTests(TestCase):
    def test_default_image_timeout_injected(self):
        primary = _FakeClient(image_behavior='img-ok')
        with patch.object(providers, '_get_raw_client', _patched_raw_clients(
            {'laozhang': primary, 'apimart': _FakeClient(image_behavior='unused')})):
            client = providers.FallbackClient('laozhang')
            client.images.generate(prompt='x')
        self.assertEqual(primary.images.calls[0]['timeout'], providers._IMAGE_TIMEOUT)
        self.assertNotEqual(providers._IMAGE_TIMEOUT, providers._CHAT_TIMEOUT)

    def test_image_availability_error_falls_back(self):
        primary = _FakeClient(image_behavior=_FakeAPIError('gateway timeout', status_code=504))
        secondary = _FakeClient(image_behavior='img-secondary')
        with patch.object(providers, '_get_raw_client', _patched_raw_clients(
            {'laozhang': primary, 'apimart': secondary})):
            client = providers.FallbackClient('laozhang')
            result = client.images.generate(prompt='x')
        self.assertEqual(result, 'img-secondary')


@override_settings(AI_PROVIDER_FALLBACK=False, LAOZHANG_API_KEY='x', APIMART_API_KEY='y')
class FallbackDisabledTests(TestCase):
    def test_disabled_flag_never_tries_second_provider(self):
        primary = _FakeClient(chat_behavior=_FakeAPIError('down', status_code=500))
        secondary = _FakeClient(chat_behavior='ok-secondary')
        with patch.object(providers, '_get_raw_client', _patched_raw_clients(
            {'laozhang': primary, 'apimart': secondary})):
            client = providers.FallbackClient('laozhang')
            with self.assertRaises(_FakeAPIError):
                client.chat.completions.create(model='x', messages=[])
        self.assertEqual(len(secondary.chat.completions.calls), 0)
