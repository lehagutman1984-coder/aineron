"""
Per-request язык каталога (Category/NeuralNetwork/FAQ) — GLOBAL_EXPANSION_PLAN.md G5.

Почему не django.utils.translation.activate(): USE_I18N=False (см. settings.py)
отключает django.utils.translation на уровне фреймворка — activate() становится
no-op, get_language() всегда возвращает settings.LANGUAGE_CODE независимо от
запроса. modeltranslation полагается именно на get_language(), поэтому его
автоматическая подстановка полей (obj.description) НИКОГДА не меняется от
запроса к запросу — она статична для инстанса (ru на .ru, en на .net).

Здесь — обходной путь в обход этого: сериализаторы явно читают ?lang= и
достают нужное поле через getattr(obj, f'{field}_{suffix}'), с фолбэком на
«сырое» поле (= LANGUAGE_CODE инстанса). Без ?lang=, а также при отсутствии
перевода для запрошенного языка — поведение идентично тому, что было
до этой фичи: ноль риска регрессии для существующих клиентов.
"""
from django.conf import settings

# django-modeltranslation мапит ISO 'id' → суффикс 'ind' (избегает коллизии
# с конвенцией *_id для внешних ключей). См. сгенерированную миграцию.
_FIELD_SUFFIX = {
    'id': 'ind',
}

SUPPORTED_CATALOG_LANGS = {code for code, _ in settings.LANGUAGES}


def resolve_catalog_lang(request) -> str | None:
    """?lang=xx (валидируется по settings.LANGUAGES) → код языка либо None.

    None означает "использовать поведение по умолчанию" (текущее статичное
    поле modeltranslation для LANGUAGE_CODE инстанса) — сохраняет обратную
    совместимость для всех вызовов без explicit ?lang=.
    """
    lang = (request.query_params.get('lang') or '').strip().lower()
    if lang in SUPPORTED_CATALOG_LANGS:
        return lang
    return None


def translated_field(obj, field: str, lang: str | None) -> str:
    """Значение переводимого поля для конкретного языка с фолбэком.

    Фолбэк — ВСЕГДА «сырое» поле через дескриптор modeltranslation, то
    есть значение для LANGUAGE_CODE инстанса (ru на .ru, en на .net). НЕ
    хардкодим 'en' как универсальный фолбэк — .ru шлёт ?lang=ru на каждый
    запрос (см. frontend/lib/api/server.ts), и если бы отсутствующий
    {field}_ru фолбэчился на {field}_en раньше {field}_ru-via-raw, русский
    пользователь увидел бы английский текст вместо русского оригинала.
    Раньше (без ?lang=) это было невозможно — обычный getattr(obj, field)
    и так возвращал ru-значение. Фолбэк на «сырое» поле сохраняет то же
    гарантированно-безопасное поведение и при explicit ?lang=.
    """
    if lang:
        suffix = _FIELD_SUFFIX.get(lang, lang)
        value = getattr(obj, f'{field}_{suffix}', None)
        if value:
            return value
    return getattr(obj, field, '') or ''
