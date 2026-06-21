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
                ]
            }]
        },
        "constraints": {},
        "metadata": {"requires_input_images": False}
    },
}


TEXT_MODELS = [
    # OpenAI GPT
    dict(name='GPT-4o', slug='gpt-4o', model_name='gpt-4o', cost_per_message=20, order=1,
         description='Флагманская мультимодальная модель OpenAI. Понимает текст, изображения и аудио.',
         handle_photo=True, is_popular=True),
    dict(name='GPT-4o Mini', slug='gpt-4o-mini', model_name='gpt-4o-mini', cost_per_message=5, order=2,
         description='Быстрая и экономичная версия GPT-4o для повседневных задач.',
         handle_photo=True, is_popular=True),
    dict(name='GPT-4.1', slug='gpt-4-1', model_name='gpt-4.1', cost_per_message=20, order=3,
         description='Обновлённая версия GPT-4 с улучшенными возможностями для кода и анализа.',
         handle_photo=True),
    dict(name='GPT-4.1 Mini', slug='gpt-4-1-mini', model_name='gpt-4.1-mini', cost_per_message=5, order=4,
         description='Компактная версия GPT-4.1 — быстро и дёшево.',
         handle_photo=True),
    dict(name='GPT-5', slug='gpt-5', model_name='gpt-5', cost_per_message=50, order=5,
         description='Самая мощная модель OpenAI нового поколения.',
         handle_photo=True, is_popular=True),
    dict(name='ChatGPT-4o', slug='chatgpt-4o-latest', model_name='chatgpt-4o-latest', cost_per_message=20, order=6,
         description='Последняя версия ChatGPT-4o, используемая в ChatGPT.',
         handle_photo=True),
    # OpenAI Reasoning
    dict(name='o3', slug='o3', model_name='o3', cost_per_message=40, order=10,
         description='Мощная модель рассуждений OpenAI для сложных задач: математика, наука, логика.'),
    dict(name='o4 Mini', slug='o4-mini', model_name='o4-mini', cost_per_message=15, order=11,
         description='Быстрая модель рассуждений OpenAI. Отлично справляется с кодингом и математикой.',
         is_popular=True),
    dict(name='o1', slug='o1', model_name='o1', cost_per_message=30, order=12,
         description='Классическая reasoning-модель OpenAI с глубоким анализом.'),
    dict(name='o3 Mini', slug='o3-mini', model_name='o3-mini', cost_per_message=10, order=13,
         description='Компактная reasoning-модель для логических и математических задач.'),
    # Claude
    dict(name='Claude Sonnet 4.6', slug='claude-sonnet-4-6', model_name='claude-sonnet-4-6', cost_per_message=20, order=20,
         description='Последний Claude Sonnet — баланс интеллекта и скорости от Anthropic.',
         handle_photo=True, is_popular=True),
    dict(name='Claude Opus 4.8', slug='claude-opus-4-8', model_name='claude-opus-4-8', cost_per_message=50, order=21,
         description='Самый мощный Claude. Для сложного анализа, написания и кода.',
         handle_photo=True),
    dict(name='Claude Haiku 4.5', slug='claude-haiku-4-5', model_name='claude-haiku-4-5-20251001', cost_per_message=5, order=22,
         description='Самый быстрый и дешёвый Claude для простых задач.',
         handle_photo=True),
    dict(name='Claude Sonnet 4.5', slug='claude-sonnet-4-5', model_name='claude-sonnet-4-5-20250929', cost_per_message=15, order=23,
         description='Надёжный Claude Sonnet предыдущего поколения.',
         handle_photo=True),
    # Gemini
    dict(name='Gemini 2.5 Flash', slug='gemini-2-5-flash', model_name='gemini-2.5-flash', cost_per_message=5, order=30,
         description='Быстрая мультимодальная модель Google с поддержкой длинного контекста.',
         handle_photo=True, is_popular=True),
    dict(name='Gemini 2.5 Pro', slug='gemini-2-5-pro', model_name='gemini-2.5-pro', cost_per_message=20, order=31,
         description='Флагманская модель Google с огромным контекстом и мультимодальностью.',
         handle_photo=True),
    dict(name='Gemini 3 Flash', slug='gemini-3-flash', model_name='gemini-3-flash-preview', cost_per_message=5, order=32,
         description='Новейший Gemini Flash — быстрый и умный.',
         handle_photo=True),
    # DeepSeek
    dict(name='DeepSeek V3', slug='deepseek-v3', model_name='deepseek-v3', cost_per_message=5, order=40,
         description='Мощная открытая модель DeepSeek. Отлично справляется с кодом и аналитикой.',
         is_popular=True),
    dict(name='DeepSeek R1', slug='deepseek-r1', model_name='deepseek-r1', cost_per_message=10, order=41,
         description='Reasoning-модель DeepSeek — конкурент o1 с открытым исходным кодом.',
         is_popular=True),
    dict(name='DeepSeek V3.1', slug='deepseek-v3-1', model_name='deepseek-v3.1', cost_per_message=5, order=42,
         description='Обновлённая версия DeepSeek V3 с улучшенными возможностями.'),
    # Qwen
    dict(name='Qwen 3 235B', slug='qwen3-235b', model_name='qwen3-235b-a22b', cost_per_message=15, order=50,
         description='Флагманская открытая модель Alibaba с 235 млрд параметров.'),
    dict(name='Qwen 3 Max', slug='qwen3-max', model_name='qwen3-max', cost_per_message=10, order=51,
         description='Мощная модель Qwen 3 для сложных задач.'),
    dict(name='QwQ Plus', slug='qwq-plus', model_name='qwq-plus', cost_per_message=10, order=52,
         description='Reasoning-модель Qwen с глубоким анализом задач.'),
    # Grok
    dict(name='Grok 4', slug='grok-4', model_name='grok-4', cost_per_message=40, order=60,
         description='Новейшая флагманская модель xAI. Доступ к интернету в реальном времени.',
         is_popular=True),
    dict(name='Grok 3', slug='grok-3', model_name='grok-3', cost_per_message=20, order=61,
         description='Мощная модель xAI с обширными знаниями и аналитикой.'),
    dict(name='Grok 4 Fast', slug='grok-4-fast', model_name='grok-4-fast', cost_per_message=15, order=62,
         description='Быстрая версия Grok 4 для оперативных ответов.'),
    # Other
    dict(name='Kimi K2', slug='kimi-k2', model_name='kimi-k2', cost_per_message=10, order=70,
         description='Мощная модель Moonshot AI с огромным контекстом в 128k токенов.'),
    dict(name='GLM 4.5', slug='glm-4-5', model_name='glm-4.5', cost_per_message=5, order=71,
         description='Умная китайская модель от Zhipu AI для разнообразных задач.'),
    dict(name='GPT-3.5 Turbo', slug='gpt-3-5-turbo', model_name='gpt-3.5-turbo', cost_per_message=3, order=80,
         description='Классическая быстрая модель OpenAI. Идеально для простых чатов.'),
]

