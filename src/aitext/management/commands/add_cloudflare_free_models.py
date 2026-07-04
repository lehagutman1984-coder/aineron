"""
Бесплатные текстовые модели через Cloudflare Workers AI.

Запуск: docker-compose exec web python manage.py add_cloudflare_free_models

Модели помечаются is_free=True → показываются ТОЛЬКО во вкладке «Бесплатные»
и скрыты из общего каталога. provider='cloudflare_free' → генерация идёт через
Cloudflare Workers AI (OpenAI-совместимый эндпоинт
api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1, ключи
CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN). Бесплатный лимит — 10 000
«нейронов»/день на весь аккаунт (общий пул на все модели и всех пользователей,
сброс в 00:00 UTC), не расходуемые credits — messages_limit защищает от
исчерпания этого пула одним активным пользователем.

Доступность из РФ подтверждена вручную: 5 из 6 протестированных моделей
ответили корректно через curl с боевого окружения 2026-07-04 (см.
[[project-free-models-groq-blocked]] в памяти). 6-я (glm-4.7-flash) стабильно
таймаутила — пропущена (та же модель уже есть через Z.ai напрямую).

Повторный запуск обновляет метаданные и лимиты, но НЕ трогает уже вручную
выставленные значения цены.
"""
from django.core.management.base import BaseCommand
from aitext.models import Category, NeuralNetwork


# slug, name, model_name (Cloudflare "@cf/..."), messages_limit (в день на пользователя), order, description
FREE_MODELS = [
    (
        'free-cf-llama-4-scout', 'Llama 4 Scout — бесплатно', '@cf/meta/llama-4-scout-17b-16e-instruct',
        15, 15,
        'Мультимодальная MoE-модель Meta — понимает текст и изображения.',
    ),
    (
        'free-cf-gpt-oss-120b', 'GPT-OSS 120B (Cloudflare) — бесплатно', '@cf/openai/gpt-oss-120b',
        15, 16,
        'Открытая модель OpenAI для рассуждений — независимый резерв от версии на OpenRouter.',
    ),
    (
        'free-cf-qwen3-30b', 'Qwen3 30B — бесплатно', '@cf/qwen/qwen3-30b-a3b-fp8',
        15, 17,
        'MoE-модель Qwen для рассуждений и агентных задач.',
    ),
    (
        'free-cf-mistral-small', 'Mistral Small 3.1 — бесплатно', '@cf/mistralai/mistral-small-3.1-24b-instruct',
        15, 18,
        'Модель Mistral с пониманием изображений, контекст 128K токенов.',
    ),
    (
        'free-cf-deepseek-r1-distill', 'DeepSeek R1 Distill 32B — бесплатно', '@cf/deepseek-ai/deepseek-r1-distill-qwen-32b',
        15, 19,
        'Дистиллированная модель рассуждений DeepSeek R1 — сильна в логике и математике.',
    ),
]


class Command(BaseCommand):
    help = 'Добавляет/обновляет бесплатные текстовые модели Cloudflare Workers AI (вкладка «Бесплатные»)'

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

        self.stdout.write('\n=== Бесплатные модели (Cloudflare Workers AI) ===')
        for slug, name, model_name, limit, order, description in FREE_MODELS:
            network = NeuralNetwork.objects.filter(slug=slug).first()
            if network is None:
                network = NeuralNetwork.objects.create(
                    slug=slug,
                    name=name,
                    category=cat,
                    model_name=model_name,
                    provider='cloudflare_free',
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
                network.provider = 'cloudflare_free'
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
            f'\nГотово. Бесплатных моделей Cloudflare: {len(FREE_MODELS)}. '
            f'Проверьте CLOUDFLARE_ACCOUNT_ID и CLOUDFLARE_API_TOKEN в .env.'
        ))
