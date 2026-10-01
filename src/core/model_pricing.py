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

# (input_usd_per_1m, output_usd_per_1m) — см. §2.5 плана для обоснования цифр.
#
# 2026-09-28 (аудит после инцидента с claude-opus-5, STATUS_AND_BACKLOG_PLAN):
# таблица расширена почти до всего активного текстового каталога. Источник
# для новых строк — frontend/lib/data/pricingPreviewModels.ts (это же $/1M,
# из которых 2026-09-02..03 выведена розничная cost_kopecks по формуле
# round(usd_за_стандартное_сообщение × K=105 × 100), K — retail-константа,
# НЕ связанная с TOKEN_OVERAGE_USD_RUB ниже) и PRICING_SIMPLIFICATION_PLAN.md
# §1.1 (сверка листа OpenRouter/apimart/kie). Правило — максимум известных
# источников (безопаснее переоценить свою себестоимость, чем недооценить):
# apimart-цена берётся вместо листа, если она выше (см. gpt-5.6-sol).
# Уверенность разная — модели, где сама розница считалась НЕ по этой ставке
# (конкурентный репрайсинг 2026-09-07, дальше «no own data»), помечены явно.
MODEL_WHOLESALE = {
    'claude-fable-5':     (10.0,  50.0),   # OpenRouter, PRICING_SIMPLIFICATION_PLAN.md §1.1
    'claude-opus-4-8':    (5.0,   25.0),   # OpenRouter §1.1
    'claude-opus-5':      (5.0,   25.0),   # OpenRouter §1.1 (тот же тир, что 4.8)
    # 2026-10-01 (живой баг, messages 3719/3721): без ЭТИХ двух строк
    # claude-sonnet-5-5/claude-opus-5-5 молча матчились по substring на
    # claude-sonnet-5/claude-opus-5 (longest-prefix-wins не спасал — это был
    # ЕДИНСТВЕННЫЙ матч) и считались по ЧУЖОЙ, более дорогой ставке — ровно
    # тот класс бага, что описан в докстринге canonical_key() (claude-opus-5-
    # thinking/gpt-5.3). Подтверждено пересчётом задним числом: реальная
    # cost_kopecks у msg 3719/3721 (3/12 коп.) точно сходится с ЧУЖОЙ ставкой
    # (2.0/10.0 и 5.0/25.0 ниже), а не с настоящей апимарт-ставкой модели
    # (1.6/8.0 и 3.2/16.0, см. add_sonnet55_opus55_grok47.py).
    'claude-sonnet-5-5':  (1.6,   8.0),    # apimart, add_sonnet55_opus55_grok47.py
    'claude-opus-5-5':    (3.2,   16.0),   # apimart, add_sonnet55_opus55_grok47.py
    'claude-sonnet-5':    (2.0,   10.0),   # OpenRouter §1.1, pricingPreviewModels.ts
    'claude-sonnet-4-6':  (3.0,   15.0),   # pricingPreviewModels.ts (предыдущее поколение Sonnet)
    'claude-haiku-4-5':   (1.0,   5.0),    # pricingPreviewModels.ts
    'gpt-5.6-terra':      (2.0,   12.0),   # OpenRouter §1.1
    'gpt-5.6-sol':        (3.2,   16.0),   # apimart §1.1 — ВЫШЕ листа OpenRouter (2/10), берём апимарт
    'gpt-5.6-luna':       (0.2,   1.2),    # pricingPreviewModels.ts
    # 2026-10-01: GPT-6 Sol/6.1 Sol — та же реальная апимарт-ставка, что
    # задокументирована в add_gpt6_sol_luna_models.py при заведении моделей.
    # Разные ключи (не substring друг друга и не gpt-6-astra) — обе нужны
    # явно, иначе canonical_key() вернёт None и overage будет тихо 0.
    'gpt-6-sol':          (1.6,   8.0),    # apimart, add_gpt6_sol_luna_models.py
    'gpt-6.1-sol':        (1.6,   8.0),    # apimart, add_gpt6_sol_luna_models.py
    # gpt-6-luna сознательно НЕ добавлена — тот же случай, что gpt-5.6-luna
    # ниже: слишком дёшево, overage не имеет смысла при текущих порогах
    # (TOKEN_OVERAGE_MIN_FRACTION/MIN_KOPECKS).
    'gpt-5.5-pro':        (30.0,  180.0),  # pricingPreviewModels.ts (round(30)/round(180))
    'gpt-5.5':            (5.0,   30.0),   # pricingPreviewModels.ts
    # gpt-6-astra: розница переставлена на конкурент×0.95 07.09 (не опт×K) —
    # сам файл-источник прямо указывает опт "было бы 840/4200" при K=105.
    'gpt-6-astra':        (8.0,   40.0),   # pricingPreviewModels.ts, комментарий у gpt-6-astra
    'gemini-3.1-pro':     (2.0,   12.0),   # pricingPreviewModels.ts, §1.1
    'gemini-3.6-flash':   (0.75,  3.75),   # pricingPreviewModels.ts, подтверждено живьём на OpenRouter
    'gemini-3.7-flash':   (0.75,  3.75),   # pricingPreviewModels.ts (тот же тир, что 3.6, нет отдельных данных)
    'grok-4.7':            (1.6,  4.8),    # apimart, add_sonnet55_opus55_grok47.py (2026-10-01)
    'grok-4.6':            (2.0,  6.0),    # OpenRouter §1.1
    'grok-4.5':            (2.0,  6.0),    # снята с публичного прайса — тир 4.6, своих данных нет
    'qwen3.8-max':         (2.0,  6.0),    # OpenRouter §1.1
    'qwen3.6-max':         (2.0,  6.0),    # снята с публичного прайса — тир 3.8, своих данных нет
    # DeepSeek: retail — оценка по СЕРЕДИНЕ диапазона OpenRouter (см. её же
    # комментарий); для opt-таблицы (используется на защиту нашей маржи)
    # берём ВЕРХ диапазона OpenRouter §1.1 — безопаснее переоценить.
    'deepseek-v4-pro':     (1.32, 3.96),   # верх диапазона OpenRouter §1.1 (0.66-1.32 / 1.98-3.96)
    'deepseek-v4-flash':   (0.1,  0.22),   # pricingPreviewModels.ts (retail-оценка, ставки очень малы)
    # Ниже — устаревшие/неактивные в текущем каталоге записи (2026-09-28: нет
    # среди активных model_name), оставлены безвредно — если модель когда-то
    # вернётся под этим именем, ставка уже готова.
    'gpt-5-pro':       (15.0,  120.0),
    'gpt-5.4-pro':     (30.0,  180.0),
    'gpt-5.3':         (60.0,  60.0),
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


def canonical_key(model_name):
    """Ключ MODEL_WHOLESALE, реально сматчившийся для model_name (longest-prefix-
    wins, та же логика, что в wholesale_rates), или None.

    2026-09-28: до этой функции allowlist в TOKEN_OVERAGE_MODELS/
    TOKEN_METERING_STREAM_USAGE_MODELS сверялся С ТОЧНЫМ model_name
    (`model_name not in allowlist`), а ставки — префиксным совпадением.
    Из-за этого `claude-fable-5.1` (ставки есть через префикс 'claude-fable-5')
    не получал ни overage, ни preflight-клэмп, если в allowlist был вписан
    только `claude-fable-5` — самая дорогая активная модель оставалась вообще
    без защиты. Единое правило (см. overage_eligible) закрывает это классом,
    а не точечной правкой одного имени."""
    m = (model_name or '').lower()
    matches = [prefix for prefix in MODEL_WHOLESALE if prefix in m]
    if not matches:
        return None
    return max(matches, key=len)


def overage_eligible(model_name, allowlist):
    """Модель одновременно аудирована (есть ставки) И разрешена allowlist'ом.

    allowlist пуст ⇒ разрешена вся таблица (см. settings.TOKEN_OVERAGE_MODELS).
    Иначе разрешена, если В allowlist попал канонический ключ ставки ИЛИ сам
    model_name (второе — обратная совместимость со старыми env-списками,
    где вписывали точное имя модели, а не префикс)."""
    key = canonical_key(model_name)
    if key is None:
        return False
    if not allowlist:
        return True
    return key in allowlist or (model_name or '') in allowlist


# Розничная цена (NeuralNetwork.cost_kopecks) выведена из опта по формуле
# round(usd_за_стандартное_сообщение × PRICING_K_RETAIL × 100), где стандартное
# сообщение — 6000 входных / 1500 выходных токенов (PRICING_SIMPLIFICATION_PLAN.md
# §3/§9.3). Это НЕ то же самое, что settings.TOKEN_OVERAGE_USD_RUB (операционный
# курс расчёта доплаты) — две разные константы, отсюда и деление ниже.
PRICING_K_RETAIL = 105
_STANDARD_PROMPT_TOKENS = 6000
_STANDARD_COMPLETION_TOKENS = 1500


def is_model_blocked_for_trial(network) -> bool:
    """Rule S (free_tier guard, часть B): модель вообще не предлагается пробному
    (никогда не плативше­му) пользователю, если её флоат-цена сама по себе не
    оставляет пробному гранту запаса хотя бы на FREE_TIER_MIN_MESSAGES сообщений.

    Порог считается от ГРАНТА (Tariff.get_default_tariff().balance_grant_kopecks),
    а не от текущего остатка — иначе модель становилась бы «недоступной» посреди
    уже оплаченного диалога по мере того, как баланс тает.

    Место вызова само решает, кого проверять (обычно — user.is_unpaid_free_user());
    эта функция ничего не знает о конкретном пользователе, только о модели.

    2026-09-28 (ревью): единственная функция в этом защитном семействе (см.
    free_tier_guard/preflight_max_tokens в aitext/token_metering.py, которые
    специально спроектированы fail-open) БЕЗ try/except. Tariff.get_default_tariff()
    делает get_or_create — реальный DB-запрос/запись; любой транзиентный сбой
    БД здесь раньше давал 500 на КАЖДОЙ попытке пробного пользователя отправить
    сообщение (Rule S срабатывает до создания чата/списания денег — деньги не
    страдали, но запрос падал). Приведено к тому же fail-open стилю."""
    from django.conf import settings
    import logging
    logger = logging.getLogger(__name__)

    try:
        if not getattr(settings, 'FREE_TIER_GUARD_ENABLED', False):
            return False
        min_messages = int(getattr(settings, 'FREE_TIER_MIN_MESSAGES', 3) or 0)
        if min_messages <= 0:
            return False
        from users.models import Tariff
        grant = int(Tariff.get_default_tariff().balance_grant_kopecks or 0)
        if grant <= 0:
            return False
        threshold = grant // min_messages
        return int(getattr(network, 'cost_kopecks', 0) or 0) > threshold
    except Exception as e:
        logger.warning(f"[free_tier_guard] is_model_blocked_for_trial не применён: {e}")
        return False


def estimated_cost_kopecks(network, prompt_tokens, completion_tokens):
    """Верхняя граница себестоимости (копейки) для модели БЕЗ аудированных
    ставок — по розничной цене сообщения (`network.cost_kopecks`), которая
    известна всегда, без ручного аудита.

    Строго доказуемая верхняя граница (не догадка): для любого разбиения
    in/out-ставок opt-цена запроса in×p + out×o ≤ M × (in×6000 + out×1500),
    где M = max(p/6000, o/1500) — потому что p ≤ M×6000 и o ≤ M×1500 по
    определению M. Правая часть — это ровно opt-цена «стандартного сообщения»
    × M, а opt-цена стандартного сообщения = cost_kopecks / (PRICING_K_RETAIL×100)
    по построению розничной цены. Итог — оценка растёт с размером промта, но
    никогда не занижает реальный опт (только переоценивает — безопасное
    направление ошибки для защитного механизма).

    Используется ТОЛЬКО для превентивной защиты бесплатных пользователей
    (core.model_pricing/token_metering: free_tier_guard) — никогда для
    реального списания доплаты, для этого по-прежнему нужны аудированные
    ставки (cost_kopecks выше).

    Если модель аудирована — прозрачно делегирует туда (аудит точнее оценки).
    """
    from django.conf import settings

    audited = cost_kopecks(getattr(network, 'model_name', ''), prompt_tokens, completion_tokens)
    if audited is not None:
        return audited

    retail = int(getattr(network, 'cost_kopecks', 0) or 0)
    if retail <= 0:
        return 0
    usd_rub = float(getattr(settings, 'TOKEN_OVERAGE_USD_RUB', 80))
    k_retail = float(getattr(settings, 'PRICING_K_RETAIL', PRICING_K_RETAIL))
    if k_retail <= 0:
        return retail
    m = max(
        int(prompt_tokens or 0) / _STANDARD_PROMPT_TOKENS,
        int(completion_tokens or 0) / _STANDARD_COMPLETION_TOKENS,
    )
    import math
    return math.ceil(retail * usd_rub / k_retail * m)
