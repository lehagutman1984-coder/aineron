"""
Бесплатные текстовые модели через Groq (console.groq.com).

Запуск: docker-compose exec web python manage.py add_groq_free_models

Модели помечаются is_free=True → показываются ТОЛЬКО во вкладке «Бесплатные»
и скрыты из общего каталога. provider='groq' → генерация идёт через Groq
(OpenAI-совместимый эндпоинт, ключ GROQ_API_KEY). Стоимость = 0, но есть
дневной лимит сообщений на пользователя (messages_limit) — чтобы не исчерпать
общую бесплатную квоту Groq на весь сервис.

Лимиты подобраны по дневным квотам Groq (RPD) с запасом на всех пользователей;
их можно менять в админке. Повторный запуск обновляет метаданные и лимиты,
но НЕ трогает уже вручную выставленные значения цены.
"""
from django.core.management.base import BaseCommand
from aitext.models import Category, NeuralNetwork


# slug, name, model_name (Groq), messages_limit (в день на пользователя), order, description
FREE_MODELS = [
    (
        'free-llama-3-1-8b', 'Llama 3.1 8B — бесплатно', 'llama-3.1-8b-instant',
        50, 1,
        'Быстрая бесплатная модель для повседневных задач. Основной бесплатный движок.',
    ),
    (
        'free-llama-3-3-70b', 'Llama 3.3 70B — бесплатно', 'llama-3.3-70b-versatile',
        15, 2,
        'Более умная бесплатная модель для сложных вопросов. Дневной лимит скромнее.',
    ),
    (
        'free-qwen3-32b', 'Qwen3 32B — бесплатно', 'qwen/qwen3-32b',
        15, 3,
        'Качественная бесплатная модель с хорошим пониманием контекста.',
    ),
    (
        'free-groq-compound', 'Groq Compound — бесплатно', 'groq/compound',
        10, 4,
        'Агентная модель Groq для сложных редких задач. Небольшой дневной лимит.',
    ),
    (
        'free-groq-compound-mini', 'Groq Compound Mini — бесплатно', 'groq/compound-mini',
        10, 5,
        'Лёгкая агентная модель Groq. Быстрее Compound, тот же дневной лимит.',
    ),
]


class Command(BaseCommand):
    help = 'Добавляет/обновляет бесплатные текстовые модели Groq (вкладка «Бесплатные»)'

    def handle(self, *args, **options):
        # Кладём в ту же категорию, что и обычные текстовые модели, чтобы не плодить
        # пустых вкладок-категорий (бесплатные всё равно скрыты из категорий каталога).
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

        self.stdout.write('\n=== Бесплатные модели (Groq) ===')
        for slug, name, model_name, limit, order, description in FREE_MODELS:
            network = NeuralNetwork.objects.filter(slug=slug).first()
            if network is None:
                network = NeuralNetwork.objects.create(
                    slug=slug,
                    name=name,
                    category=cat,
                    model_name=model_name,
                    provider='groq',
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
                network.provider = 'groq'
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
            f'Проверьте GROQ_API_KEY в .env.'
        ))
