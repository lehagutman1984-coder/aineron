"""
Выравнивает цену моделей изображений так, чтобы она была РОВНО на 5%
дешевле самого дешёвого из двух живых конкурентов (RouterAI, routerai.ru;
Gen-API, собственный прайс-лист) — по прямому запросу пользователя,
2026-09-05/06. Тот же принцип, что и align_video_pricing_to_competitors:
цена может как понизиться, так и вырасти.

ВАЖНАЯ ПОПРАВКА ПЕРЕД ЭТИМ ЗАХОДОМ: в предыдущей версии сравнения
(scratch_images_vs_competitors.html) конверсия токенных моделей RouterAI
(GPT-Image-1/2) в ₽/фото использовала плоское допущение "1120 токенов на
фото для всех". Пользователь заметил скриншотом реальную страницу
RouterAI и попросил перепроверить — по факту официальные цены OpenAI за
фото сильно различаются по качеству (gpt-image-2: $0.006 low / $0.053
medium / $0.211 high), что даёт РЕАЛЬНОЕ число токенов на medium-фото:
gpt-image-2 = $0.053 / ($30/1M) = 1767 ток/фото (было грубо 1120);
gpt-image-1 = $0.042 / ($40/1M) = 1050 ток/фото (было 1120, ближе к правде).
Это меняет диагноз ("на сколько мы дороже RouterAI"), но НЕ меняет
итоговую цену ни по одной из двух моделей — в обоих случаях Gen-API
(плоская, проверенная цена, не пересчитанная из токенов) оказался ниже
исправленного RouterAI и остался определяющим конкурентом.
gpt-image-1-mini: официальной цены за фото у OpenAI найти не удалось —
конверсия по-прежнему на грубом допущении 1120 ток/фото, ПОМЕЧЕНО как
неподтверждённое в PRICING_SIMPLIFICATION_PLAN.md.

Модели без цены ни у одного конкурента НЕ трогаются: gpt-image-1-5.

extra_cost по настройкам (разрешение/качество) НЕ пересчитывается —
только базовая cost_kopecks.

Запуск: docker-compose exec web python manage.py align_image_pricing_to_competitors
        docker-compose exec web python manage.py align_image_pricing_to_competitors --dry-run
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork

# slug -> new cost_kopecks (= min(router, genapi) ₽/фото × 0.95 × 100)
PRICING = {
    'flux-2-pro': 321,               # 3.21₽ (было 3.22₽) — RouterAI 3.38₽
    'gemini-3-1-flash-image': 827,   # 8.27₽ (было 9.50₽) — RouterAI 8.71₽ (1290 ток/фото, офиц. Google)
    'gemini-3-pro-image': 1655,      # 16.55₽ (было 3.20₽, ПОДНЯТА) — RouterAI 17.42₽
    'gpt-image-1': 209,              # 2.09₽ (было 3.70₽) — Gen-API 2.20₽ (RouterAI после правки 4.73₽, но Gen-API дешевле)
    'gpt-image-1-mini': 96,          # 0.96₽ (было 1.80₽) — RouterAI 1.01₽, НЕПОДТВЕРЖДЕНО (см. docstring)
    'gpt-image-2': 238,              # 2.38₽ (было 7.60₽) — Gen-API 2.50₽ (RouterAI после правки 5.96₽, но Gen-API дешевле)
    'grok-imagine-image': 475,       # 4.75₽ (было 2.10₽, ПОДНЯТА) — Gen-API 5.00₽
    'grok-imagine-image-quality': 535,  # 5.35₽ (было 4.70₽, ПОДНЯТА) — RouterAI 5.63₽ (ниже Gen-API 12.5₽)
    'qwen-image-3-0': 321,           # 3.21₽ (было 3.22₽) — RouterAI 3.38₽
    'qwen-image-3-0-pro': 427,       # 4.27₽ (было 3.00₽, ПОДНЯТА) — RouterAI 4.50₽
    'seedream-4-5': 427,             # 4.27₽ (было 4.29₽) — RouterAI 4.50₽
    'seedream-5-0': 374,             # 3.74₽ (было 1.50₽, ПОДНЯТА) — RouterAI 3.94₽ (Lite-тир, ближайший аналог)
    'wan-2-7-image': 713,            # 7.13₽ (было 2.30₽, ПОДНЯТА) — Gen-API 7.50₽
}
# Без изменений (нет конкурента хотя бы у одного из двух источников):
# dall-e-3, flux-kontext-max, flux-kontext-pro, gpt-image-1-5, z-image-turbo


class Command(BaseCommand):
    help = "Выравнивает базовую цену моделей изображений на конкурент×0.95 (см. docstring файла)"

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
