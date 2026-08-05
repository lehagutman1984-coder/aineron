"""
Отчёт по себестоимости/доплате за токены (TOKEN_OVERAGE_BILLING_PLAN.md,
Спринт 2, задача 4) — по каждой аудированной модели: сколько сообщений,
сколько получили бы overage, суммарная себестоимость vs выручка, маржа.

НИЧЕГО не списывает — читает уже посчитанные MessageTokenUsage.cost_kopecks/
overage_kopecks (записаны token_metering.apply_overage при TOKEN_METERING_ENABLED=1).
Это артефакт, по которому основатель принимает решение — включать
TOKEN_OVERAGE_ENABLED (Спринт 3) или калибровать параметры дальше.

Запуск: docker-compose exec web python manage.py overage_report --days 7
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum, Avg, Max, Q
from django.utils import timezone


class Command(BaseCommand):
    help = "Отчёт по реальной себестоимости и расчётной доплате за токены"

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7, help='Период в днях (по умолчанию 7)')

    def handle(self, *args, **options):
        from aitext.models import MessageTokenUsage

        days = options['days']
        since = timezone.now() - timezone.timedelta(days=days)
        qs = MessageTokenUsage.objects.filter(created_at__gte=since, source=MessageTokenUsage.Source.PROVIDER)

        total = qs.count()
        self.stdout.write(f"\nОтчёт за последние {days} дн. — всего размеченных сообщений: {total}\n" + "=" * 100)
        if total == 0:
            self.stdout.write(self.style.WARNING(
                "Нет данных. Проверь TOKEN_METERING_ENABLED=1 и что прошло достаточно времени."
            ))
            return

        by_model = (
            qs.values('model_name')
            .annotate(
                messages=Count('id'),
                billable=Count('id', filter=Q(flat_was_charged=True)),
                with_overage=Count('id', filter=Q(overage_kopecks__gt=0)),
                total_cost=Sum('cost_kopecks'),
                total_flat=Sum('flat_kopecks'),
                total_overage=Sum('overage_kopecks'),
                avg_overage=Avg('overage_kopecks', filter=Q(overage_kopecks__gt=0)),
                max_overage=Max('overage_kopecks'),
            )
            .order_by('-total_overage')
        )

        header = f"{'Модель':<20} {'Сообщ.':>8} {'С overage':>10} {'%':>6} {'Σ overage':>12} {'ср.':>8} {'макс.':>8} {'Σ себест.':>12} {'Σ выручка':>12} {'маржа':>8}"
        self.stdout.write(header)
        self.stdout.write('-' * len(header))

        for row in by_model:
            messages = row['messages']
            billable = row['billable'] or 0
            with_overage = row['with_overage'] or 0
            pct = (with_overage / billable * 100) if billable else 0
            total_cost = row['total_cost'] or 0
            total_flat = row['total_flat'] or 0
            total_overage = row['total_overage'] or 0
            revenue = total_flat + total_overage
            margin = (revenue / total_cost) if total_cost else 0
            avg_overage = row['avg_overage'] or 0
            max_overage = row['max_overage'] or 0

            self.stdout.write(
                f"{row['model_name']:<20} {messages:>8} {with_overage:>10} {pct:>5.1f}% "
                f"{total_overage / 100:>10.2f}₽ {avg_overage / 100:>6.2f}₽ {max_overage / 100:>6.2f}₽ "
                f"{total_cost / 100:>10.2f}₽ {revenue / 100:>10.2f}₽ {margin:>6.2f}×"
            )

        self.stdout.write('=' * len(header))
        self.stdout.write(
            "\nЦелевой ориентир (§2.5 плана): доля сообщений с overage не более 2-5% "
            "на аудированных моделях. Если больше — плоская цена занижена сильнее, чем "
            "рассчитывали, стоит поднять её, а не полагаться на overage как основной "
            "источник маржи."
        )
