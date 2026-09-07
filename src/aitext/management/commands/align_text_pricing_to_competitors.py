"""
Выравнивает базовую цену 6 текстовых моделей (7 записей — Fable 5 и 5.1
считаются одной строкой в исходном отчёте) так, чтобы она была РОВНО на 5%
дешевле самого дешёвого из двух живых конкурентов (RouterAI, routerai.ru;
Gen-API, собственный прайс-лист) — по прямому запросу пользователя,
2026-09-07. Тот же принцип, что и align_image_pricing_to_competitors /
align_video_pricing_to_competitors.

Это ТОЧЕЧНАЯ команда — только 6 моделей, отмеченных как ценовые аномалии
(отклонение больше ±15% от конкурента) в полном аудите всех 22 текстовых
моделей (PRICING_VS_COMPETITORS_2026-09-07.html). Остальные 16 моделей
сидят в разумных -6..-7% от конкурента (ожидаемо: K=105 у нас vs K≈112
у RouterAI) и НЕ трогаются.

Единица сравнения: "цена типичного сообщения" по стандартному профилю
токенов из PRICING_SIMPLIFICATION_PLAN.md §3 (6000 вход + 1500 выход,
тот же профиль, что уже применён для текущих cost_kopecks 2026-09-02/03,
см. журнал §9.3) — единственный способ честно сравнить наш флэт-биллинг
за сообщение с токенным биллингом конкурентов.

Цены конкурентов сняты живьём 2026-09-07, ДВАЖДЫ независимо перепроверены
(6 параллельных агентов round 1 + 6 round 2, 0 расхождений), и ЕЩЁ РАЗ
перепроверены точечно по прямому запросу пользователя (включая сверку со
скриншотом routerai.ru/models/openai/gpt-6-astra — цифры совпали 1:1).
Gen-API — собственный текстовый дамп прайс-листа (genapi.txt), снят
2026-09-05, не пересбирался в этом заходе.

Направление меняется в обе стороны (не только "не поднимать") — 4 модели
дорожают (были переоценены против конкурента), 2 дешевеют одинаково
(Fable 5 и 5.1 были недооценены на 19%):
  gpt-6-astra         32.07₽ -> 14.43₽  (-55%) — RouterAI 1125/5628 ₽/1M (нет данных Gen-API)
  deepseek-v4-pro      1.10₽ ->  0.71₽  (-35%) — Gen-API 70/217.5 ₽/1M дешевле RouterAI 189/189
  qwen3-6-max          2.20₽ ->  1.64₽  (-25%) — RouterAI 115/693 ₽/1M (нет данных Gen-API)
  deepseek-v4-flash    0.10₽ ->  0.08₽  (-20%) — RouterAI 8/21 ₽/1M дешевле Gen-API 35/108.75
  claude-fable-5      14.18₽ -> 16.60₽  (+17%) — RouterAI 1294/6472 ₽/1M дешевле Gen-API 2500/12500
  claude-fable-5-1    14.18₽ -> 16.60₽  (+17%) — то же самое соотношение
  gpt-5-5-pro         16.00₽ -> 57.74₽ (+261%) — RouterAI 4052/24313 ₽/1M дешевле Gen-API 7500/45000,
                                                  модель была сильно недооценена относительно рынка

extra_cost за настройки не пересчитывается этой командой — у текстовых
моделей их и так нет (см. PRICING_VS_COMPETITORS_2026-09-07.html).

Запуск: docker-compose exec web python manage.py align_text_pricing_to_competitors
        docker-compose exec web python manage.py align_text_pricing_to_competitors --dry-run
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork

# slug -> new cost_kopecks (= min(router_msg, genapi_msg) × 0.95 × 100,
# профиль 6000 вход/1500 выход)
PRICING = {
    'gpt-6-astra': 1443,          # 14.43₽ (было 32.07₽) — RouterAI 1125/5628 ₽/1M
    'deepseek-v4-pro': 71,        # 0.71₽ (было 1.10₽) — Gen-API 70/217.5 ₽/1M
    'qwen3-6-max': 164,           # 1.64₽ (было 2.20₽) — RouterAI 115/693 ₽/1M
    'deepseek-v4-flash': 8,       # 0.08₽ (было 0.10₽) — RouterAI 8/21 ₽/1M
    'claude-fable-5': 1660,       # 16.60₽ (было 14.18₽) — RouterAI 1294/6472 ₽/1M
    'claude-fable-5-1': 1660,     # 16.60₽ (было 14.18₽) — RouterAI 1294/6472 ₽/1M
    'gpt-5-5-pro': 5774,          # 57.74₽ (было 16.00₽) — RouterAI 4052/24313 ₽/1M
}


class Command(BaseCommand):
    help = "Выравнивает базовую цену 6 аномальных текстовых моделей на конкурент×0.95 (см. docstring файла)"

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
