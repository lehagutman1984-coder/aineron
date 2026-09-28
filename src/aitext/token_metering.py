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
    if not model_pricing.overage_eligible(usage_row.model_name, allowlist):
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
        # 2026-09-28 (ревью): при сбое здесь usage_row.overage_kopecks остаётся
        # на дефолте 0 — в отличие от settle_overage (где недосчитанное явно
        # видно через overage_kopecks>0 + settled_at пусто, и подхватывается
        # reconcile_unsettled_overage), эту строку реконсилер НЕ подберёт: он
        # ищет overage_kopecks>0, а тут 0 — формально "нечего досчитывать".
        # Недосчитанная доплата по такой строке теряется без следа, кроме
        # лога — поднято до error (деньги), как и у settle_overage.
        logger.error(f"[token_metering] apply_overage failed for usage_row {getattr(usage_row, 'id', None)}: {e}", exc_info=True)


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

    2026-09-28 (ревью, раунд 3, TOKEN_OVERAGE_RESERVE_ENABLED): если сообщение
    получило атомарный резерв (reserve_overage_tokens, message.settings
    ['overage_reserve_reference']), settle НЕ списывает overage целиком
    заново — он НЕТТО-ЗАЧИТЫВАЕТ факт против уже зарезервированной суммы
    (см. _settle_against_reservation). Это reservation-aware поведение
    работает БЕЗУСЛОВНО, не за флагом — именно это делает выключение
    TOKEN_OVERAGE_RESERVE_ENABLED безопасным откатом: уже созданные резервы
    доселятся корректно и после выключения флага, дубль-списания не будет
    (обе ветки читают/пишут непересекающиеся reference'ы в ledger).
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

        reserve_ref = (usage_row.message.settings or {}).get('overage_reserve_reference')
        if reserve_ref:
            _reserve_txn = BalanceTransaction.objects.filter(
                user=user, type=BalanceTransaction.Type.OVERAGE, reference=reserve_ref,
            ).first()
            reserved_kopecks = abs(int(_reserve_txn.amount_kopecks or 0)) if _reserve_txn else 0
            if reserved_kopecks > 0:
                return _settle_against_reservation(usage_row, user, overage, reserved_kopecks, reserve_ref)
            # reserve_ref в settings есть, но ledger-записи нет (например, резерв
            # был 0 — overage при клэмпнутом max_tokens не достигал порога) —
            # падаем в обычный путь ниже, там ничего не зарезервировано.

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


def _settle_against_reservation(usage_row, user, overage: int, reserved_kopecks: int, reserve_ref: str) -> int:
    """
    Нетто-зачёт факта (overage) против уже зарезервированной суммы
    (reserved_kopecks, прочитана из ledger вызывающей стороной — settle_overage).

    completion_tokens физически не может превысить max_tokens, под который
    считался резерв, поэтому overage > reserved_kopecks возможен только из-за
    ошибки ОЦЕНКИ prompt_tokens на preflight (estimate_prompt_tokens — эвристика,
    не токенизатор) — узкий, редкий случай, в отличие от legacy-пути, где ВСЯ
    сумма всегда собиралась заново и могла целиком провалиться на гонке.

    add_kopecks (возврат неиспользованного) и spend_kopecks (досписание
    перерасхода) оба идемпотентны по (type, reference) — безопасны при
    повторном вызове реконсилером (crash между списанием и записью строки).
    """
    from django.db import transaction
    from django.utils import timezone
    from aitext.models import MessageTokenUsage
    from users.models import BalanceTransaction, UserSpending

    diff = overage - reserved_kopecks
    refund_ref = f'{reserve_ref}:refund'
    extra_ref = f'{reserve_ref}:extra'

    if diff < 0:
        # Возврат неиспользованного резерва — add_kopecks не может провалиться
        # на нехватке средств (это пополнение), идемпотентен при повторе.
        user.add_kopecks(-diff, type='refund', reference=refund_ref)
    elif diff > 0:
        if not user.spend_kopecks(diff, type=BalanceTransaction.Type.OVERAGE, reference=extra_ref):
            logger.error(
                f"[overage] overage:{usage_row.message_id}: резерв {reserved_kopecks} коп. собран, "
                f"перерасход сверх резерва {diff} коп. не списан (баланс {user.balance_kopecks} коп., "
                f"user={user.id}) — settled_at остаётся пустым, подберёт reconcile_unsettled_overage."
            )
            return 0

    with transaction.atomic():
        marked = MessageTokenUsage.objects.filter(
            pk=usage_row.pk, settled_at__isnull=True,
        ).update(settled_kopecks=overage, settled_at=timezone.now())
        if marked and diff > 0:
            UserSpending.objects.create(
                user=user, amount=diff // 100, amount_kopecks=diff,
                description=f"Доплата сверх резерва за длинный ответ, {usage_row.model_name}",
            )

    if not marked:
        # Row уже отмечена другим одновременным вызовом (инлайн + реконсилер) —
        # money movement выше идемпотентен по reference, повторной порчи нет,
        # но списанное в ЭТОМ вызове засчитывать не себе, а тому, кто выиграл.
        return 0

    usage_row.refresh_from_db(fields=['settled_kopecks', 'settled_at'])
    logger.info(f"[overage] overage:{usage_row.message_id}: зачтено против резерва "
                f"({reserved_kopecks} коп. резерв, {overage} коп. факт, {usage_row.model_name})")
    return overage


# Ниже этого значения ответ уже бессмысленно обрезать — клэмп не опускается
# дальше, даже если пользователь не может оплатить и столько. Остаточный риск
# нехватки на settle покрывает реконсилер (§3.3, вариант C + B как страховка).
PREFLIGHT_MIN_MAX_TOKENS = 1024


def outstanding_overage_kopecks(usage_row) -> int:
    """
    2026-09-28 (ревью, раунд 3): для мониторингового алерта
    (aitext.tasks.reconcile_unsettled_overage) — сколько РЕАЛЬНО ещё не собрано.
    Без резерва это просто overage_kopecks (как раньше). С резервом бОльшая
    часть уже реально списана атомарным reserve_overage_tokens ДО генерации —
    алерт "не списано X ₽" был бы вводящим в заблуждение, если реально
    осталось собрать только небольшой перерасход сверх резерва."""
    overage = int(getattr(usage_row, 'overage_kopecks', 0) or 0)
    try:
        reserve_ref = (usage_row.message.settings or {}).get('overage_reserve_reference')
    except Exception:
        reserve_ref = None
    if not reserve_ref:
        return overage
    from users.models import BalanceTransaction
    txn = BalanceTransaction.objects.filter(
        user=usage_row.message.chat.user, type=BalanceTransaction.Type.OVERAGE, reference=reserve_ref,
    ).first()
    reserved = abs(int(txn.amount_kopecks or 0)) if txn else 0
    return max(0, overage - reserved)


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
    aitext.memory.estimate_tokens, без tiktoken.

    2026-09-28 (ревью, раунд 3): части content без ключа 'text' (вложения —
    image_url/image/input_image) раньше вносили 0 в оценку — пробный
    пользователь мог приложить картинку с минимумом текста, guard считал
    промт «дешёвым», а реальный usage от провайдера оказывался в разы больше
    (тот же класс инцидента, что и исходный 50887-токенный случай, новым
    вектором обхода). Фиксированная оценка за картинку — тот же приём, что
    уже есть в api/services/billing.py::estimate_messages_tokens (dev-API)."""
    from aitext.memory import estimate_tokens
    total = 0
    for m in messages_for_api or []:
        content = m.get('content') if isinstance(m, dict) else None
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                if isinstance(part.get('text'), str):
                    total += estimate_tokens(part['text'])
                elif part.get('type') in ('image_url', 'image', 'input_image'):
                    total += 2000  # картинка: фиксированная оценка (как в dev-API)
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
        if not model_pricing.overage_eligible(model_name, allowlist):
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


def _worst_case_overage_kopecks(network, prompt_tokens, out_tokens, flat_kopecks) -> int:
    """
    2026-09-28 (ревью, раунд 3, TOKEN_OVERAGE_RESERVE_ENABLED): формула worst-case
    overage для АТОМАРНОГО резерва — зеркалит compute_overage() 1:1 (wholesale-
    ставки через model_pricing.cost_kopecks, тот же markup/threshold/cap), а не
    retail-прокси free_tier_guard.estimated_cost_kopecks — резерв обязан совпадать
    с тем, что реально спишет settle_overage() после генерации, иначе резерв
    систематически недооценивает/переоценивает реальную доплату.

    Возвращает 0 (нечего резервировать), если модель не аудирована
    (wholesale_rates отсутствуют) — вызывающая сторона обязана убедиться, что
    overage_eligible(model) True ДО вызова (иначе settle_overage всё равно
    вернёт overage=0 и резерв был бы зря заморожен на балансе пользователя).
    """
    from django.conf import settings as dj_settings
    from core import model_pricing

    cost = model_pricing.cost_kopecks(network.model_name, prompt_tokens, out_tokens)
    if cost is None:
        return 0
    flat = int(flat_kopecks or 0)
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
    return max(0, int(overage))


def reserve_overage_tokens(user, network, prompt_tokens, max_tokens, flat_kopecks, message_id):
    """
    Атомарно резервирует worst-case доплату под max_tokens (тот, что уже прошёл
    advisory-клэмп — free_tier_guard/preflight_max_tokens выше). Закрывает гонку
    параллельных сообщений: раньше оба независимо ЧИТАЛИ один и тот же остаток
    баланса и оба разрешали полноразмерный ответ; теперь второе сообщение
    реально не сможет зарезервировать то же самое (spend_kopecks атомарен).

    При недостатке средств сужает max_tokens (геометрически к PREFLIGHT_MIN_MAX_TOKENS)
    и пробует снова — каждая неудачная попытка не создаёт ledger-записи
    (spend_kopecks с недостатком средств — чистый no-op), поэтому ретраи безопасны.

    Возвращает (max_tokens_used, reserved_kopecks, reference, ok):
    - ok=True — можно продолжать с max_tokens_used как есть. reserved_kopecks==0
      и reference is None при этом означают, что резервировать было нечего
      (overage ниже порога даже при max_tokens_used) — НЕ ошибка.
    - ok=False — не хватило средств даже на floor (гонка параллельных запросов
      исчерпала баланс между advisory-клэмпом и этим вызовом). max_tokens_used
      в этом случае — floor; вызывающая сторона решает: для пробных — 'block',
      для платящих — fail-open на floor без резерва (как было до этой защиты).
    - reference — реальная ledger-запись (type=OVERAGE, f'overage-reserve:{id}'),
      её обязана сохранить вызывающая сторона в message.settings
      ('overage_reserve_reference'), чтобы settle_overage() мог её найти и
      netto-зачесть, и её обязан освободить refund_message_billing() при
      финальном провале генерации (иначе резерв "зависнет" списанным без
      возврата).
    """
    from users.models import BalanceTransaction

    max_tokens = max(1, int(max_tokens or 0))
    floor = min(max_tokens, PREFLIGHT_MIN_MAX_TOKENS)
    reference = f'overage-reserve:{message_id}'

    candidate = max_tokens
    for _ in range(8):
        amount = _worst_case_overage_kopecks(network, prompt_tokens, candidate, flat_kopecks)
        if amount <= 0:
            return candidate, 0, None, True
        if user.spend_kopecks(amount, type=BalanceTransaction.Type.OVERAGE, reference=reference):
            if candidate < max_tokens:
                logger.info(f"[overage][reserve] {network.model_name}: max_tokens {max_tokens} -> "
                            f"{candidate}, зарезервировано {amount} коп. ({reference})")
            return candidate, amount, reference, True
        if candidate <= floor:
            logger.warning(f"[overage][reserve] {network.model_name}: резерв не удался даже на floor "
                            f"({floor} токенов, {message_id}) — гонка параллельных запросов")
            return floor, 0, None, False
        candidate = max(floor, int(candidate * 0.75))
    return floor, 0, None, False


def release_overage_reservation(user, reference: str) -> bool:
    """Освобождает резерв (полный возврат) при финальном провале генерации —
    сообщение так и не было отправлено апстриму/не досчиталось, оставлять
    деньги замороженными нельзя. Идемпотентно: add_kopecks с тем же reference
    (type=refund) — повтор no-op по unique(type, reference). Сумма читается из
    ledger (BalanceTransaction), а не из message.settings — на случай крэша
    Celery между spend_kopecks резерва и записью settings (settings могли бы
    хранить неверную/устаревшую сумму, ledger — источник истины)."""
    if not reference:
        return False
    from users.models import BalanceTransaction

    txn = BalanceTransaction.objects.filter(
        user=user, type=BalanceTransaction.Type.OVERAGE, reference=reference,
    ).first()
    if txn is None:
        return False
    reserved = abs(int(txn.amount_kopecks or 0))
    if reserved <= 0:
        return False
    return user.add_kopecks(reserved, type='refund', reference=f'{reference}:release')


def free_tier_guard(user, network, prompt_tokens, max_tokens, flat_kopecks, balance_before_flat):
    """
    STATUS_AND_BACKLOG_PLAN_2026-09-25.md / инцидент 2026-09-27 (claude-opus-5,
    50887 prompt-токенов на пробном балансе 10 руб.): overage сам по себе не
    защищает от ОГРОМНОГО ВХОДНОГО промта — доплата считается только с выхода,
    входные токены уже «съедены» к моменту расчёта. preflight_max_tokens выше
    не помогает бесплатным пользователям: он сужает max_tokens, но минимальный
    пол PREFLIGHT_MIN_MAX_TOKENS(1024) всё равно генерируется и биллится, даже
    если это исчерпывает и обнуляет весь пробный баланс за один ответ (settle
    после этого просто не может списать доплату и уходит в реконсилер).

    Отдельный, более строгий guard ТОЛЬКО для пробных пользователей (никогда не
    плативших реально, см. CustomUser.is_unpaid_free_user): либо отвечать
    полностью в рамках баланса (клэмп, видимый пользователю — вызывающая
    сторона обязана показать уведомление), либо отказать ДО обращения к
    апстриму, если СРАЗУ ЖЕ, включая пол в 1024 токена, не хватает денег на
    весь запрос (не только на довесок после плоского списания, как в
    preflight_max_tokens, — pull запроса за счёт входного промта уже посчитан).

    Возвращает (action, adjusted_max_tokens, estimated_kopecks):
    - 'ok'    — обычная логика (в т.ч. preflight_max_tokens) не менять;
    - 'clamp' — сузить max_tokens, вызывающая сторона обязана уведомить
      пользователя (settings['balance_clamp'] / отдельное сообщение в боте);
    - 'block' — отказать ДО вызова апстрима, ничего не списывать/вернуть
      уже списанное, показать понятную причину с предложением пополнить баланс.

    balance_before_flat — баланс пользователя ДО плоского списания за это
    сообщение (для пробного пользователя бюджет на весь запрос — это весь его
    остаток, а не «остаток после списания», как для платящих в preflight_max_tokens:
    именно плоское списание с пробного баланса и есть то, что мы защищаем).
    Работает и для аудированных моделей, и (через estimated_cost_kopecks) для
    любой модели без ставок — в отличие от preflight_max_tokens, allowlist не
    нужен: розничная cost_kopecks известна всегда.
    """
    from django.conf import settings as dj_settings
    from core import model_pricing

    try:
        if not getattr(dj_settings, 'FREE_TIER_GUARD_ENABLED', False):
            return 'ok', int(max_tokens or 0), 0
        if user is None or not getattr(user, 'is_unpaid_free_user', lambda: False)():
            return 'ok', int(max_tokens or 0), 0

        max_tokens = int(max_tokens or 0)
        if max_tokens <= 0:
            return 'ok', max_tokens, 0
        prompt_tokens = max(0, int(prompt_tokens or 0))
        flat = int(flat_kopecks or 0)
        balance = max(0, int(balance_before_flat or 0))
        markup = float(getattr(dj_settings, 'TOKEN_OVERAGE_MARKUP', 1.6))
        floor_tokens = min(max_tokens, PREFLIGHT_MIN_MAX_TOKENS)

        # 2026-09-28 (ревью): эта функция раньше считала target = cost*markup
        # напрямую как "сколько реально спишется", игнорируя cap/threshold из
        # compute_overage/preflight_max_tokens. Из-за этого реально списываемая
        # сумма (flat + overage, где overage ограничен TOKEN_OVERAGE_CAP_MULTIPLE/
        # TOKEN_OVERAGE_ABS_CAP_KOPECKS) МЕНЬШЕ, чем здесь считалось — честного
        # пробного пользователя, чей реальный overage упёрся бы в потолок, могли
        # пережать (ложный clamp/block), хотя денег хватало. Формула ниже
        # зеркалит compute_overage() 1:1.
        min_fraction = float(getattr(dj_settings, 'TOKEN_OVERAGE_MIN_FRACTION', 0.25))
        min_kopecks = int(getattr(dj_settings, 'TOKEN_OVERAGE_MIN_KOPECKS', 100))
        cap_multiple = float(getattr(dj_settings, 'TOKEN_OVERAGE_CAP_MULTIPLE', 2.0))
        abs_cap = int(getattr(dj_settings, 'TOKEN_OVERAGE_ABS_CAP_KOPECKS', 4000))
        cap = max(flat * cap_multiple, abs_cap)
        threshold = max(min_kopecks, flat * min_fraction)

        def total_cost(out_tokens):
            est = model_pricing.estimated_cost_kopecks(network, prompt_tokens, out_tokens)
            target = round(est * markup)
            overage_raw = target - flat
            overage = overage_raw if overage_raw >= threshold else 0
            overage = min(overage, cap) if overage > 0 else 0
            # 2026-09-28 (ревью, раунд 2): compute_overage() всегда возвращает
            # max(0, int(overage)) — здесь этого не было. При нецелом
            # TOKEN_OVERAGE_CAP_MULTIPLE (например 2.2) `flat * cap_multiple`
            # даёт float с погрешностью (3000*2.2 == 6600.000000000001), и если
            # overage упирается в потолок, total_cost() возвращал на долю
            # копейки больше реальной списываемой суммы — на границе баланса
            # это могло дать ложный 'block'/более жёсткий 'clamp', чем реально
            # нужно. int()/max(0, ...) зеркалит compute_overage() до конца.
            return flat + max(0, int(overage))

        floor_total = total_cost(floor_tokens)
        if floor_total > balance:
            return 'block', 0, floor_total

        if total_cost(max_tokens) <= balance:
            return 'ok', max_tokens, 0

        # Бинарный поиск наибольшего o с total_cost(o) <= balance: estimated_cost_kopecks
        # не всегда линейна по токенам (у неаудированных моделей — retail-прокси через
        # max(p/6000, o/1500)), но монотонна по o — обратная формула не нужна.
        lo, hi = floor_tokens, max_tokens
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if total_cost(mid) <= balance:
                lo = mid
            else:
                hi = mid - 1
        clamped_cost = total_cost(lo)
        logger.info(f"[free_tier_guard] {getattr(network, 'model_name', '?')}: max_tokens "
                    f"{max_tokens} -> {lo} (пробный баланс {balance} коп.)")
        return 'clamp', lo, clamped_cost
    except Exception as e:
        logger.warning(f"[free_tier_guard] guard не применён: {e}")
        return 'ok', int(max_tokens or 0), 0


def resolve_overage_guard(user, network, prompt_tokens, max_tokens, flat_kopecks,
                           head_kopecks, balance_before_flat, message_id, is_trial):
    """
    2026-09-28 (ревью, раунд 3): единая точка входа, объединяющая free_tier_guard
    (Rule D для пробных) и защиту от overage (preflight-клэмп либо атомарный
    резерв, TOKEN_OVERAGE_RESERVE_ENABLED) — раньше эта логика была продублирована
    почти дословно в api/views/chats.py и aitext/tasks.py (источник 2 из 3 багов
    раунда 2: `elif` вместо `if action=='ok'` в одном месте почти не тронуло
    второе). Оба вызывающих места теперь зовут ЭТУ функцию один раз.

    head_kopecks — баланс ПОСЛЕ планового списания flat (для legacy
    preflight_max_tokens); balance_before_flat — баланс ДО (для free_tier_guard,
    актуально только при is_trial=True).

    Возвращает namedtuple(action, max_tokens, estimated_kopecks, reserve_reference):
    - action: 'ok' | 'clamp' | 'block'
    - max_tokens: итоговый лимит ответа (может остаться неизменным)
    - estimated_kopecks: для 'block' — сумма в тексте отказа; иначе 0
    - reserve_reference: не None только при реальном атомарном резерве —
      вызывающая сторона ОБЯЗАНА сохранить его в message.settings
      ('overage_reserve_reference') и прокинуть до refund_message_billing()
      на случай финального провала генерации (releases the reservation).
    """
    from collections import namedtuple
    from django.conf import settings as dj_settings
    from core import model_pricing

    Result = namedtuple('OverageGuardResult', ['action', 'max_tokens', 'estimated_kopecks', 'reserve_reference'])

    candidate = max(1, int(max_tokens or 0))
    action = 'ok'
    estimated = 0

    if is_trial:
        action, guarded_tokens, est = free_tier_guard(
            user, network, prompt_tokens, candidate, flat_kopecks, balance_before_flat,
        )
        if action == 'block':
            return Result('block', 0, est, None)
        if action == 'clamp':
            candidate = guarded_tokens
            estimated = est

    allowlist = getattr(dj_settings, 'TOKEN_OVERAGE_MODELS', [])
    eligible = overage_settle_active() and model_pricing.overage_eligible(network.model_name, allowlist)
    if not eligible:
        # Модель не участвует в overage (не аудирована/не в allowlist/фича
        # выключена) — решение free_tier_guard выше (если было) остаётся
        # финальным, дальше ничего резервировать/клэмпить не требуется.
        return Result(action, candidate, estimated, None)

    if not getattr(dj_settings, 'TOKEN_OVERAGE_RESERVE_ENABLED', False):
        # Legacy: чистый advisory-клэмп без атомарного резерва (прежнее
        # поведение до этой защиты — безопасный откат при выключенном флаге).
        requested = candidate
        candidate = preflight_max_tokens(
            network.model_name, candidate, prompt_tokens=prompt_tokens,
            flat_kopecks=flat_kopecks, head_kopecks=head_kopecks,
        )
        if candidate < requested:
            action = 'clamp'
        return Result(action, candidate, estimated, None)

    # Резерв: advisory-клэмп (preflight_max_tokens, один SELECT) как дешёвая
    # отправная точка, затем один атомарный spend_kopecks на этом кандидате
    # (reserve_overage_tokens сама сужает и повторяет при неудаче).
    requested = candidate
    advisory = preflight_max_tokens(
        network.model_name, candidate, prompt_tokens=prompt_tokens,
        flat_kopecks=flat_kopecks, head_kopecks=head_kopecks,
    )
    new_tokens, reserved, ref, ok = reserve_overage_tokens(
        user, network, prompt_tokens, advisory, flat_kopecks, message_id,
    )
    if not ok:
        # Не хватило средств даже на floor — гонка параллельных сообщений
        # исчерпала баланс между advisory-клэмпом и атомарным резервом.
        if is_trial:
            floor_est = _worst_case_overage_kopecks(network, prompt_tokens, new_tokens, flat_kopecks)
            return Result('block', 0, int(flat_kopecks or 0) + floor_est, None)
        # Платящие никогда не блокируются overage-защитой — fail-open на floor
        # без резерва (тот же риск недосбора доплаты, что был ДО этой защиты,
        # но теперь только в этом узком, редком случае, а не при каждом
        # параллельном сообщении).
        return Result('clamp' if new_tokens < requested else action, new_tokens, estimated, None)

    final_action = 'clamp' if new_tokens < requested else action
    return Result(final_action, new_tokens, reserved, ref)


def trial_block_message(network, lang='ru') -> str:
    """Rule S: текст 402, когда модель вообще не предлагается пробному пользователю
    (её флоат-цена уже не оставляет запаса на несколько сообщений, см.
    core.model_pricing.is_model_blocked_for_trial)."""
    from core.errors_i18n import t_error
    name = getattr(network, 'name', None) or getattr(network, 'model_name', '') or '?'
    return t_error('trial_model_locked', lang).format(model=name)


def trial_too_large_message(network, required_kopecks, balance_kopecks, lang='ru') -> str:
    """Rule D (block): текст 402, когда даже минимальный ответ не влезает в остаток
    пробного баланса — запрос отклонён ДО обращения к апстриму."""
    from core.errors_i18n import t_error
    from core.money import format_rub
    name = getattr(network, 'name', None) or getattr(network, 'model_name', '') or '?'
    return t_error('trial_request_too_large', lang).format(
        model=name, amount=format_rub(required_kopecks), have=format_rub(balance_kopecks),
    )


def trial_truncated_message(lang='ru') -> str:
    """Rule D (clamp): текст уведомления, когда ответ сужен под пробный баланс."""
    from core.errors_i18n import t_error
    return t_error('trial_reply_truncated', lang)


def balance_truncated_message(is_trial: bool, lang='ru') -> str:
    """Единая точка текста уведомления об урезанном ответе — для пробных
    пользователей (Rule D, free_tier_guard) и для ПЛАТЯЩИХ (обычный
    preflight_max_tokens: доплата за длинный ответ превысила бы остаток
    баланса). Раньше клэмп для платящих был полностью тихим — пользователь
    получал короткий ответ без единого слова о причине."""
    from core.errors_i18n import t_error
    return t_error('trial_reply_truncated' if is_trial else 'balance_reply_truncated', lang)


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