IMAGE_MODELS = [
    dict(name='DALL-E 3', slug='dall-e-3', model_name='dall-e-3', cost_per_message=20, order=1,
         description='Генерирует высококачественные изображения по текстовому описанию. Лучший выбор для иллюстраций.',
         config_key='dalle3', is_popular=True),
    dict(name='GPT Image 1', slug='gpt-image-1', model_name='gpt-image-1', cost_per_message=30, order=2,
         description='Новейшая модель генерации изображений от OpenAI с превосходной детализацией.',
         config_key='gpt_image', is_popular=True),
    dict(name='GPT Image 2', slug='gpt-image-2', model_name='gpt-image-2', cost_per_message=40, order=3,
         description='Флагманская модель OpenAI для генерации изображений — максимальное качество.',
         config_key='gpt_image'),
    dict(name='GPT Image 1 Mini', slug='gpt-image-1-mini', model_name='gpt-image-1-mini', cost_per_message=15, order=4,
         description='Компактная и быстрая версия GPT Image 1.',
         config_key='gpt_image'),
    dict(name='Flux 2 Pro', slug='flux-2-pro', model_name='flux-2-pro', cost_per_message=25, order=10,
         description='Профессиональная модель Flux от Black Forest Labs. Фотореализм и точность.',
         config_key='flux', is_popular=True),
    dict(name='Flux 2 Max', slug='flux-2-max', model_name='flux-2-max', cost_per_message=30, order=11,
         description='Максимальная версия Flux 2 — высочайшее качество генерации.',
         config_key='flux'),
    dict(name='Flux Kontext Pro', slug='flux-kontext-pro', model_name='flux-kontext-pro', cost_per_message=30, order=12,
         description='Flux с контекстным пониманием — точно следует сложным описаниям.',
         config_key='flux'),
    dict(name='Flux Kontext Max', slug='flux-kontext-max', model_name='flux-kontext-max', cost_per_message=35, order=13,
         description='Максимальный Flux Kontext для сложных многодетальных изображений.',
         config_key='flux'),
    dict(name='Flux 2 Flex', slug='flux-2-flex', model_name='flux-2-flex', cost_per_message=15, order=14,
         description='Гибкая и быстрая версия Flux 2 по доступной цене.',
         config_key='flux'),
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
