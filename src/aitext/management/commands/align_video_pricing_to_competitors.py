"""
Выравнивает базовую (без учёта extra_cost за настройки) цену видео-моделей
так, чтобы она была РОВНО на 5% дешевле самого дешёвого из двух живых
конкурентов (RouterAI, routerai.ru; Gen-API, собственный прайс-лист) —
по прямому запросу пользователя, 2026-09-05. Это не «не поднимать цену
никогда» (как в более раннем правиле §9.3 плана) — цена по этой команде
может как понизиться, так и вырасти (у 19 из 24 моделей выросла, иногда
в 2-3 раза — наш опт по Apimart/CometAPI оказался настолько дешевле
конкурентов, что K=105 от опта давал цену значительно НИЖЕ, чем
«конкурент минус 5%»).

Модели без опубликованной цены ни у одного из двух конкурентов НЕ трогаются
(остаются на прежней, опт×105 базе) — сравнивать не с чем: veo-3, veo-3-fast
(эксклюзив CometAPI), kling-v3-omni, kling-3-0-turbo, hailuo-2-3-fast,
vidu-q3-pro.

Конкурентные цены (₽/сек, самая низкая опубликованная) сняты живьём:
RouterAI — routerai.ru/models?output_modalities[]=video (28 моделей, 2
страницы), Gen-API — собственный текстовый дамп прайс-листа. Обе даты снятия
— 2026-09-05. См. артефакт сравнения (scratch_video_vs_competitors.html)
для полной таблицы по каждой модели.

extra_cost по настройкам (resolution/duration/audio) НЕ пересчитывается
этой командой — только базовая cost_kopecks. Доплаты остаются в прежних
абсолютных величинах, откалиброванных по реальному опту в предыдущем заходе.

Запуск: docker-compose exec web python manage.py align_video_pricing_to_competitors
        docker-compose exec web python manage.py align_video_pricing_to_competitors --dry-run
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork

# slug -> new cost_kopecks (= min(router, genapi) ₽/сек × 0.95 × реальная_длительность × 100)
PRICING = {
    'veo-3-1': 34200,               # 342.00₽ (было 105.00₽) — конкурент RouterAI 45₽/сек
    'veo-3-1-fast': 8360,           # 83.60₽ (было 14.70₽) — RouterAI 11₽/сек
    'veo-3-1-lite': 4279,           # 42.79₽ (было 7.35₽) — RouterAI 5.63₽/сек
    'kling-v26': 8313,              # 83.13₽ (было 19.32₽) — Gen-API 17.5₽/сек (нет данных RouterAI)
    'kling-v3': 6650,               # 66.50₽ (было 35.28₽) — RouterAI 14₽/сек
    'kling-video-o1': 5700,         # 57.00₽ (было 35.28₽) — RouterAI 12₽/сек
    'kling-v3-motion-control': 8313,  # 83.13₽ (было 54.01₽) — Gen-API 17.5₽/сек (аналог v2.6, нет данных RouterAI)
    'hailuo-2-3': 5130,             # 51.30₽ (было 30.74₽) — RouterAI 9₽/сек
    'pixverse-v6': 2969,            # 29.69₽ (было 12.60₽) — Gen-API 6.25₽/сек (нет данных RouterAI)
    'wan-2-6': 2138,                # 21.38₽ (было 26.25₽) — RouterAI 4.50₽/сек — ЕДИНСТВЕННОЕ снижение
    'wan-2-7': 5225,                # 52.25₽ (было 34.86₽) — RouterAI 11₽/сек
    'seedance-1-5-pro': 2774,       # 27.74₽ (было 23.10₽) — RouterAI 5.84₽/сек
    'seedance-2-0': 7600,           # 76.00₽ (было 74.55₽) — Gen-API 16₽/сек
    'seedance-2-0-fast': 4750,      # 47.50₽ (было 44.94₽) — RouterAI 10₽/сек
    'seedance-2-5': 12350,          # 123.50₽ (было 50.44₽) — RouterAI 26₽/сек
    'vidu-q3': 8313,                # 83.13₽ (было 29.40₽) — Gen-API 17.5₽/сек (нет данных RouterAI)
    'vidu-q3-turbo': 4156,          # 41.56₽ (было 32.34₽) — Gen-API 8.75₽/сек (нет данных RouterAI)
    'grok-imagine-1-5': 5130,       # 51.30₽ (было 6.43₽) — RouterAI 9₽/сек
}


class Command(BaseCommand):
    help = "Выравнивает базовую цену видео-моделей на конкурент×0.95 (см. docstring файла)"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Только показать изменения, не сохранять')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        for slug, new_cost in PRICING.items():
            network = NeuralNetwork.objects.filter(slug=slug).first()
            if not network:
                self.stdout.write(self.style.WARNING(f'{slug}: не найдена в БД, пропуск'))
                continue
            old_cost = network.cost_kopecks
            direction = 'ПОДНЯТА' if new_cost > old_cost else ('снижена' if new_cost < old_cost else 'без изменений')
            self.stdout.write(
                f'{slug}: cost_kopecks {old_cost} -> {new_cost} '
                f'({old_cost/100:.2f}₽ -> {new_cost/100:.2f}₽, {direction})'
            )
            if not dry_run:
                network.cost_kopecks = new_cost
                network.save(update_fields=['cost_kopecks'])

        if dry_run:
            self.stdout.write(self.style.WARNING('\n--dry-run: изменения НЕ сохранены'))
        else:
            self.stdout.write(self.style.SUCCESS('\nГотово, сохранено в БД'))
