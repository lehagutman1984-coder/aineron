"""
Добавляет GPT-6.1 Sol, GPT-6 Luna, GPT-6 Sol в каталог — по прямому запросу
пользователя, 2026-10-01 (2 скриншота apimart.ai, тип=chat).

Проверено живым вызовом (не только присутствием в прайс-листе/дампе!) на
laozhang.ai chat/completions с реальным ключом — все три отдают 200 и
реальный usage (reasoning-модели, требуют max_completion_tokens вместо
max_tokens - это НЕ ошибка отсутствия модели, обычное свойство всей линейки
GPT-5.6/6.x, уже учтено существующим кодом аналогично gpt-5.6-*/gpt-6-astra).

Остальные 9 моделей с тех же 2 скриншотов (claude-sonnet-5-5, claude-opus-5-5,
grok-4.7, deepseek-v4.1-flash, qwen3.8-2.4t-a95b, qwen3.8-flash,
qwen3.8-max-0902, qwen3.7-flash, qwen3.8-27b) НЕ добавлены этой командой:
- qwen3.8-max-0902 не нужна отдельно - недатированная "qwen3.8-max" уже
  активна в каталоге (id уже есть), датированный вариант у обоих
  провайдеров возвращает model_not_found.
- qwen3.7-flash и qwen3.8-27b не работают ни на laozhang, ни на CometAPI
  (503 model_not_found на обоих, живым вызовом).
- claude-sonnet-5-5/claude-opus-5-5/grok-4.7/deepseek-v4.1-flash/
  qwen3.8-2.4t-a95b/qwen3.8-flash — РЕАЛЬНО работают, но только через
  CometAPI (laozhang 503 "no available channels" у всех шести, apimart
  вообще не имеет их в каталоге). В проекте нет механизма "CometAPI как
  основной провайдер для текста" - только для изображений/видео
  (metadata.cometapi_fallback_model в fal_utils.py). Построить такой же
  путь для текста (другой код, SSE-стриминг) - отдельная по объёму задача,
  не добавляю вслепую без решения пользователя заводить её.

Цена (опт×1.05, профиль 6000 вход/1500 выход - тот же, что в
align_text_pricing_to_competitors.py, Gen-API/RouterAI по этим трём моделям
пока не публикуют цену - слишком новые, использован опт apimart.ai как
референс, тот же источник, что и для align_image_pricing_to_competitors):
  gpt-6.1-sol / gpt-6-sol: apimart IN $1.6/1M, OUT $8/1M (после скидки 20%)
    -> (1.6*0.006 + 8*0.0015) * 80 руб/$ * 1.05 = 1.81₽ = 181 коп.
  gpt-6-luna: apimart IN $0.08/1M, OUT $0.4/1M (после скидки 20%)
    -> (0.08*0.006 + 0.4*0.0015) * 80 * 1.05 = 0.0907₽ - округлено вверх до
    10 коп. (MIN_CHARGE_KOPECKS уже не даёт списать меньше на споте, ставим
    и в каталоге ту же цифру, чтобы показанная цена совпадала со списанной).

Запуск: docker-compose exec web python manage.py add_gpt6_sol_luna_models
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork, Category


MODELS = [
    {
        'name': 'GPT-6.1 Sol',
        'slug': 'gpt-6-1-sol',
        'model_name': 'gpt-6.1-sol',
        'order': 81,
        'cost_kopecks': 181,
        'description': 'Следующая версия линейки GPT-6 Sol.',
    },
    {
        'name': 'GPT-6 Sol',
        'slug': 'gpt-6-sol',
        'model_name': 'gpt-6-sol',
        'order': 82,
        'cost_kopecks': 181,
        'description': 'Одна из веток нового семейства GPT-6.',
    },
    {
        'name': 'GPT-6 Luna',
        'slug': 'gpt-6-luna',
        'model_name': 'gpt-6-luna',
        'order': 83,
        'cost_kopecks': 10,
        'description': 'Одна из веток нового семейства GPT-6 — лёгкая и быстрая.',
    },
]


class Command(BaseCommand):
    help = 'Добавляет GPT-6.1 Sol/GPT-6 Sol/GPT-6 Luna в каталог (get_or_create, не трогает остальные модели)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Только показать, что будет сделано')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        category, _ = Category.objects.get_or_create(name='Текст')

        for spec in MODELS:
            existing = NeuralNetwork.objects.filter(slug=spec['slug']).first()
            if existing:
                self.stdout.write(self.style.WARNING(f"{spec['slug']}: уже существует (id={existing.id}), пропуск"))
                continue

            self.stdout.write(
                f"{spec['slug']}: создать \"{spec['name']}\" model_name={spec['model_name']} "
                f"cost_kopecks={spec['cost_kopecks']} ({spec['cost_kopecks']/100:.2f}₽)"
            )
            if dry_run:
                continue

            NeuralNetwork.objects.create(
                name=spec['name'],
                slug=spec['slug'],
                category=category,
                description=spec['description'],
                description_ru=spec['description'],
                model_name=spec['model_name'],
                provider='openrouter',
                order=spec['order'],
                cost_per_message=max(spec['cost_kopecks'] // 100, 1),
                cost_kopecks=spec['cost_kopecks'],
                is_active=True,
                is_new=True,
                handle_photo=True,
                handle_text_files=True,
                translate_to_english=False,
                config_json={},
            )

        if dry_run:
            self.stdout.write(self.style.WARNING('\n--dry-run: изменения НЕ сохранены'))
        else:
            self.stdout.write(self.style.SUCCESS('\nГотово'))
