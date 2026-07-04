"""
Бесплатные текстовые модели через OpenRouter (`:free`).

Запуск: docker-compose exec web python manage.py add_openrouter_free_models

Модели помечаются is_free=True → показываются ТОЛЬКО во вкладке «Бесплатные»
и скрыты из общего каталога. provider='openrouter_free' → генерация идёт через
OpenRouter (OpenAI-совместимый эндпоинт, ключ OPENROUTER_API_KEY). Стоимость = 0,
но есть дневной лимит сообщений на пользователя (messages_limit) — весь пул
`:free`-моделей на OpenRouter общий на один API-ключ (аккаунт), это защита от
исчерпания квоты аккаунта одним активным пользователем.

Также деактивирует ранее засеянные бесплатные модели Groq (add_groq_free_models) —
Groq блокирует запросы из РФ (403 Forbidden), поэтому эти модели больше не
рабочие и не должны показываться пользователям — и первую (неверенную) партию
моделей OpenRouter, заменённую этим списком, отобранным по реальному объёму
недельного использования на openrouter.ai/models (топ по токенам = наиболее
стабильные и часто доступные провайдеры).

Повторный запуск обновляет метаданные и лимиты, но НЕ трогает уже вручную
выставленные значения цены.
"""
from django.core.management.base import BaseCommand
from aitext.models import Category, NeuralNetwork


# slug, name, model_name (OpenRouter), messages_limit (в день на пользователя), order, description
FREE_MODELS = [
    (
        'free-nemotron-3-ultra', 'Nemotron 3 Ultra — бесплатно', 'nvidia/nemotron-3-ultra-550b-a55b:free',
        15, 1,
        'Флагманская модель для сложных рассуждений и многошаговых задач, контекст 1M токенов.',
    ),
    (
        'free-nemotron-3-super', 'Nemotron 3 Super — бесплатно', 'nvidia/nemotron-3-super-120b-a12b:free',
        15, 2,
        'Структурированные ответы и сложные многошаговые рассуждения, контекст 1M токенов.',
    ),
    (
        'free-laguna-m1', 'Laguna M.1 — бесплатно', 'poolside/laguna-m.1:free',
        15, 3,
        'Флагманская модель для кода и агентной разработки от Poolside.',
    ),
    (
        'free-north-mini-code', 'North Mini Code — бесплатно', 'cohere/north-mini-code:free',
        15, 4,
        'Агентная модель Cohere для кода, terminal-задач и разработки.',
    ),
    (
        'free-gpt-oss-120b', 'GPT-OSS 120B — бесплатно', 'openai/gpt-oss-120b:free',
        15, 5,
        'Открытая модель OpenAI для рассуждений и агентных задач общего назначения.',
    ),
    (
        'free-gemma-4-31b', 'Gemma 4 31B — бесплатно', 'google/gemma-4-31b-it:free',
        15, 6,
        'Модель Google DeepMind с поддержкой изображений — универсальный чат и код.',
    ),
    (
        'free-qwen3-coder', 'Qwen3 Coder 480B — бесплатно', 'qwen/qwen3-coder:free',
        15, 7,
        'Флагманская модель Qwen для кода и агентных задач, контекст 1M токенов.',
    ),
    (
        'free-nemotron-3-nano-30b', 'Nemotron 3 Nano 30B — бесплатно', 'nvidia/nemotron-3-nano-30b-a3b:free',
        15, 8,
        'Компактная эффективная модель NVIDIA для агентных задач.',
    ),
    (
        'free-qwen3-next-80b', 'Qwen3 Next 80B — бесплатно', 'qwen/qwen3-next-80b-a3b-instruct:free',
        15, 9,
        'Быстрые и стабильные ответы без «размышлений» — код, знания, много языков.',
    ),
    (
        'free-laguna-xs21', 'Laguna XS 2.1 — бесплатно', 'poolside/laguna-xs-2.1:free',
        15, 10,
        'Компактная модель Poolside для кода — быстрая и экономичная.',
    ),
    (
        'free-nemotron-nano-9b', 'Nemotron Nano 9B — бесплатно', 'nvidia/nemotron-nano-9b-v2:free',
        15, 11,
        'Универсальная модель NVIDIA с настраиваемым режимом рассуждений.',
    ),
]

