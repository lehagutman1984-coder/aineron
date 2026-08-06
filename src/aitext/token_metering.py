"""
Единственная точка записи реального расхода токенов на сообщение.

TOKEN_OVERAGE_BILLING_PLAN.md, Спринт 1 — только метрирование, ни одна
копейка не меняет владельца. record_usage() вызывается из всех путей
генерации текста (Celery-путь бота/веб-polling, веб-SSE) и никогда не
должна ронять генерацию — любая ошибка здесь только логируется.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def record_usage(message, network, channel, prompt_tokens, completion_tokens, source,
                  flat_was_charged=False, flat_kopecks=0):
    """
    Записать/обновить MessageTokenUsage для message. update_or_create — не
    create: на SSE-пути основной вызов и страховочный finally оба могут
    попытаться записать строку для одного сообщения (см. Спринт 1, задача 5
    плана), OneToOneField иначе бросит IntegrityError на втором вызове.
    """
    if not getattr(settings, 'TOKEN_METERING_ENABLED', False):
        return None
    try:
        from aitext.models import MessageTokenUsage

        channel_value = channel if channel in MessageTokenUsage.Channel.values else MessageTokenUsage.Channel.WEB
        source_value = source if source in MessageTokenUsage.Source.values else MessageTokenUsage.Source.MISSING

        row, _ = MessageTokenUsage.objects.update_or_create(
            message=message,
            defaults=dict(
                network=network,
                model_name=getattr(network, 'model_name', '') or '',
                channel=channel_value,
                prompt_tokens=int(prompt_tokens or 0),
                completion_tokens=int(completion_tokens or 0),
                source=source_value,
                flat_was_charged=bool(flat_was_charged),
                flat_kopecks=int(flat_kopecks or 0),
            ),
        )
        return row
    except Exception as e:
        logger.warning(f"[token_metering] record_usage failed for message {getattr(message, 'id', None)}: {e}")
        return None


def compute_overage(usage_row):
    """
    TOKEN_OVERAGE_BILLING_PLAN.md, §2.3 — расчёт доплаты за длинный ответ.
    НИЧЕГО не списывает (это Спринт 3, settle) — только вычисляет.

    Возвращает (cost_kopecks, overage_kopecks):
    - cost_kopecks — реальная себестоимость (int) или None, если модель не
      аудирована (core.model_pricing.wholesale_rates). Вычисляется НЕЗАВИСИМО
      от прав на overage ниже — нужна для отчёта по марже (Спринт 2, задача 4)
      даже на бесплатных/безлимитных сообщениях, где overage всегда 0.
    - overage_kopecks — 0, если сработал любой guard. ПЕРВЫЙ guard —
      `flat_was_charged` (см. §2.3.1 плана): при `flat_was_charged=False`
      (безлимитный/бесплатный тариф — network.unlimited или is_free, реальный
      flat_kopecks в БД будет 0) overage обязан быть 0 БЕЗУСЛОВНО, а не
      выводиться из cap-формулы — иначе безлимитный пользователь у потолка
      токенов получает тихое платное списание на модели, объявленной
      бесплатной. Проверяется первым, до всей остальной формулы.
    """
    from django.conf import settings as dj_settings
    from core import model_pricing
    from aitext.models import MessageTokenUsage

    cost = model_pricing.cost_kopecks(usage_row.model_name, usage_row.prompt_tokens, usage_row.completion_tokens)
    if cost is None:
        return None, 0

    if not usage_row.flat_was_charged:
        return cost, 0
    if usage_row.source != MessageTokenUsage.Source.PROVIDER:
        return cost, 0
    allowlist = getattr(dj_settings, 'TOKEN_OVERAGE_MODELS', [])
    if allowlist and usage_row.model_name not in allowlist:
        return cost, 0

    flat = int(usage_row.flat_kopecks or 0)
    markup = float(getattr(dj_settings, 'TOKEN_OVERAGE_MARKUP', 1.6))
    target = round(cost * markup)
    overage_raw = target - flat

    min_fraction = float(getattr(dj_settings, 'TOKEN_OVERAGE_MIN_FRACTION', 0.25))
    min_kopecks = int(getattr(dj_settings, 'TOKEN_OVERAGE_MIN_KOPECKS', 100))
    threshold = max(min_kopecks, flat * min_fraction)

    cap_multiple = float(getattr(dj_settings, 'TOKEN_OVERAGE_CAP_MULTIPLE', 2.0))
    abs_cap = int(getattr(dj_settings, 'TOKEN_OVERAGE_ABS_CAP_KOPECKS', 4000))
    cap = max(flat * cap_multiple, abs_cap)

    overage = overage_raw if overage_raw >= threshold else 0
    overage = min(overage, cap) if overage > 0 else 0
    return cost, max(0, int(overage))


def apply_overage(usage_row):
    """Вычисляет и сохраняет cost_kopecks/overage_kopecks на уже записанную
    MessageTokenUsage строку. Вызывать сразу после record_usage. settled_kopecks
    здесь не трогается — это Спринт 3 (settle), в Спринте 2 всегда 0."""
    if usage_row is None or not getattr(usage_row, 'pk', None):
        return
    try:
        cost, overage = compute_overage(usage_row)
        usage_row.cost_kopecks = cost or 0
        usage_row.overage_kopecks = overage
        usage_row.save(update_fields=['cost_kopecks', 'overage_kopecks'])
    except Exception as e:
        logger.warning(f"[token_metering] apply_overage failed for usage_row {getattr(usage_row, 'id', None)}: {e}")


def settle_overage(usage_row):
    """
    TOKEN_OVERAGE_BILLING_PLAN.md, Спринт 3 — единственная точка, где доплата
    реально списывается. Возвращает списанное ИМЕННО В ЭТОМ вызове (копейки):
    0 при любом no-op (выключено, dry-run, уже списано, нечего списывать).

    Идемпотентность двухслойная:
    - `unique(type, reference)` на BalanceTransaction делает второе списание
      физически невозможным (users/models.py);
    - но `spend_kopecks` при дубликате возвращает True, не отличая «списал» от
      «уже было» (users/models.py:680-683), поэтому перед неидемпотентными
      side-эффектами (UserSpending) идёт явная проба по идиоме
      studio/billing.py:106-116. Это же закрывает падение процесса между
      списанием и обновлением строки: транзакция в ledger есть, settled_at
      пуст — второй вызов только доотметит строку, не списывая повторно;
    - от гонки двух ОДНОВРЕМЕННЫХ settle (инлайн + реконсилер) защищает
      condition-UPDATE `settled_at__isnull=True` в начале транзакции — сама
      проба выше это check-then-act и в одиночку недостаточна.

    Ошибка списания (нехватка баланса — гонка с параллельным запросом,
    preflight-клэмп её только сужает, но не исключает) НЕ бросается наверх:
    settled_at остаётся пустым, строку подберёт reconcile_unsettled_overage.
    Логируется на ERROR (не warning, как метрирование) — это деньги.
    """
    from django.conf import settings as dj_settings
    from django.db import transaction
    from django.utils import timezone
    from aitext.models import MessageTokenUsage
    from users.models import BalanceTransaction, UserSpending

    if usage_row is None or not getattr(usage_row, 'pk', None):
        return 0
    overage = int(usage_row.overage_kopecks or 0)
    if overage <= 0 or usage_row.settled_at is not None:
        return 0
    if not getattr(dj_settings, 'TOKEN_OVERAGE_ENABLED', False):
        return 0

    reference = f'overage:{usage_row.message_id}'
    if getattr(dj_settings, 'TOKEN_OVERAGE_DRY_RUN', True):
        logger.info(f"[overage][dry-run] {reference}: {overage} коп. рассчитано, не списано "
                    f"({usage_row.model_name}, {usage_row.prompt_tokens}/{usage_row.completion_tokens})")
        return 0

    try:
        user = usage_row.message.chat.user
        already = BalanceTransaction.objects.filter(
            user=user, type=BalanceTransaction.Type.OVERAGE, reference=reference,
        ).exists()

        with transaction.atomic():
            # Condition-UPDATE идёт ПЕРВЫМ и работает как блокировка: сама
            # `.exists()`-проба выше — check-then-act, и два параллельных settle
            # (инлайн + реконсилер после того, как его заведут в Beat) оба
            # увидели бы already=False. Второй тогда получил бы от spend_kopecks
            # True по проглоченному IntegrityError и создал бы вторую
            # UserSpending. Кто выиграл этот UPDATE — тот и списывает.
            marked = MessageTokenUsage.objects.filter(
                pk=usage_row.pk, settled_at__isnull=True,
            ).update(settled_kopecks=overage, settled_at=timezone.now())
            if not marked:
                return 0
            if not already:
                if not user.spend_kopecks(overage, type=BalanceTransaction.Type.OVERAGE, reference=reference):
                    logger.error(
                        f"[overage] {reference}: списание {overage} коп. не прошло — "
                        f"недостаточно средств у user={user.id} (баланс {user.balance_kopecks} коп.). "
                        f"settled_at остаётся пустым, подберёт reconcile_unsettled_overage."
                    )
                    # Откатываем и отметку строки тоже — иначе сообщение
                    # осталось бы «списанным» без единой копейки в ledger.
                    transaction.set_rollback(True)
                    return 0
                UserSpending.objects.create(
                    user=user, amount=overage // 100, amount_kopecks=overage,
                    # Отличимое описание — единственная поверхность прозрачности
                    # при обрыве соединения (§1.1(б)): строка сама появляется в
                    # /account/analytics/ без изменений фронта.
                    description=f"Доплата за длинный ответ, {usage_row.model_name}",
                )

        usage_row.refresh_from_db(fields=['settled_kopecks', 'settled_at'])
        if already:
            return 0
        logger.info(f"[overage] {reference}: списано {overage} коп. ({usage_row.model_name}, "
                    f"{usage_row.prompt_tokens}/{usage_row.completion_tokens} токенов)")
        return overage
    except Exception as e:
        logger.error(f"[overage] {reference}: settle упал ({e}) — деньги могут быть не списаны, "
                     f"подберёт reconcile_unsettled_overage", exc_info=True)
        return 0


# Ниже этого значения ответ уже бессмысленно обрезать — клэмп не опускается
# дальше, даже если пользователь не может оплатить и столько. Остаточный риск
# нехватки на settle покрывает реконсилер (§3.3, вариант C + B как страховка).
PREFLIGHT_MIN_MAX_TOKENS = 1024


def overage_settle_active():
    """Списывается ли доплата прямо сейчас. Дешёвая проверка для вызывающих —
    оценка длины промта под preflight_max_tokens сканирует весь контекст, и
    делать это на каждом сообщении при выключенной доплате незачем."""
    from django.conf import settings as dj_settings
    return (bool(getattr(dj_settings, 'TOKEN_OVERAGE_ENABLED', False))
            and not getattr(dj_settings, 'TOKEN_OVERAGE_DRY_RUN', True))


def estimate_prompt_tokens(messages_for_api):
    """Грубая оценка длины промта для preflight-клэмпа (§3.3). Это защитная
    граница, а не счёт — точность не критична, поэтому локальная эвристика
    aitext.memory.estimate_tokens, без tiktoken."""
    from aitext.memory import estimate_tokens
    total = 0
    for m in messages_for_api or []:
        content = m.get('content') if isinstance(m, dict) else None
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and isinstance(part.get('text'), str):
                    total += estimate_tokens(part['text'])
    return total


def preflight_max_tokens(model_name, max_tokens, prompt_tokens, flat_kopecks, head_kopecks):
    """
    TOKEN_OVERAGE_BILLING_PLAN.md §3.3, вариант C: сузить ответ до того, что
    пользователь способен оплатить, вместо отказа в запросе и вместо ситуации
    «сгенерировали, а доплату списать нечем».

    head_kopecks — баланс, который останется ПОСЛЕ плоского списания.
    Возвращает max_tokens без изменений везде, где доплата невозможна
    (выключено, dry-run, модель не аудирована/не в allowlist, плоского
    списания не было). Клэмп — user-visible обрезание ответа, поэтому под
    dry-run он обязан быть полным no-op: считать, но не трогать генерацию.
    """
    from django.conf import settings as dj_settings
    from core import model_pricing

    try:
        max_tokens = int(max_tokens or 0)
        if max_tokens <= 0:
            return max_tokens
        if not overage_settle_active():
            return max_tokens
        flat = int(flat_kopecks or 0)
        if flat <= 0:
            return max_tokens  # flat_was_charged=False ⇒ overage всегда 0 (§2.3.1)
        allowlist = getattr(dj_settings, 'TOKEN_OVERAGE_MODELS', [])
        if allowlist and model_name not in allowlist:
            return max_tokens
        rates = model_pricing.wholesale_rates(model_name)
        if rates is None:
            return max_tokens

        markup = float(getattr(dj_settings, 'TOKEN_OVERAGE_MARKUP', 1.6))
        cap_multiple = float(getattr(dj_settings, 'TOKEN_OVERAGE_CAP_MULTIPLE', 2.0))
        abs_cap = int(getattr(dj_settings, 'TOKEN_OVERAGE_ABS_CAP_KOPECKS', 4000))
        cap = max(flat * cap_multiple, abs_cap)
        head = max(0, int(head_kopecks or 0))

        worst_cost = model_pricing.cost_kopecks(model_name, prompt_tokens, max_tokens) or 0
        worst_overage = min(max(0, round(worst_cost * markup) - flat), cap)
        if worst_overage <= head:
            return max_tokens

        # overage(out) ≤ head  ⇔  cost(out) × markup ≤ head + flat
        in_usd_per_1m, out_usd_per_1m = rates
        usd_rub = float(getattr(dj_settings, 'TOKEN_OVERAGE_USD_RUB', 80))
        kopecks_per_out_token = out_usd_per_1m / 1_000_000 * usd_rub * 100
        if kopecks_per_out_token <= 0:
            return max_tokens
        budget_cost = (head + flat) / markup
        prompt_cost = int(prompt_tokens or 0) * in_usd_per_1m / 1_000_000 * usd_rub * 100
        affordable = int((budget_cost - prompt_cost) / kopecks_per_out_token)

        clamped = max(PREFLIGHT_MIN_MAX_TOKENS, min(max_tokens, affordable))
        if clamped < max_tokens:
            logger.info(f"[overage][preflight] {model_name}: max_tokens {max_tokens} → {clamped} "
                        f"(баланс после плоского списания {head} коп.)")
        return clamped
    except Exception as e:
        logger.warning(f"[overage][preflight] клэмп не применён для {model_name}: {e}")
        return max_tokens


def channel_for_chat(chat):
    """web | telegram — по наличию TelegramChat на chat."""
    try:
        from telegram_bot.models import TelegramChat
        from aitext.models import MessageTokenUsage
        if TelegramChat.objects.filter(chat=chat).exists():
            return MessageTokenUsage.Channel.TELEGRAM
        return MessageTokenUsage.Channel.WEB
    except Exception:
        from aitext.models import MessageTokenUsage
        return MessageTokenUsage.Channel.WEB
