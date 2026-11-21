"""
Поднимает цены моделей, которые продавались НИЖЕ себестоимости (требование
владельца, 2026-11-21: «нам нельзя ниже себестоимости — плюсуй маржу»).

ПРАВИЛО: новая цена = оптовая стоимость сообщения × 105 (стандартный K витрины,
PRICING_SIMPLIFICATION_PLAN.md §2.1; это ≈ +15% к реальному курсу ~91 ₽/$).
Сообщение = стандартный профиль 6000 вход + 1500 выход токенов. Команда ТОЛЬКО
ПОДНИМАЕТ: если текущая цена уже >= новой — модель пропускается.

ИСТОЧНИКИ ОПТА (USD за 1M токенов, вход/выход) и расчёт:
  модель                опт (вх/вых)     источник                      msg$      ×105     было
  deepseek-v4-flash     0.343 / 1.032    реестр apimart (пик) + замер  0.00361   0.38₽    0.08₽
  deepseek-v4-pro       1.029 / 3.086    реестр apimart (пик)          0.01081   1.13₽    0.71₽
  gpt-5-6-sol           3.2 / 16         реестр apimart (≤272K)        0.0432    4.54₽    2.84₽
  claude-sonnet-5-5     1.6 / 8          apimart/CometAPI (прайс)      0.0216    2.27₽    1.81₽
  claude-opus-5-5       3.2 / 16         apimart (замер входа 2026-11-21) 0.0432 4.54₽    3.63₽
  gpt-6-sol, gpt-6-1-sol 1.6 / 8         apimart (прайс, прошлые раунды) 0.0216 2.27₽    1.81₽
  grok-4-7              1.6 / 4.8        apimart (прайс)               0.0168    1.76₽    1.41₽
  qwen3-6-max           1.664 / 9.984    CometAPI x ratio (единственный провайдер: у apimart модели нет)
                                                                        0.02496   2.62₽    1.64₽
  gpt-6-luna            0.08 / 0.4       apimart (прайс)               0.00108   0.12₽(мин) 0.10₽
Достоверность: высокая — deepseek-v4-flash/opus-5-5/sonnet-5-5/gpt-5-6-sol;
средняя — gpt-6-sol/gpt-6-1-sol/grok-4-7/gpt-6-luna (опт из прайсов прошлых
раундов, живьём не перемерян; значения K=105 дают запас).

Остальные текстовые модели не трогаются: они выше расчётного пола.
Медиа (картинки/видео) — отдельная часть этого захода (см. MEDIA_RAISE).

Запуск: docker compose exec web python manage.py raise_prices_to_cost_floor_2026_11_21 [--dry-run]
Идемпотентна. Только slug из списка, остальные поля моделей не меняются.
"""
from django.core.management.base import BaseCommand

from aitext.models import NeuralNetwork

# slug -> новая цена, коп.
TEXT_RAISE = {
    'deepseek-v4-flash': 38,
    'deepseek-v4-pro': 113,
    'gpt-5-6-sol': 454,
    'claude-sonnet-5-5': 227,
    'claude-opus-5-5': 454,
    'gpt-6-sol': 227,
    'gpt-6-1-sol': 227,
    'grok-4-7': 176,
    'qwen3-6-max': 262,
    'gpt-6-luna': 12,
}

# Медиа. Опт ИЗМЕРЕН точно: поле `cost` (USD, billing_status=settled) задачи
# apimart GET /v1/tasks/{id}, 2026-11-21, наши дефолтные параметры.
#   gpt-image-2-5-sunburst / -flare  1024x1024 auto: $0.042212 -> x105 = 4.43₽ (было 2.38₽, ниже опта 3.84₽ при 91 ₽/$)
#   wan-2-6  5 с 720p: $0.25 (реестр apimart) -> x105 = 26.25₽ (было 21.38₽, опт 22.75₽ при 91 ₽/$).
#            ВНИМАНИЕ: на резерве CometAPI опт $0.40 (36.4₽) — при фолбэке всё равно убыток.
# Проверено и НЕ требует повышения (замер): gpt-image-1.5 $0.0296 (цена 5.70₽), gpt-image-2 $0.0085,
# gemini-2.5-flash-image $0.008, gemini-3-pro-image $0.020, veo3.1-lite $0.07 (цена 42.79₽) — все с запасом.
MEDIA_RAISE = {
    'gpt-image-2-5-sunburst': 443,
    'gpt-image-2-5-flare': 443,
    'wan-2-6': 2625,
}

RAISE = {**TEXT_RAISE, **MEDIA_RAISE}


class Command(BaseCommand):
    help = 'Поднимает цены моделей, продававшихся ниже себестоимости (только вверх)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry = options['dry_run']
        changed = 0
        for slug, new in RAISE.items():
            n = NeuralNetwork.objects.filter(slug=slug).first()
            if not n:
                self.stdout.write(self.style.WARNING(f'{slug}: нет такой модели, пропуск'))
                continue
            if n.cost_kopecks >= new:
                self.stdout.write(f'{slug}: {n.cost_kopecks} >= {new} коп., уже не ниже — пропуск')
                continue
            self.stdout.write(f'{slug}: {n.cost_kopecks} -> {new} коп. ({n.cost_kopecks/100:.2f} -> {new/100:.2f} ₽)')
            if dry:
                continue
            # Как и прошлые раунды репрайсинга — только cost_kopecks (авторитетное
            # поле); legacy cost_per_message не трогаем.
            NeuralNetwork.objects.filter(pk=n.pk).update(cost_kopecks=new)
            changed += 1
        self.stdout.write(self.style.WARNING('\n--dry-run: не сохранено') if dry
                          else self.style.SUCCESS(f'\nГотово: поднято {changed}'))
