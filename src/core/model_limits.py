"""
Единый источник правды для потолка completion-токенов по модели.

Раньше этот жёсткий потолок жил только в src/aitext/tasks.py и применялся
только к внутреннему чату (сайт/бот). Внешний dev-API (/api/v1/chat/completions
и /api/v1/messages) принимал max_tokens от клиента без всякой проверки — при
плоской цене за сообщение и моделях, где выходной токен в 5-8 раз дороже
входного (см. TARIFFS.md), это позволяло любому держателю API-ключа запросить
произвольно длинный ответ и получить его дешевле реальной себестоимости.

Это защита от злоупотребления, не инструмент ограничения длины ответа для
обычного пользователя — при нормальном использовании потолок не задевается.
"""

MODEL_MAX_TOKENS_CAP = {
    'gpt-3.5': 4096,
    'gpt-4o': 16384,
    'chatgpt-4o': 16384,
    'gpt-4.1': 16384,
    'gpt-4-turbo': 16384,
    'deepseek': 8192,
    'qwen3-30b-a3b': 12000,
    # Провайдер возвращает 400 invalid_value при превышении лимита модели —
    # значение из БД тоже клампится к этому потолку.
    'claude': 16384,
    # Реальный потолок вывода 12800 (реестр цен APIMart, 2026-09-06) — ниже
    # общего _DEFAULT_CAP=16384, без явной записи клампилось бы до 16384 и
    # ловило бы 400 от провайдера на любом запросе с большим max_tokens.
    'gpt-6-astra': 12800,
}

# Прочие семейства без явного потолка выше — общий консервативный дефолт
# вместо "без ограничения". Раньше здесь было 1_000_000, что на практике
# означало отсутствие защиты для любой не перечисленной явно модели.
_DEFAULT_CAP = 16384


def model_max_tokens_cap(model_name: str) -> int:
    m = (model_name or '').lower()
    for prefix, cap in MODEL_MAX_TOKENS_CAP.items():
        if prefix in m:
            return cap
    return _DEFAULT_CAP


def auto_max_tokens(model_name: str) -> int:
    """Auto max_tokens by model family when not set in DB."""
    return min(32000, model_max_tokens_cap(model_name))


def clamp_max_tokens(requested, model_name: str) -> int:
    """Клампит запрошенное значение (клиентом или из БД) к потолку модели.
    requested может быть None/0/отсутствовать — тогда используется auto_max_tokens.
    """
    cap = model_max_tokens_cap(model_name)
    if requested:
        return min(int(requested), cap)
    return auto_max_tokens(model_name)


# Обнаружено живым тестом 2026-08-27: apimart/Bedrock отдаёт 400
# ValidationException на некоторых моделях Claude, если запрос вообще
# содержит поле temperature — "temperature is deprecated for this model"
# либо "temperature may only be set to 1" (для моделей с расширенным
# рассуждением Bedrock фиксирует temperature сам и не даёт его переопределить).
# Список — только модели, где ошибка реально подтверждена живым вызовом
# API, не догадка по названию: у соседних моделей той же линейки (haiku-4-5,
# sonnet-4-5/4-6) тот же параметр проходит нормально. Если у новой модели
# Claude появится та же ошибка в логах (`api.views.chat` / `aitext.tasks`,
# "temperature is deprecated"/"temperature may only be set to") — добавить
# её exact model_name сюда, а не расширять по префиксу вслепую.
NO_TEMPERATURE_MODELS = {
    'claude-opus-4-7',
    'claude-opus-4-8',
    'claude-opus-5',
    'claude-sonnet-5',
}


def supports_temperature(model_name: str) -> bool:
    return (model_name or '') not in NO_TEMPERATURE_MODELS


# 2026-09-06: reasoning_effort — живьём подтверждено (прямой вызов apimart,
# stream=False) РЕАЛЬНО работающим ТОЛЬКО для этих 4 моделей OpenAI o-серии:
# `reasoning_effort: "high"` меняет реальное поведение провайдера (тест на
# тривиальном вопросе — o3-mini: "low" = 3 токена ответа/0 токенов
# рассуждений, "high" = 854 токена ответа, из них 832 — рассуждения).
# У Claude (Opus/Sonnet 5 и т.д.) через apimart эффект НЕ регулируется —
# провайдер отвечает "thinking.type is managed by the model" на любую
# попытку задать уровень; там доступен только бинарный переключатель
# видимости рассуждений (thinking.display=summarized), не уровень усилий —
# поэтому его сюда не включаем, реклама "5 уровней" для Claude на страницах
# моделей не соответствует тому, что реально отдаёт apimart.
#
# Доплата — не жёсткая защита (у этих 4 моделей нет записи в MODEL_WHOLESALE,
# т.е. полноценного token-overage billing нет, см. TOKEN_OVERAGE_BILLING_PLAN.md
# и аудит от 2026-09-06), а оценка по ~6000 токенам рассуждений на "трудный"
# запрос (реально наблюдался 832 на тривиальном; жёсткий потолок ответа для
# этих моделей — 16384, см. _DEFAULT_CAP, они не в MODEL_MAX_TOKENS_CAP) —
# ×105 (K) на реальную wholesale-цену выходного токена у apimart
# (0.8×official, см. "Реестр цен APIMart текстовые модели.html"):
# o1 $48/1M (оценка по паттерну 0.8× от official $60, живьём в реестре не
# нашлось), o3 $6.4/1M, o3-mini/o4-mini $3.52/1M (оба живьём подтверждены).
REASONING_EFFORT_MODELS = {'o1', 'o3', 'o3-mini', 'o4-mini'}

REASONING_EFFORT_SURCHARGE_KOPECKS = {
    'o1': 3000,       # ~30₽
    'o3': 400,        # ~4₽
    'o3-mini': 250,   # ~2.5₽
    'o4-mini': 250,   # ~2.5₽
}

# При reasoning_effort='high' режем потолок ответа вдвое от общего
# _DEFAULT_CAP (16384) — снижает абсолютный худший случай (доплата выше
# рассчитана на ~6000 токенов рассуждений, не на весь потолок), не влияя на
# типичный запрос (реальный расход в тесте — 832 токена, с большим запасом).
REASONING_EFFORT_MAX_TOKENS = 8000


def reasoning_effort_surcharge_kopecks(model_name: str, reasoning_effort: str | None) -> int:
    if reasoning_effort != 'high':
        return 0
    return REASONING_EFFORT_SURCHARGE_KOPECKS.get((model_name or '').lower(), 0)
