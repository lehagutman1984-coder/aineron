"""Гигиена Roadmap H2: миграция включённых дайджестов на движок AITask.

Дайджест = встроенная AI-задача (TELEGRAM_SUPREMACY_PLAN S2). Команда
конвертирует пользователей с digest_enabled=True в AITask (ежедневно в их
digest_hour:digest_minute) и выключает старый флаг. /digest остаётся алиасом
для новых включений. Идемпотентна: пропускает уже сконвертированных.

Запуск: python manage.py migrate_digest_to_aitask [--dry-run]
"""
from django.core.management.base import BaseCommand

DIGEST_PROMPT = (
    'Сделай краткий ежедневный дайджест: 1) один интересный факт или новость '
    'об AI за последние сутки, 2) практический совет по работе с нейросетями, '
    '3) короткая мотивирующая мысль. Лаконично, 3 абзаца, на русском.'
)


class Command(BaseCommand):
    help = 'Конвертирует digest_enabled пользователей в AITask (движок S2)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Показать план без изменений')

    def handle(self, *args, **options):
        from datetime import time as dtime
        from telegram_bot.models import TelegramUser, AITask

        dry = options['dry_run']
        users = TelegramUser.objects.filter(digest_enabled=True).select_related('user')
        converted = skipped = 0

        for tu in users:
            if AITask.objects.filter(user=tu.user, title='Ежедневный AI-дайджест').exists():
                skipped += 1
                continue
            if dry:
                self.stdout.write(f'  [dry] {tu} → AITask {tu.digest_hour:02d}:{tu.digest_minute:02d}')
                converted += 1
                continue
            task = AITask(
                user=tu.user,
                title='Ежедневный AI-дайджест',
                prompt=DIGEST_PROMPT,
                schedule_type=AITask.Schedule.DAILY,
                run_time=dtime(tu.digest_hour, tu.digest_minute),
                use_web_search=True,
                created_from='bot',
            )
            task.next_run_at = task.compute_next_run()
            task.save()
            tu.digest_enabled = False
            tu.save(update_fields=['digest_enabled'])
            converted += 1
            self.stdout.write(f'  [+] {tu} → AITask #{task.pk}')

        self.stdout.write(self.style.SUCCESS(
            f'Готово: {converted} сконвертировано, {skipped} уже были.'
        ))
