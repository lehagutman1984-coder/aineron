"""
Провайдер-слой с прозрачным автоматическим фолбэком между AI-сервисами.

Оба сервиса — OpenAI-совместимые прокси:
  - laozhang.ai  — основной для текста и изображений
  - apimart.ai   — основной для видео; резерв для текста и изображений

Идея: если основной сервис недоступен (сеть/таймаут/5xx/429) или конкретная
модель на нём недоступна (404 / model not found / доступ), автоматически
пробуем резервный сервис с тем же именем модели. Ошибки, вызванные
пользовательским контентом (400 bad request, content policy), НЕ являются
поводом для фолбэка — их пробрасываем как есть.

Ключевая точка интеграции: фабрики клиентов `get_laozhang_client()` и
`get_laozhang_image_client()` возвращают `FallbackClient`, поэтому ВСЕ
существующие вызовы `client.chat.completions.create(...)` и
`client.images.generate(...)` получают фолбэк без изменения кода вызова.
Остальные неймспейсы (audio, embeddings, models) прозрачно делегируются
основному клиенту без фолбэка.

Таймауты (B13, 2026-07-24): без явного timeout openai-python использует
дефолт SDK — 600 сек тишины на попытку, из-за чего "молча зависший" (принял
соединение, но не отвечает) провайдер держал бы пользователя/воркер
несколько минут, прежде чем вообще дойти до фолбэка. Ниже — два разных по
смыслу таймаута:

  - _CHAT_TIMEOUT (read=90с) — для чата: и обычного (non-stream), и как
    ограничение "тишины между двумя чанками" для стрима. Не ограничивает
    ОБЩУЮ длительность ответа — httpx.Timeout.read это тишина между байтами,
    не потолок на весь запрос, так что модель может отвечать сколь угодно
    долго, если она реально что-то передаёт.
  - _IMAGE_TIMEOUT (read=240с) — для генерации изображений: там нет
    промежуточных байтов вообще (провайдер молчит весь цикл генерации, потом
    отдаёт готовый результат целиком), поэтому окно заметно шире, чтобы не
    обрывать реально идущую (просто небыструю) генерацию как "недоступность".

Стриминг-фолбэк (_run_stream): считаем провайдера успешным только после
того, как реально получен первый чанк тела ответа — "отдал заголовки,
но дальше молчит" тоже ловим как недоступность и переключаемся. А вот
ПОСЛЕ первого чанка на этот же запрос уже НЕ переключаемся: пользователь
уже что-то видит, тихо начинать заново на другом сервисе означало бы
задвоенный/оборванный текст. Это тот же принцип, что и для изображений —
не переключать провайдера в процессе уже начавшейся генерации, только до
её начала.
"""
import logging
import httpx
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

_CHAT_TIMEOUT = httpx.Timeout(connect=10.0, read=90.0, write=15.0, pool=10.0)
_IMAGE_TIMEOUT = httpx.Timeout(connect=10.0, read=240.0, write=15.0, pool=10.0)

# (name, base_url_setting, key_setting)
_PROVIDER_META = {
    'laozhang': ('LAOZHANG_API_URL', 'LAOZHANG_API_KEY'),
    'apimart': ('APIMART_API_URL', 'APIMART_API_KEY'),
}

_raw_clients = {}
_groq_client = None
_openrouter_free_client = None
_zai_client = None
_cloudflare_client = None


def get_groq_client():
    """
    «Сырой» OpenAI-совместимый клиент Groq (console.groq.com) для бесплатных
    текстовых моделей.

    ВНИМАНИЕ: Groq блокирует запросы из РФ на уровне сети (403 Forbidden ещё
    до проверки ключа). Рабочий вариант только через прокси/VPS вне РФ.
    Без фолбэка — Groq единственный источник этих моделей.
    """
    global _groq_client
    if _groq_client is None:
        _groq_client = OpenAI(
            base_url=getattr(settings, 'GROQ_API_URL', 'https://api.groq.com/openai/v1'),
            api_key=getattr(settings, 'GROQ_API_KEY', ''),
        )
    return _groq_client


def get_openrouter_free_client():
    """
    «Сырой» OpenAI-совместимый клиент OpenRouter (openrouter.ai) для бесплатных
    моделей (`:free`). Доступен из РФ без прокси. Без фолбэка.
    """
    global _openrouter_free_client
    if _openrouter_free_client is None:
        _openrouter_free_client = OpenAI(
            base_url=getattr(settings, 'OPENROUTER_API_URL', 'https://openrouter.ai/api/v1'),
            api_key=getattr(settings, 'OPENROUTER_API_KEY', ''),
        )
    return _openrouter_free_client


