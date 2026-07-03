from django.core.management.base import BaseCommand
from aitext.models import Category, NeuralNetwork


IMAGE_CONFIG = {
    'dalle3': {
        "name": "DALL-E 3",
        "api_defaults": {"size": "1024x1024", "quality": "standard", "n": 1},
        "ui_settings": {
            "sections": [{
                "title": "Настройки изображения",
                "fields": [
                    {
                        "name": "size",
                        "type": "select",
                        "label": "Размер",
                        "extra_cost": 0,
                        "options": [
                            {"value": "1024x1024", "label": "1024×1024 (квадрат)", "extra_cost": 0},
                            {"value": "1024x1792", "label": "1024×1792 (вертикаль)", "extra_cost": 0},
                            {"value": "1792x1024", "label": "1792×1024 (горизонталь)", "extra_cost": 0},
                        ]
                    },
                    {
                        "name": "quality",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "standard", "label": "Стандартное", "extra_cost": 0},
                            {"value": "hd", "label": "HD (детализированное)", "extra_cost": 10},
                        ]
                    },
                    {
                        "name": "style",
                        "type": "select",
                        "label": "Стиль",
                        "extra_cost": 0,
                        "options": [
                            {"value": "vivid", "label": "Яркий (vivid)", "extra_cost": 0},
                            {"value": "natural", "label": "Естественный (natural)", "extra_cost": 0},
                        ]
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {"requires_input_images": False}
    },
    'gpt_image': {
        "name": "GPT Image",
        "api_defaults": {"size": "1024x1024", "quality": "auto", "n": 1},
        "ui_settings": {
            "sections": [{
                "title": "Настройки изображения",
                "fields": [
                    {
                        "name": "size",
                        "type": "select",
                        "label": "Размер",
                        "extra_cost": 0,
                        "options": [
                            {"value": "1024x1024", "label": "1024×1024 (квадрат)", "extra_cost": 0},
                            {"value": "1024x1536", "label": "1024×1536 (вертикаль)", "extra_cost": 0},
                            {"value": "1536x1024", "label": "1536×1024 (горизонталь)", "extra_cost": 0},
                        ]
                    },
                    {
                        "name": "quality",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "auto", "label": "Авто", "extra_cost": 0},
                            {"value": "low", "label": "Низкое", "extra_cost": 0},
                            {"value": "medium", "label": "Среднее", "extra_cost": 0},
                            {"value": "high", "label": "Высокое", "extra_cost": 10},
                        ]
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {"requires_input_images": False}
    },
    'flux': {
        "name": "Flux",
        "api_defaults": {"size": "1024x1024", "n": 1},
        "ui_settings": {
            "sections": [{
                "title": "Настройки изображения",
                "fields": [
                    {
                        "name": "size",
                        "type": "select",
                        "label": "Размер",
                        "extra_cost": 0,
                        "options": [
                            {"value": "1024x1024", "label": "1024×1024 (квадрат)", "extra_cost": 0},
                            {"value": "1024x1792", "label": "1024×1792 (вертикаль)", "extra_cost": 0},
                            {"value": "1792x1024", "label": "1792×1024 (горизонталь)", "extra_cost": 0},
                            {"value": "512x512", "label": "512×512 (маленькое)", "extra_cost": 0},
                        ]
                    },
                    # Sprint 4: Creative Controls (только Flux — seed/negative_prompt безопасны
                    # для fal-ai/Flux, но НЕ для OpenAI-бэкенда dall-e/gpt_image).
                    {
                        "name": "seed",
                        "type": "number",
                        "label": "Seed",
                        "min": 0,
                        "max": 9999999999,
                        "default": None,
                        "extra_cost": 0,
                    },
                    {
                        "name": "negative_prompt",
                        "type": "textarea",
                        "label": "Негативный промт",
                        "max_length": 1000,
                        "extra_cost": 0,
                    },
                    {
                        "name": "num_images",
                        "type": "select",
                        "label": "Кол-во",
                        "extra_cost": 0,
                        # num_images=N множит стоимость провайдера в N раз — берём
                        # доплату, иначе revenue leak (1× за 4 картинки).
                        "options": [
                            {"value": "1", "label": "1", "extra_cost": 0},
                            {"value": "2", "label": "2", "extra_cost": 20},
                            {"value": "4", "label": "4", "extra_cost": 60},
                        ]
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {"requires_input_images": False}
    },
    # Seedream (ByteDance) и Gemini Image не принимают size/n — minimal_params.
    'seedream': {
        "name": "Seedream",
        "api_defaults": {},
        "ui_settings": {"sections": []},
        "constraints": {},
        "metadata": {"requires_input_images": False, "minimal_params": True}
    },
    'gemini_image': {
        "name": "Gemini Image",
        "api_defaults": {},
        "ui_settings": {"sections": []},
        "constraints": {},
        "metadata": {"requires_input_images": False, "minimal_params": True}
    },
}

# Sprint 4: поля Creative Controls для миграции уже задеплоенных строк
# (см. management-команду update_image_model_settings). Должны совпадать с
# полями, добавленными выше в IMAGE_CONFIG['flux'].
CREATIVE_CONTROL_FIELDS = [
    {
        "name": "seed",
        "type": "number",
        "label": "Seed",
        "min": 0,
        "max": 9999999999,
        "default": None,
        "extra_cost": 0,
    },
    {
        "name": "negative_prompt",
        "type": "textarea",
        "label": "Негативный промт",
        "max_length": 1000,
        "extra_cost": 0,
    },
    {
        "name": "num_images",
        "type": "select",
        "label": "Кол-во",
        "extra_cost": 0,
        "options": [
            {"value": "1", "label": "1", "extra_cost": 0},
            {"value": "2", "label": "2", "extra_cost": 20},
            {"value": "4", "label": "4", "extra_cost": 60},
        ]
    },
]

# Слаги моделей, для которых Creative Controls безопасны (config_key == 'flux').
FLUX_MODEL_SLUGS = [
    'flux-2-pro', 'flux-2-max', 'flux-kontext-pro', 'flux-kontext-max', 'flux-2-flex',
]


TEXT_MODELS = [
    # OpenAI GPT
    dict(name='GPT-4o', slug='gpt-4o', model_name='gpt-4o', cost_per_message=4, cost_kopecks=400, order=1,
         description='Флагманская мультимодальная модель OpenAI. Понимает текст, изображения и аудио.',
         handle_photo=True, is_popular=True),
    dict(name='GPT-4o Mini', slug='gpt-4o-mini', model_name='gpt-4o-mini', cost_per_message=1, cost_kopecks=100, order=2,
         description='Быстрая и экономичная версия GPT-4o для повседневных задач.',
         handle_photo=True, is_popular=True),
    dict(name='GPT-4.1', slug='gpt-4-1', model_name='gpt-4.1', cost_per_message=4, cost_kopecks=400, order=3,
         description='Обновлённая версия GPT-4 с улучшенными возможностями для кода и анализа.',
         handle_photo=True),
    dict(name='GPT-4.1 Mini', slug='gpt-4-1-mini', model_name='gpt-4.1-mini', cost_per_message=1, cost_kopecks=100, order=4,
         description='Компактная версия GPT-4.1 — быстро и дёшево.',
         handle_photo=True),
    dict(name='GPT-5', slug='gpt-5', model_name='gpt-5', cost_per_message=12, cost_kopecks=1200, order=5,
         description='Самая мощная модель OpenAI нового поколения.',
         handle_photo=True, is_popular=True),
    dict(name='ChatGPT-4o', slug='chatgpt-4o-latest', model_name='chatgpt-4o-latest', cost_per_message=4, cost_kopecks=400, order=6,
         description='Последняя версия ChatGPT-4o, используемая в ChatGPT.',
         handle_photo=True),
    # OpenAI Reasoning
    dict(name='o3', slug='o3', model_name='o3', cost_per_message=10, cost_kopecks=1000, order=10,
         description='Мощная модель рассуждений OpenAI для сложных задач: математика, наука, логика.'),
    dict(name='o4 Mini', slug='o4-mini', model_name='o4-mini', cost_per_message=3, cost_kopecks=300, order=11,
         description='Быстрая модель рассуждений OpenAI. Отлично справляется с кодингом и математикой.',
         is_popular=True),
    dict(name='o1', slug='o1', model_name='o1', cost_per_message=8, cost_kopecks=800, order=12,
         description='Классическая reasoning-модель OpenAI с глубоким анализом.'),
    dict(name='o3 Mini', slug='o3-mini', model_name='o3-mini', cost_per_message=2, cost_kopecks=200, order=13,
         description='Компактная reasoning-модель для логических и математических задач.'),
    # Claude
    dict(name='Claude Sonnet 4.6', slug='claude-sonnet-4-6', model_name='claude-sonnet-4-6', cost_per_message=5, cost_kopecks=500, order=20,
         description='Последний Claude Sonnet — баланс интеллекта и скорости от Anthropic.',
         handle_photo=True, is_popular=True),
    dict(name='Claude Opus 4.8', slug='claude-opus-4-8', model_name='claude-opus-4-8', cost_per_message=20, cost_kopecks=2000, order=21,
         description='Самый мощный Claude. Для сложного анализа, написания и кода.',
         handle_photo=True),
    dict(name='Claude Haiku 4.5', slug='claude-haiku-4-5', model_name='claude-haiku-4-5-20251001', cost_per_message=2, cost_kopecks=150, order=22,
         description='Самый быстрый и дешёвый Claude для простых задач.',
         handle_photo=True),
    dict(name='Claude Sonnet 4.5', slug='claude-sonnet-4-5', model_name='claude-sonnet-4-5-20250929', cost_per_message=4, cost_kopecks=400, order=23,
         description='Надёжный Claude Sonnet предыдущего поколения.',
         handle_photo=True),
    # Gemini
    dict(name='Gemini 2.5 Flash', slug='gemini-2-5-flash', model_name='gemini-2.5-flash', cost_per_message=1, cost_kopecks=100, order=30,
         description='Быстрая мультимодальная модель Google с поддержкой длинного контекста.',
         handle_photo=True, is_popular=True),
    dict(name='Gemini 2.5 Pro', slug='gemini-2-5-pro', model_name='gemini-2.5-pro', cost_per_message=5, cost_kopecks=500, order=31,
         description='Флагманская модель Google с огромным контекстом и мультимодальностью.',
         handle_photo=True),
    dict(name='Gemini 3 Flash', slug='gemini-3-flash', model_name='gemini-3-flash-preview', cost_per_message=2, cost_kopecks=150, order=32,
         description='Новейший Gemini Flash — быстрый и умный.',
         handle_photo=True),
    # DeepSeek
    dict(name='DeepSeek V3', slug='deepseek-v3', model_name='deepseek-v3', cost_per_message=1, cost_kopecks=100, order=40,
         description='Мощная открытая модель DeepSeek. Отлично справляется с кодом и аналитикой.',
         is_popular=True),
    dict(name='DeepSeek R1', slug='deepseek-r1', model_name='deepseek-r1', cost_per_message=2, cost_kopecks=200, order=41,
         description='Reasoning-модель DeepSeek — конкурент o1 с открытым исходным кодом.',
         is_popular=True),
    dict(name='DeepSeek V3.1', slug='deepseek-v3-1', model_name='deepseek-v3.1', cost_per_message=1, cost_kopecks=100, order=42,
         description='Обновлённая версия DeepSeek V3 с улучшенными возможностями.'),
    # Qwen
    dict(name='Qwen 3 235B', slug='qwen3-235b', model_name='qwen3-235b-a22b', cost_per_message=2, cost_kopecks=200, order=50,
         description='Флагманская открытая модель Alibaba с 235 млрд параметров.'),
    dict(name='Qwen 3 Max', slug='qwen3-max', model_name='qwen3-max', cost_per_message=2, cost_kopecks=200, order=51,
         description='Мощная модель Qwen 3 для сложных задач.'),
    dict(name='QwQ Plus', slug='qwq-plus', model_name='qwq-plus', cost_per_message=2, cost_kopecks=200, order=52,
         description='Reasoning-модель Qwen с глубоким анализом задач.'),
    # Grok
    dict(name='Grok 4', slug='grok-4', model_name='grok-4', cost_per_message=10, cost_kopecks=1000, order=60,
         description='Новейшая флагманская модель xAI. Доступ к интернету в реальном времени.',
         is_popular=True),
    dict(name='Grok 3', slug='grok-3', model_name='grok-3', cost_per_message=4, cost_kopecks=400, order=61,
         description='Мощная модель xAI с обширными знаниями и аналитикой.'),
    dict(name='Grok 4 Fast', slug='grok-4-fast', model_name='grok-4-fast', cost_per_message=2, cost_kopecks=200, order=62,
         description='Быстрая версия Grok 4 для оперативных ответов.'),
    # Other
    dict(name='Kimi K2', slug='kimi-k2', model_name='kimi-k2', cost_per_message=2, cost_kopecks=200, order=70,
         description='Мощная модель Moonshot AI с огромным контекстом в 128k токенов.'),
    dict(name='GLM 4.5', slug='glm-4-5', model_name='glm-4.5', cost_per_message=1, cost_kopecks=100, order=71,
         description='Умная китайская модель от Zhipu AI для разнообразных задач.'),
    dict(name='GPT-3.5 Turbo', slug='gpt-3-5-turbo', model_name='gpt-3.5-turbo', cost_per_message=1, cost_kopecks=50, order=80,
         description='Классическая быстрая модель OpenAI. Идеально для простых чатов.'),

    # ── Новые флагманы (2026) ────────────────────────────────────────────────
    # OpenAI GPT-5.x
    dict(name='GPT-5.2', slug='gpt-5-2', model_name='gpt-5.2', cost_per_message=14, cost_kopecks=1400, order=5,
         description='Новейшая флагманская модель OpenAI. Максимальный интеллект и мультимодальность.',
         handle_photo=True, is_popular=True),
    dict(name='GPT-5.1', slug='gpt-5-1', model_name='gpt-5.1', cost_per_message=12, cost_kopecks=1200, order=6,
         description='Улучшенный GPT-5 с более точными ответами и рассуждением.',
         handle_photo=True, is_popular=True),
    # Claude нового поколения
    dict(name='Claude Sonnet 5', slug='claude-sonnet-5', model_name='claude-sonnet-5', cost_per_message=6, cost_kopecks=600, order=19,
         description='Новейший Claude Sonnet 5 — топовый баланс скорости и интеллекта от Anthropic.',
         handle_photo=True, is_popular=True),
    dict(name='Claude Opus 4.7', slug='claude-opus-4-7', model_name='claude-opus-4-7', cost_per_message=18, cost_kopecks=1800, order=24,
         description='Мощнейший Claude Opus для глубокого анализа, кода и длинных текстов.',
         handle_photo=True),
    # Gemini 3.x
    dict(name='Gemini 3 Pro', slug='gemini-3-pro', model_name='gemini-3.1-pro-preview', cost_per_message=6, cost_kopecks=600, order=33,
         description='Флагман Google нового поколения — огромный контекст и мультимодальность.',
         handle_photo=True, is_popular=True),
    dict(name='Gemini 3.5 Flash', slug='gemini-3-5-flash', model_name='gemini-3.5-flash', cost_per_message=2, cost_kopecks=150, order=34,
         description='Сверхбыстрый Gemini Flash последнего поколения.',
         handle_photo=True),
    # DeepSeek
    dict(name='DeepSeek V3.2', slug='deepseek-v3-2', model_name='deepseek-v3.2', cost_per_message=1, cost_kopecks=100, order=43,
         description='Новейшая версия DeepSeek V3 — умнее и эффективнее.',
         is_popular=True),
    # Qwen
    dict(name='Qwen3 Coder Plus', slug='qwen3-coder-plus', model_name='qwen3-coder-plus', cost_per_message=2, cost_kopecks=200, order=53,
         description='Специализированная модель Qwen для программирования — быстрая и точная в коде.',
         is_popular=True),
    # Grok
    dict(name='Grok 4.3', slug='grok-4-3', model_name='grok-4.3', cost_per_message=10, cost_kopecks=1000, order=63,
         description='Новейший флагман xAI с доступом к интернету в реальном времени.',
         is_popular=True),
    dict(name='Grok 4.1 Fast', slug='grok-4-1-fast', model_name='grok-4-1-fast', cost_per_message=2, cost_kopecks=200, order=64,
         description='Быстрая версия Grok 4.1 для оперативных ответов.'),
    # Прочие топ-модели
    dict(name='Kimi K2.5', slug='kimi-k2-5', model_name='kimi-k2.5', cost_per_message=2, cost_kopecks=200, order=72,
         description='Новейшая модель Moonshot AI с огромным контекстом.'),
    dict(name='GLM 4.6', slug='glm-4-6', model_name='glm-4.6', cost_per_message=1, cost_kopecks=100, order=73,
         description='Обновлённая модель Zhipu AI — умная и доступная.'),
    dict(name='MiniMax M2.5', slug='minimax-m2-5', model_name='MiniMax-M2.5', cost_per_message=2, cost_kopecks=150, order=74,
         description='Мощная модель MiniMax для разнообразных задач.'),
]

IMAGE_MODELS = [
    dict(name='DALL-E 3', slug='dall-e-3', model_name='dall-e-3', cost_per_message=8, cost_kopecks=800, order=1,
         description='Генерирует высококачественные изображения по текстовому описанию. Лучший выбор для иллюстраций.',
         config_key='dalle3', is_popular=True),
    dict(name='GPT Image 1', slug='gpt-image-1', model_name='gpt-image-1', cost_per_message=12, cost_kopecks=1200, order=2,
         description='Новейшая модель генерации изображений от OpenAI с превосходной детализацией.',
         config_key='gpt_image', is_popular=True),
    dict(name='GPT Image 2', slug='gpt-image-2', model_name='gpt-image-2', cost_per_message=15, cost_kopecks=1500, order=3,
         description='Флагманская модель OpenAI для генерации изображений — максимальное качество.',
         config_key='gpt_image'),
    dict(name='GPT Image 1 Mini', slug='gpt-image-1-mini', model_name='gpt-image-1-mini', cost_per_message=6, cost_kopecks=600, order=4,
         description='Компактная и быстрая версия GPT Image 1.',
         config_key='gpt_image'),
    dict(name='Flux 2 Pro', slug='flux-2-pro', model_name='flux-2-pro', cost_per_message=12, cost_kopecks=1200, order=10,
         description='Профессиональная модель Flux от Black Forest Labs. Фотореализм и точность.',
         config_key='flux', is_popular=True),
    dict(name='Flux 2 Max', slug='flux-2-max', model_name='flux-2-max', cost_per_message=15, cost_kopecks=1500, order=11,
         description='Максимальная версия Flux 2 — высочайшее качество генерации.',
         config_key='flux'),
    dict(name='Flux Kontext Pro', slug='flux-kontext-pro', model_name='flux-kontext-pro', cost_per_message=12, cost_kopecks=1200, order=12,
         description='Flux с контекстным пониманием — точно следует сложным описаниям.',
         config_key='flux'),
    dict(name='Flux Kontext Max', slug='flux-kontext-max', model_name='flux-kontext-max', cost_per_message=15, cost_kopecks=1500, order=13,
         description='Максимальный Flux Kontext для сложных многодетальных изображений.',
         config_key='flux'),
    dict(name='Flux 2 Flex', slug='flux-2-flex', model_name='flux-2-flex', cost_per_message=8, cost_kopecks=800, order=14,
         description='Гибкая и быстрая версия Flux 2 по доступной цене.',
         config_key='flux'),

    # ── Новые топ-модели изображений (2026) ──────────────────────────────────
    dict(name='GPT Image 1.5', slug='gpt-image-1-5', model_name='gpt-image-1.5', cost_per_message=13, cost_kopecks=1300, order=5,
         description='Обновлённая модель генерации изображений OpenAI с улучшенной детализацией.',
         config_key='gpt_image'),
    dict(name='Nano Banana (Gemini 2.5 Flash Image)', slug='gemini-2-5-flash-image', model_name='gemini-2.5-flash-image', cost_per_message=6, cost_kopecks=600, order=20,
         description='Быстрая модель генерации и редактирования изображений Google. Точное следование промту.',
         config_key='gemini_image', is_popular=True),
    dict(name='Gemini 3 Pro Image', slug='gemini-3-pro-image', model_name='gemini-3-pro-image', cost_per_message=12, cost_kopecks=1200, order=21,
         description='Флагманская модель генерации изображений Google нового поколения.',
         config_key='gemini_image', is_popular=True),
    dict(name='Seedream 4.5', slug='seedream-4-5', model_name='seedream-4-5-251128', cost_per_message=10, cost_kopecks=1000, order=30,
         description='Новейшая модель ByteDance для фотореалистичной генерации изображений.',
         config_key='seedream', is_popular=True),
    dict(name='Seedream 4.0', slug='seedream-4-0', model_name='seedream-4-0-250828', cost_per_message=8, cost_kopecks=800, order=31,
         description='Мощная модель генерации изображений ByteDance с высокой детализацией.',
         config_key='seedream'),
]


class Command(BaseCommand):
    help = 'Добавляет популярные модели laozhang.ai в базу данных'

    def _get_or_create_category(self, name, slug, icon, order):
        cat = Category.objects.filter(name=name).first()
        if cat:
            return cat
        # Если slug занят — добавляем суффикс
        base_slug = slug
        i = 1
        while Category.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{i}"
            i += 1
        cat = Category.objects.create(name=name, slug=slug, icon=icon, order=order)
        return cat

    def handle(self, *args, **options):
        # Показываем существующие категории
        self.stdout.write('Существующие категории:')
        for cat in Category.objects.all():
            self.stdout.write(f'  id={cat.id} slug={cat.slug} name={cat.name}')

        text_cat = self._get_or_create_category('Текст', 'text', 'fas fa-comment-dots', 1)
        image_cat = self._get_or_create_category('Изображения', 'images', 'fas fa-image', 2)

        self.stdout.write(f'Используем категории: "{text_cat.name}" (id={text_cat.id}), "{image_cat.name}" (id={image_cat.id})')

        # Добавляем текстовые модели
        self.stdout.write('\n=== Текстовые модели ===')
        for i, m in enumerate(TEXT_MODELS):
            config_key = m.pop('config_key', None)
            network, created = NeuralNetwork.objects.update_or_create(
                slug=m['slug'],
                defaults={
                    'name': m['name'],
                    'category': text_cat,
                    'model_name': m['model_name'],
                    'cost_per_message': m['cost_per_message'],
                    'cost_kopecks': m.get('cost_kopecks', m['cost_per_message'] * 100),
                    'order': m.get('order', i),
                    'description': m.get('description', ''),
                    'provider': 'openrouter',
                    'is_active': True,
                    'handle_photo': m.get('handle_photo', False),
                    'handle_text_files': True,
                    'is_popular': m.get('is_popular', False),
                }
            )
            status = 'создана' if created else 'обновлена'
            self.stdout.write(f'  {status}: {network.name} ({network.model_name})')

        # Добавляем модели изображений
        self.stdout.write('\n=== Модели изображений ===')
        for i, m in enumerate(IMAGE_MODELS):
            config_key = m.pop('config_key')
            config = dict(IMAGE_CONFIG[config_key])
            config['name'] = m['name']

            network, created = NeuralNetwork.objects.update_or_create(
                slug=m['slug'],
                defaults={
                    'name': m['name'],
                    'category': image_cat,
                    'model_name': m['model_name'],
                    'cost_per_message': m['cost_per_message'],
                    'cost_kopecks': m.get('cost_kopecks', m['cost_per_message'] * 100),
                    'order': m.get('order', i),
                    'description': m.get('description', ''),
                    'provider': 'fal-ai',
                    'config_json': config,
                    'is_active': True,
                    'is_popular': m.get('is_popular', False),
                }
            )
            status = 'создана' if created else 'обновлена'
            self.stdout.write(f'  {status}: {network.name} ({network.model_name})')

        total = len(TEXT_MODELS) + len(IMAGE_MODELS)
        self.stdout.write(f'\nГотово! Обработано моделей: {total}')