# Слаги старых бесплатных моделей Groq (add_groq_free_models) — деактивируем,
# так как Groq недоступен из РФ (гео-блок).
OLD_GROQ_FREE_SLUGS = [
    'free-llama-3-1-8b', 'free-llama-3-3-70b', 'free-qwen3-32b',
    'free-groq-compound', 'free-groq-compound-mini',
]

# Слаги первой (неверенной) партии OpenRouter-моделей, заменённой списком выше.
# 'free-qwen3-coder' сюда не входит — модель осталась в FREE_MODELS (тот же слаг).
OLD_OPENROUTER_FREE_SLUGS = [
    'free-deepseek-v4-flash', 'free-llama-3-3-70b-or', 'free-glm-4-5-air',
]


class Command(BaseCommand):
    help = 'Добавляет/обновляет бесплатные текстовые модели OpenRouter (вкладка «Бесплатные»)'

    def handle(self, *args, **options):
        text_net = (
            NeuralNetwork.objects.filter(provider='openrouter')
            .select_related('category').first()
        )
        if text_net:
            cat = text_net.category
        else:
            cat, _ = Category.objects.get_or_create(
                slug='neuroseti',
                defaults={'name': 'Нейросети', 'icon': 'fas fa-robot', 'order': 0},
            )
        self.stdout.write(f'Категория для бесплатных моделей: "{cat.name}" (id={cat.id})')

        self.stdout.write('\n=== Деактивация нерабочих моделей Groq (гео-блок РФ) ===')
        deactivated = NeuralNetwork.objects.filter(
            slug__in=OLD_GROQ_FREE_SLUGS, is_active=True,
        ).update(is_active=False)
        self.stdout.write(f'  деактивировано: {deactivated}')

        self.stdout.write('\n=== Деактивация первой партии OpenRouter-моделей (заменены) ===')
        deactivated_or = NeuralNetwork.objects.filter(
            slug__in=OLD_OPENROUTER_FREE_SLUGS, is_active=True,
        ).update(is_active=False)
        self.stdout.write(f'  деактивировано: {deactivated_or}')

        self.stdout.write('\n=== Бесплатные модели (OpenRouter) ===')
        for slug, name, model_name, limit, order, description in FREE_MODELS:
            network = NeuralNetwork.objects.filter(slug=slug).first()
            if network is None:
                network = NeuralNetwork.objects.create(
                    slug=slug,
                    name=name,
                    category=cat,
                    model_name=model_name,
                    provider='openrouter_free',
                    is_free=True,
                    cost_per_message=0,
                    cost_kopecks=0,
                    messages_limit=limit,
                    order=order,
                    description=description,
                    is_active=True,
                    is_popular=False,
                    unlimited=False,
                )
                self.stdout.write(
                    f"  {self.style.SUCCESS('создана')}: {network.name} "
                    f"({network.model_name}, лимит {limit}/день)"
                )
            else:
                network.name = name
                network.category = cat
                network.model_name = model_name
                network.provider = 'openrouter_free'
                network.is_free = True
                network.cost_per_message = 0
                network.cost_kopecks = 0
                network.messages_limit = limit
                network.order = order
                network.description = description
                network.is_active = True
                network.is_popular = False
                network.unlimited = False
                network.save(update_fields=[
                    'name', 'category', 'model_name', 'provider', 'is_free',
                    'cost_per_message', 'cost_kopecks', 'messages_limit', 'order',
                    'description', 'is_active', 'is_popular', 'unlimited',
                ])
                self.stdout.write(
                    f"  обновлена: {network.name} ({network.model_name}, лимит {limit}/день)"
                )

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово. Бесплатных моделей: {len(FREE_MODELS)}. '
            f'Проверьте OPENROUTER_API_KEY в .env.'
        ))
