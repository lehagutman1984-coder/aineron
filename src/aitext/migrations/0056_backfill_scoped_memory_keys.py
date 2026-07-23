# B12: бэкфилл content_key существующих UserMemory под новую схему скоупа.
#
# До этой миграции content_key для ЛЮБОГО факта был просто normalize_fact(content),
# без учёта project/organization, при UniqueConstraint(user, content_key) — то есть
# одинаковый по тексту факт в двух разных проектах пользователя физически не мог
# существовать двумя строками: вторая экстракция тихо перезаписывала первую и
# "перескакивала" в чужой проект. Код теперь пишет ключ с префиксом proj{id}:/
# org{id}: (aitext/memory.py::scoped_content_key) — эта миграция приводит уже
# сохранённые строки к тому же виду, чтобы новый код с ними не спорил.
#
# Идемпотентна (безопасно перезапускать) и instance-agnostic — работает одинаково
# на aineron.ru и aineron.net, ничего не предполагает про валюту/локаль/инстанс.
import logging

from django.db import IntegrityError, migrations, transaction

logger = logging.getLogger(__name__)


def _normalize_fact(text):
    import re
    t = (text or '').lower().strip()
    t = re.sub(r'[^\w\s]', '', t, flags=re.UNICODE)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:255]


def backfill_scoped_content_keys(apps, schema_editor):
    UserMemory = apps.get_model('aitext', 'UserMemory')
    qs = (
        UserMemory.objects
        .filter(content_key__gt='')
        .exclude(project__isnull=True, organization__isnull=True)
    )
    updated = 0
    skipped = 0
    for m in qs.iterator():
        if m.project_id:
            prefix = f'proj{m.project_id}:'
        elif m.organization_id:
            prefix = f'org{m.organization_id}:'
        else:
            continue  # unreachable given the exclude() above, kept for clarity

        if m.content_key.startswith(prefix):
            continue  # уже в новой схеме (org-факты уже так создавались раньше)

        # База берётся из живого content, а не из старого content_key — если эта
        # строка когда-то "выиграла" коллизию (см. описание миграции), content_key
        # мог принадлежать более позднему факту, а content уже перезаписан вместе с ним.
        base = _normalize_fact(m.content)
        if not base:
            continue
        new_key = (prefix + base)[:255]
        if new_key == m.content_key:
            continue

        m.content_key = new_key
        try:
            # Savepoint: RunPython выполняется в одной внешней транзакции (Postgres).
            # Без вложенного atomic() необработанный IntegrityError на одной строке
            # "отравляет" всю внешнюю транзакцию — следующий же запрос (даже
            # следующая порция qs.iterator()) упадёт с InFailedSqlTransaction и
            # уронит миграцию целиком вместо аккуратного skip одной строки.
            with transaction.atomic():
                m.save(update_fields=['content_key'])
            updated += 1
        except IntegrityError:
            # Теоретическая коллизия (см. описание миграции — крайне маловероятна).
            # Не блокируем весь бэкфилл из-за одной строки; она останется на старом
            # ключе и будет видна для ручного разбора в логах деплоя.
            logger.warning(
                '[memory backfill] content_key collision for UserMemory id=%s '
                '(user=%s), left unscoped: %r', m.pk, m.user_id, new_key,
            )
            skipped += 1
    if updated or skipped:
        logger.info(
            '[memory backfill] scoped content_key: %d updated, %d skipped',
            updated, skipped,
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0055_alter_usermemory_project'),
    ]

    operations = [
        migrations.RunPython(backfill_scoped_content_keys, noop_reverse),
    ]
