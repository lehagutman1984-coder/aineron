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