def get_zai_client():
    """
    «Сырой» OpenAI-совместимый клиент Z.ai (Zhipu AI, Китай) для бесплатных
    моделей GLM-*-Flash. Китайский провайдер — доступен из РФ без прокси
    (в отличие от Groq). Без фолбэка.
    """
    global _zai_client
    if _zai_client is None:
        _zai_client = OpenAI(
            base_url=getattr(settings, 'ZAI_API_URL', 'https://api.z.ai/api/paas/v4'),
            api_key=getattr(settings, 'ZAI_API_KEY', ''),
        )
    return _zai_client


def get_cloudflare_client():
    """
    «Сырой» OpenAI-совместимый клиент Cloudflare Workers AI для бесплатных
    моделей (10 000 «нейронов»/день на аккаунт, общий пул). Доступность из РФ
    подтверждена вручную (curl с боевого окружения, 2026-07-04). Без фолбэка.
    """
    global _cloudflare_client
    if _cloudflare_client is None:
        _cloudflare_client = OpenAI(
            base_url=getattr(settings, 'CLOUDFLARE_API_URL', ''),
            api_key=getattr(settings, 'CLOUDFLARE_API_TOKEN', ''),
        )
    return _cloudflare_client


def _get_raw_client(provider):
    """Кэшированный «сырой» OpenAI-клиент конкретного сервиса."""
    if provider not in _raw_clients:
        url_key, key_key = _PROVIDER_META[provider]
        base_url = getattr(settings, url_key, '')
        api_key = getattr(settings, key_key, '')
        _raw_clients[provider] = OpenAI(base_url=base_url, api_key=api_key)
    return _raw_clients[provider]


def _fallback_enabled():
    return getattr(settings, 'AI_PROVIDER_FALLBACK', True)


def _provider_available(provider):
    _, key_key = _PROVIDER_META[provider]
    return bool(getattr(settings, key_key, ''))


def is_availability_error(exc) -> bool:
    """
    True, если ошибка означает недоступность сервиса/модели (стоит попробовать
    другой сервис), а не проблему в пользовательском запросе (контент/параметры).
    """
    # Явные транспортные ошибки openai SDK — всегда availability.
    try:
        from openai import APIConnectionError, APITimeoutError
        if isinstance(exc, (APIConnectionError, APITimeoutError)):
            return True
    except Exception:
        pass

    status = getattr(exc, 'status_code', None)
    if status is None:
        status = getattr(getattr(exc, 'response', None), 'status_code', None)

    if status is not None:
        # 5xx, rate limit, «не найдено», проблемы доступа/ключа на этом сервисе.
        if status >= 500 or status in (429, 404, 401, 403, 408, 409):
            return True
        if status == 400:
            # 400 обычно про контент/параметры — но некоторые прокси так отдают
            # «модель не найдена/не поддерживается».
            msg = str(exc).lower()
            markers = ('not found', 'not exist', "doesn't exist", 'does not exist',
                       'unavailable', 'not support', 'no such model', 'unknown model',
                       'no available', 'no channel')
            if 'model' in msg and any(m in msg for m in markers):
                return True
            return False
        # Прочие 4xx (422 и т.п.) — считаем проблемой запроса.
        return False

    # Статус неизвестен — ориентируемся по тексту (сетевые/шлюзовые сбои).
    msg = str(exc).lower()
    net_markers = ('timeout', 'timed out', 'connection', 'connect', 'unavailable',
                   'bad gateway', 'gateway', 'temporarily', 'reset by peer',
                   'no available', 'no channel', 'overloaded', 'try again')
    return any(m in msg for m in net_markers)


def _order_for(primary):
    """Список сервисов в порядке приоритета для данного основного сервиса."""
    if primary == 'laozhang':
        chain = ['laozhang', 'apimart']
    elif primary == 'apimart':
        chain = ['apimart', 'laozhang']
    else:
        chain = [primary]
    if not _fallback_enabled():
        chain = chain[:1]
    # Оставляем только сервисы с настроенным ключом.
    chain = [p for p in chain if _provider_available(p)]
    if not chain:
        chain = [primary]
    return chain


class _PeekedStream:
    """
    Обёртка над openai `Stream`: первый чанк уже получен и провалидирован
    (см. FallbackClient._run_stream), остальное — прозрачно из исходного
    потока. `Stream.__iter__`/`__next__` в openai-python читают из одного
    и того же закэшированного `self._iterator`, так что once-consumed
    первый чанк не теряется и не дублируется — просто отдаём его сами,
    а дальше делегируем тому же объекту.

    Поддерживает `with client.chat.completions.create(...) as stream:` —
    вызывающий код (api/views/chat.py, chats.py) это использует и не должен
    меняться.
    """
    def __init__(self, first_chunk, stream):
        self._first_chunk = first_chunk
        self._stream = stream
        self._first_yielded = False

    def __iter__(self):
        if not self._first_yielded:
            self._first_yielded = True
            yield self._first_chunk
        yield from self._stream

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        close = getattr(self._stream, 'close', None)
        if callable(close):
            close()
        return False

    def __getattr__(self, name):
        return getattr(self._stream, name)


