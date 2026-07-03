"""U2 (UNIFIED_SUPREMACY) — бэкфилл эмбеддингов резюме чатов для Total Recall.

Запуск после деплоя (батчами, безопасно повторять):
  python manage.py backfill_summary_embeddings [--limit 500]
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Эмбеддит ChatSummary без embedding (Total Recall, батчами)'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=500,
                            help='Максимум резюме за один запуск')

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            self.stdout.write(self.style.WARNING('Только PostgreSQL — пропуск.'))
            return

        from aitext.embeddings import embed_chat_summary

        with connection.cursor() as cur:
            cur.execute(
                'SELECT id FROM aitext_chatsummary '
                'WHERE embedding IS NULL '
                "AND (summary_text <> '' OR rolling_summary <> '') "
                'ORDER BY updated_at DESC LIMIT %s',
                [options['limit']],
            )
            ids = [r[0] for r in cur.fetchall()]

        if not ids:
            self.stdout.write(self.style.SUCCESS('Все резюме уже с эмбеддингами.'))
            return

        ok = fail = 0
        for sid in ids:
            if embed_chat_summary(sid):
                ok += 1
            else:
                fail += 1
        self.stdout.write(self.style.SUCCESS(
            f'Готово: {ok} эмбеддингов создано, {fail} пропущено/ошибок '
            f'(осталось — повторите команду).'
        ))
