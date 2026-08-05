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