class _EmptyStream:
    """
    Пустой стрим — провайдер сразу отдал [DONE] без единого чанка (валидный,
    хоть и редкий, ответ — например, на сообщение с пустым результатом).
    Не ошибка, но `with client.chat.completions.create(...) as stream:` в
    вызывающем коде всё равно ждёт контекстный менеджер, а не голый iter(()) —
    делегируем close() исходному объекту, чтобы соединение закрылось штатно.
    """
    def __init__(self, stream):
        self._stream = stream

    def __iter__(self):
        return iter(())

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        close = getattr(self._stream, 'close', None)
        if callable(close):
            close()
        return False

    def __getattr__(self, name):
        return getattr(self._stream, name)


class _CompletionsProxy:
    def __init__(self, parent):
        self._parent = parent

    def create(self, **kwargs):
        kwargs.setdefault('timeout', _CHAT_TIMEOUT)
        if kwargs.get('stream'):
            return self._parent._run_stream('chat', kwargs)
        return self._parent._run('chat', lambda c: c.chat.completions.create(**kwargs))

    def __getattr__(self, name):
        return getattr(self._parent._primary().chat.completions, name)


class _ChatProxy:
    def __init__(self, parent):
        self._parent = parent
        self.completions = _CompletionsProxy(parent)

    def __getattr__(self, name):
        return getattr(self._parent._primary().chat, name)


class _ImagesProxy:
    def __init__(self, parent):
        self._parent = parent

    def generate(self, **kwargs):
        kwargs.setdefault('timeout', _IMAGE_TIMEOUT)
        return self._parent._run('images', lambda c: c.images.generate(**kwargs))

    def edit(self, **kwargs):
        kwargs.setdefault('timeout', _IMAGE_TIMEOUT)
        return self._parent._run('images', lambda c: c.images.edit(**kwargs))

    def __getattr__(self, name):
        return getattr(self._parent._primary().images, name)


class FallbackClient:
    """
    OpenAI-совместимый клиент с прозрачным фолбэком между сервисами.

    Перехватывает только `chat.completions.create`, `images.generate` и
    `images.edit`; всё остальное делегируется основному клиенту без фолбэка.
    """

    def __init__(self, primary):
        # `primary` — имя основного сервиса ('laozhang' | 'apimart')
        self._primary_name = primary
        self.chat = _ChatProxy(self)
        self.images = _ImagesProxy(self)

    def _primary(self):
        return _get_raw_client(self._primary_name)

    def _run(self, kind, fn):
        chain = _order_for(self._primary_name)
        last = None
        for i, provider in enumerate(chain):
            client = _get_raw_client(provider)
            try:
                return fn(client)
            except Exception as e:  # noqa: BLE001
                last = e
                is_last = i == len(chain) - 1
                if is_last or not is_availability_error(e):
                    raise
                nxt = chain[i + 1]
                logger.warning(
                    "[providers] %s недоступен для %s (%s). Фолбэк → %s",
                    provider, kind, e, nxt,
                )
        if last is not None:
            raise last
        # chain пуст быть не может, но на всякий случай.
        raise RuntimeError("Нет доступных AI-провайдеров")

    def _run_stream(self, kind, kwargs):
        """
        Фолбэк для стриминга chat.completions (B13). В отличие от `_run`,
        успехом провайдера считаем не сам факт `.create()` без исключения
        (openai Stream возвращается сразу после заголовков, тело ещё не
        читалось — "принял соединение, но молчит" не поймать по-другому),
        а получение РЕАЛЬНОГО первого чанка тела ответа. Если провайдер
        отдал заголовки и затем не прислал ни байта в течение _CHAT_TIMEOUT —
        это тоже недоступность, пробуем следующий сервис.

        После первого чанка на этот же запрос уже не переключаемся — см.
        _PeekedStream и комментарий про принцип "не менять провайдера в
        процессе уже начавшейся генерации" в шапке модуля.
        """
        chain = _order_for(self._primary_name)
        last = None
        for i, provider in enumerate(chain):
            client = _get_raw_client(provider)
            try:
                stream = client.chat.completions.create(**kwargs)
                it = iter(stream)
                first_chunk = next(it)
            except StopIteration:
                # Пустой стрим (сразу [DONE]) — не ошибка провайдера, отдаём как есть.
                return _EmptyStream(stream)
            except Exception as e:  # noqa: BLE001
                last = e
                is_last = i == len(chain) - 1
                if is_last or not is_availability_error(e):
                    raise
                nxt = chain[i + 1]
                logger.warning(
                    "[providers] %s недоступен для %s (%s, стрим). Фолбэк → %s",
                    provider, kind, e, nxt,
                )
                continue
            return _PeekedStream(first_chunk, stream)
        if last is not None:
            raise last
        raise RuntimeError("Нет доступных AI-провайдеров")

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return getattr(self._primary(), name)
