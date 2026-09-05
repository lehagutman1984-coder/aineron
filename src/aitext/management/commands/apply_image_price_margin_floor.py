"""
Второй проход поверх align_image_pricing_to_competitors: применяет ПОЛ по
марже — розничная цена не может быть ниже опта (APIMart/CometAPI) × 1.05.
По прямому запросу пользователя, 2026-09-06: "цены на 5% дешевле
конкурентов, кроме тех моделей, где это было бы дешевле опта плюс наш
коэффициент 1.05 для маржи — там оставляем цену не ниже опт×1.05".

Формула на слаг: new_price = max(min(RouterAI, Gen-API) × 0.95, опт × 1.05).
Опт взят из IMAGE_PROVIDER_MIGRATION_PRICING_2026-09-05.html (собственное
исследование APIMart/CometAPI, курс 80 ₽/$) — самый дешёвый из двух опт-
источников на тот же представительный тир (medium/1K), который уже
использовался при выравнивании по конкурентам.

Из 23 моделей каталога формула меняет 4:
  gpt-image-1              2.09₽ -> 2.26₽   опт×1.05=2.26₽ (APIMart medium 2.15₽) > target 2.09₽
  gemini-2-5-flash-image   6.00₽ -> 9.26₽   не входила в раунд выравнивания вообще — просто досчитана target'ом
  seedream-4-0             8.00₽ -> 7.13₽   не входила в раунд выравнивания — была ВЫШЕ рынка (+6.7%), досчитана target'ом
  qwen-image-2-0           8.00₽ -> 8.31₽   не входила в раунд выравнивания — досчитана target'ом

gpt-image-1-mini НЕ включена, хотя формально опт×1.05 (2.30₽×1.05=2.42₽) выше
target (0.96₽): единственная опт-цифра для неё — CometAPI GPT Image 1 mini,
которая в исходном реестре APIMart/CometAPI дословно совпадает с ценой
GPT Image 1.5 (см. IMAGE_PROVIDER_MIGRATION_PRICING_2026-09-05.html) —
вероятная ошибка каталогизации у CometAPI, а не реальный опт по mini.
Применить пол по заведомо недостоверной цифре означало бы поднять розницу
до 2.42₽ при живом конкуренте RouterAI по 1.01₽ — вчетверо дороже рынка на
пустом месте. Оставлена без изменений до появления надёжного опта.

dall-e-3 не входит: опт по ней не собирался ни у APIMart, ни у CometAPI
(модель есть только на laozhang.ai) — пол посчитать не из чего.

Запуск: docker-compose exec web python manage.py apply_image_price_margin_floor
        docker-compose exec web python manage.py apply_image_price_margin_floor --dry-run
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork

# slug -> new cost_kopecks
PRICING = {
    'gpt-image-1': 226,               # 2.26₽ (было 2.09₽) — пол: APIMart опт 2.15₽ × 1.05
    'gemini-2-5-flash-image': 926,    # 9.26₽ (было 6.00₽) — Gen-API 9.75₽ × 0.95 (не входила в выравнивание)
    'seedream-4-0': 713,              # 7.13₽ (было 8.00₽) — Gen-API 7.50₽ × 0.95 (не входила в выравнивание)
    'qwen-image-2-0': 831,            # 8.31₽ (было 8.00₽) — Gen-API 8.75₽ × 0.95 (не входила в выравнивание)
}
# Проверена и сознательно НЕ включена: gpt-image-1-mini (см. docstring —
# единственный опт-источник у CometAPI недостоверен, дублирует цену 1.5).
# Без опта вообще, пол посчитать не из чего: dall-e-3.


class Command(BaseCommand):
    help = "Применяет пол по марже (опт×1.05) поверх align_image_pricing_to_competitors — см. docstring файла"

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
            direction = 'поднята' if new_cost > old_cost else ('снижена' if new_cost < old_cost else 'без изменений')
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
