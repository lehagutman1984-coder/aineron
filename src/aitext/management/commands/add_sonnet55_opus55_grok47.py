"""
Добавляет Claude Sonnet 5.5, Claude Opus 5.5, Grok 4.7 — по прямому запросу
пользователя, 2026-10-01 (2 скриншота apimart.ai, фильтры providers=Anthropic
и providers=xAI).

ВАЖНАЯ ПОПРАВКА к предыдущему заходу (d7f9fba): ранее эти 3 модели (плюс
deepseek-v4.1-flash/qwen3.8-2.4t-a95b/qwen3.8-flash) были признаны "работают
только через CometAPI, для текста нет механизма primary=cometapi" — это было
неверно, потому что диагностика шла напрямую на api.laozhang.ai. На самом
деле с 2026-09-06 ВЕСЬ текст (provider='openrouter') идёт через
get_laozhang_client() → FallbackClient('apimart_text') → цепочка
['apimart', 'cometapi'] (см. aitext/tasks.py:517-535, aitext/providers.py) —
имя функции осталось историческим, laozhang из активной цепочки убран.
apimart тестировался напрямую через requests и ошибочно казался "без
модели" (сам провайдер молча отдаёт text/event-stream с 200 даже без
stream=True в теле запроса — requests.json() падает на SSE-формате, что
выглядело как "модели нет", хотя модель реально отвечала). Пользователь
нашёл эти 3 модели на apimart напрямую через фильтр по провайдеру (скрины)
и смысл проверить правильно - через реальный прод-путь.

Подтверждено двумя независимыми способами:
1. Сырой curl к api.apimart.ai/v1/chat/completions - реальные SSE-чанки с
   содержимым (grok-4.7: delta.content="OK"; claude-sonnet-5-5: поток идёт,
   не ошибка).
2. CometAPI (резервный провайдер в той же цепочке) - 200 с реальным
   содержимым для всех трёх, живым вызовом.
Ни одна из трёх моделей не в TEXT_COMETAPI_NO_MODEL / TEXT_APIMART_NO_MODEL
(aitext/providers.py) - фолбэк сработает штатно, без спец-конфига.

Цена (опт×1.05, профиль 6000 вход/1500 выход - align_text_pricing_to_
competitors.py; RouterAI/Gen-API по этим моделям пока не публикуют цену,
опт взят с apimart.ai, тот же референс, что и для add_gpt6_sol_luna_models):
  claude-sonnet-5-5: apimart IN $1.6/1M, OUT $8/1M
    -> (1.6*0.006 + 8*0.0015) * 80 * 1.05 = 1.81₽ = 181 коп.
  claude-opus-5-5: apimart IN $3.2/1M, OUT $16/1M
    -> (3.2*0.006 + 16*0.0015) * 80 * 1.05 = 3.63₽ = 363 коп.
  grok-4.7: apimart IN $1.6/1M, OUT $4.8/1M
    -> (1.6*0.006 + 4.8*0.0015) * 80 * 1.05 = 1.41₽ = 141 коп.

Запуск: docker-compose exec web python manage.py add_sonnet55_opus55_grok47
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork, Category


MODELS = [
    {
        'name': 'Claude Sonnet 5.5',
        'slug': 'claude-sonnet-5-5',
        'model_name': 'claude-sonnet-5-5',
        'order': 84,
        'cost_kopecks': 181,
        'handle_photo': True,
        'description': 'Обновлённая версия Claude Sonnet — баланс скорости и интеллекта от Anthropic.',
    },
    {
        'name': 'Claude Opus 5.5',
        'slug': 'claude-opus-5-5',
        'model_name': 'claude-opus-5-5',
        'order': 85,
        'cost_kopecks': 363,
        'handle_photo': True,
        'description': 'Обновлённая версия флагманского Claude Opus — максимальное качество рассуждений.',
    },
    {
        'name': 'Grok 4.7',
        'slug': 'grok-4-7',
        'model_name': 'grok-4.7',
        'order': 86,
        'cost_kopecks': 141,
        'handle_photo': False,
        'description': 'Следующая версия флагмана xAI после Grok 4.6 — расширенные рассуждения и актуальные знания.',
    },
]


class Command(BaseCommand):
    help = 'Добавляет Claude Sonnet 5.5/Opus 5.5/Grok 4.7 в каталог (get_or_create, не трогает остальные модели)'

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
                handle_photo=spec['handle_photo'],
                handle_text_files=True,
                translate_to_english=False,
                config_json={},
            )

        if dry_run:
            self.stdout.write(self.style.WARNING('\n--dry-run: изменения НЕ сохранены'))
        else:
            self.stdout.write(self.style.SUCCESS('\nГотово'))
