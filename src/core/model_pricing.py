"""
Оптовые $/1M-токен ставки провайдера по аудированным моделям
(TOKEN_OVERAGE_BILLING_PLAN.md, Спринт 2, §2.5) — источник истины для
себестоимости сообщения при расчёте доплаты за длинный ответ.

По образцу core/model_limits.py: та же конвенция префиксного матчинга,
тот же принцип "неаудированная модель = None, а не угадывание".

Ключи — model_name из БД (проверено запросом к проде в этой же сессии):
дефис, не точка (`claude-opus-4-8`, не `claude-opus-4.8`) — иначе
префиксный матч молча не находит модель вообще.
"""

# (input_usd_per_1m, output_usd_per_1m) — см. §2.5 плана для обоснования цифр
MODEL_WHOLESALE = {
    'claude-fable-5':  (10.0,  50.0),
    'claude-opus-4-8': (5.0,   25.0),
    'claude-opus-5':   (5.0,   25.0),
    'gpt-5-pro':       (15.0,  120.0),
    'gpt-5.4-pro':     (30.0,  180.0),
    'gpt-5.3':         (60.0,  60.0),
    'gpt-5.6-terra':   (2.0,   12.0),
}


def wholesale_rates(model_name):
    """
    None — модель не аудирована, overage невозможен (compute_overage должен
    вернуть 0, не пытаться оценить себестоимость по умолчанию).

    Возвращает ставки САМОГО ДЛИННОГО совпавшего префикса (longest-prefix-
    wins), а не первого по порядку словаря — иначе будущий вариант модели
    (например claude-opus-5-thinking) молча унаследует ставки claude-opus-5,
    даже если реальная стоимость другая. Ровно так завёлся баг $60/$60 у
    варианта gpt-5.3, разобранный в этом же аудите (TARIFFS.md).
    """
    m = (model_name or '').lower()
    matches = [(prefix, rates) for prefix, rates in MODEL_WHOLESALE.items() if prefix in m]
    if not matches:
        return None
    return max(matches, key=lambda pr: len(pr[0]))[1]


def cost_kopecks(model_name, prompt_tokens, completion_tokens):
    """
    Реальная себестоимость сообщения в копейках, округлённая до целого —
    round() применяется ЗДЕСЬ, а не в вызывающем коде: compute_overage
    считает target_kopecks от уже округлённого cost_kopecks (см. §2.3 плана,
    рабочий пример Opus 5 1850/10428 сходится только в этом порядке
    округления: cost=2160, target=round(2160×1.6)=3456, не 3455).

    None, если модель не аудирована.
    """
    rates = wholesale_rates(model_name)
    if rates is None:
        return None
    in_usd_per_1m, out_usd_per_1m = rates
    from django.conf import settings
    usd_rub = float(getattr(settings, 'TOKEN_OVERAGE_USD_RUB', 80))
    usd = (int(prompt_tokens or 0) * in_usd_per_1m + int(completion_tokens or 0) * out_usd_per_1m) / 1_000_000
    return round(usd * usd_rub * 100)


def worst_case_cost_kopecks(model_name, prompt_tokens):
    """Себестоимость при максимально возможном completion (потолок модели,
    core.model_limits.model_max_tokens_cap) — верхняя граница риска на
    сообщение, используется в отчётах/калибровке (Спринт 2, задача 4/5)."""
    from core.model_limits import model_max_tokens_cap
    return cost_kopecks(model_name, prompt_tokens, model_max_tokens_cap(model_name))
