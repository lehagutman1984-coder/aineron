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
