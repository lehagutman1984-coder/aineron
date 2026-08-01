"""
Массовая генерация промокодов на баланс — для раздачи через Plati.market/
Digiseller, посевы в Telegram-каналах и т.п. (см. GROWTH_PLAN_RU.md §4).

До этой команды пул кодов приходилось создавать вручную в админке —
десятки-сотни кликов на партию. Каждый код по умолчанию одноразовый
(usage_limit=1), чтобы не открывать дыру для мультиаккаунтов при раздаче
через каналы без собственной защиты от повторного использования.

Пример:
    python manage.py generate_promo_codes --count 100 --amount 50 \\
        --prefix PLATI --valid-days 90
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from users.models import PromoCode
from users.promo import generate_unique_promo_code


class Command(BaseCommand):
    help = 'Массово создаёт промокоды на баланс (для Plati/каналов/партнёров)'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, required=True, help='Сколько кодов создать')
        parser.add_argument('--amount', type=int, required=True, help='Начисление на баланс, ₽ (safe: 30-50 массово, до 150 адресно — см. TARIFFS.md §5)')
        parser.add_argument('--prefix', type=str, default='', help='Префикс кода, например PLATI или TG')
        parser.add_argument('--usage-limit', type=int, default=1, help='Лимит использований на код (по умолчанию 1 — защита от мультиаккаунтов)')
        parser.add_argument('--valid-days', type=int, default=None, help='Срок действия в днях от текущей даты (по умолчанию бессрочно)')
        parser.add_argument('--dry-run', action='store_true', help='Показать, что будет создано, без записи в БД')

    def handle(self, *args, **options):
        count = options['count']
        amount = options['amount']
        prefix = options['prefix'].strip().upper()
        usage_limit = options['usage_limit']
        valid_days = options['valid_days']
        dry_run = options['dry_run']

        if count <= 0:
            raise CommandError('--count должен быть положительным')
        if amount <= 0:
            raise CommandError('--amount должен быть положительным')
        if amount > 150:
            self.stdout.write(self.style.WARNING(
                f'Внимание: {amount} ₽ выше адресного потолка 150 ₽ из TARIFFS.md §5 '
                '(безопасно по марже k≤1.55). Продолжаю, но проверьте расчёт.'
            ))

        expires_at = timezone.now() + timezone.timedelta(days=valid_days) if valid_days else None

        if dry_run:
            self.stdout.write(f'[dry-run] Создал бы {count} кодов по {amount} ₽, '
                               f'usage_limit={usage_limit}, expires_at={expires_at}, префикс={prefix or "(нет)"}')
            return

        codes = []
        for _ in range(count):
            code = generate_unique_promo_code(prefix)
            codes.append(PromoCode(
                code=code,
                stars=amount,
                kopecks=amount * 100,  # bulk_create обходит save(), где это считается автоматически
                usage_limit=usage_limit,
                expires_at=expires_at,
                is_active=True,
            ))
        PromoCode.objects.bulk_create(codes)

        self.stdout.write(self.style.SUCCESS(f'Создано {len(codes)} промокодов по {amount} ₽ (usage_limit={usage_limit})'))
        self.stdout.write('Первые 10 для проверки:')
        for c in codes[:10]:
            self.stdout.write(f'  {c.code}')
