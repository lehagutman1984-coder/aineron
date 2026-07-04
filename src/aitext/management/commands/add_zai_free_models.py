"""
Бесплатные текстовые модели через Z.ai (Zhipu AI, Китай) — GLM-*-Flash.

Запуск: docker-compose exec web python manage.py add_zai_free_models

Модели помечаются is_free=True → показываются ТОЛЬКО во вкладке «Бесплатные»
и скрыты из общего каталога. provider='zai_free' → генерация идёт через Z.ai
(OpenAI-совместимый эндпоинт api.z.ai/api/paas/v4, ключ ZAI_API_KEY). Согласно
официальному прайсингу Z.ai (docs.z.ai/guides/overview/pricing), GLM-4.7-Flash,
GLM-4.5-Flash и GLM-4.6V-Flash — постоянно бесплатны (не «limited-time»),
в отличие от большинства других строк таблицы. Z.ai — китайский провайдер,
доступен из РФ без прокси (в отличие от Groq, см. [[project-free-models-groq-blocked]]).

Публичные документированные лимиты RPM/RPD для бесплатного тира Z.ai не
найдены — messages_limit подобран консервативно; при необходимости свериться
с личным кабинетом (z.ai/manage-apikey/rate-limits) и скорректировать в админке.

Повторный запуск обновляет метаданные и лимиты, но НЕ трогает уже вручную
выставленные значения цены.
"""
from django.core.management.base import BaseCommand
from aitext.models import Category, NeuralNetwork


# slug, name, model_name (Z.ai), messages_limit (в день на пользователя), order, description
FREE_MODELS = [
    (
        'free-glm-4-7-flash', 'GLM-4.7 Flash — бесплатно', 'glm-4.7-flash',
        15, 12,
        'Быстрая модель Z.ai для кода, рассуждений и агентных задач.',
    ),
    (
        'free-glm-4-5-flash', 'GLM-4.5 Flash — бесплатно', 'glm-4.5-flash',
        15, 13,
        'Модель Z.ai с хорошей производительностью для рассуждений и кода.',
    ),
    (
        'free-glm-4-6v-flash', 'GLM-4.6V Flash — бесплатно', 'glm-4.6v-flash',
        15, 14,
        'Модель Z.ai с пониманием изображений — низкая задержка, быстрые ответы.',
    ),
]


class Command(BaseCommand):
    help = 'Добавляет/обновляет бесплатные текстовые модели Z.ai (вкладка «Бесплатные»)'

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

        self.stdout.write('\n=== Бесплатные модели (Z.ai) ===')
        for slug, name, model_name, limit, order, description in FREE_MODELS:
            network = NeuralNetwork.objects.filter(slug=slug).first()
            if network is None:
                network = NeuralNetwork.objects.create(
                    slug=slug,
                    name=name,
                    category=cat,
                    model_name=model_name,
                    provider='zai_free',
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
                network.provider = 'zai_free'
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
            f'\nГотово. Бесплатных моделей Z.ai: {len(FREE_MODELS)}. '
            f'Проверьте ZAI_API_KEY в .env.'
        ))
