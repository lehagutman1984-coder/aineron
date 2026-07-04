"""
Добавляет новые модели laozhang.ai: Seedream, Gemini Image, GPT Image 1.5,
и свежие текстовые модели (DeepSeek V3.2/V4, Gemini 3.x, GLM 5, GPT-5.x, Grok 4.3 и др.)
Запуск: docker-compose exec web python manage.py add_new_models
"""
from django.core.management.base import BaseCommand
from aitext.models import Category, NeuralNetwork


IMAGE_CONFIG = {
    # Seedream — ByteDance, высокое художественное качество, конкурент Midjourney
    # minimal_params=True: Seedream не принимает size/n — только model+prompt
    'seedream': {
        "name": "Seedream",
        "api_defaults": {},
        "ui_settings": {"sections": []},
        "constraints": {},
        "metadata": {"requires_input_images": False, "minimal_params": True, "output_type": "image"}
    },

    # Gemini Image — Google Imagen, фотореализм и художественный стиль
    # minimal_params=True: тестируем без size/n — уточним после первого теста
    'gemini_image': {
        "name": "Gemini Image",
        "api_defaults": {},
        "ui_settings": {"sections": []},
        "constraints": {},
        "metadata": {"requires_input_images": False, "minimal_params": True, "output_type": "image"}
    },

    # GPT Image — OpenAI, используем существующий конфиг
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
        "metadata": {"requires_input_images": False, "output_type": "image"}
    },
}


NEW_IMAGE_MODELS = [
    # Seedream 5.0 — флагман ByteDance (январь 2026), конкурент Midjourney
    dict(name='Seedream 5.0', slug='seedream-5-0', model_name='seedream-5-0-260128',
         cost_per_message=40, order=20,
         description='Флагманская модель генерации изображений от ByteDance. Художественное качество уровня Midjourney.',
         config_key='seedream', is_popular=True),
    # Seedream 4.5 — ноябрь 2025
    dict(name='Seedream 4.5', slug='seedream-4-5', model_name='seedream-4-5-251128',
         cost_per_message=30, order=21,
         description='Seedream 4.5 — улучшенная версия генератора изображений от ByteDance.',
         config_key='seedream'),
    # Seedream 4.0 — август 2025
    dict(name='Seedream 4.0', slug='seedream-4-0', model_name='seedream-4-0-250828',
         cost_per_message=25, order=22,
         description='Seedream 4.0 — высококачественная генерация изображений от ByteDance.',
         config_key='seedream'),

    # Gemini image models — Google Imagen / Gemini 3
    dict(name='Gemini 3.1 Flash Image', slug='gemini-3-1-flash-image', model_name='gemini-3.1-flash-image',
         cost_per_message=20, order=30,
         description='Быстрая генерация изображений через Gemini 3.1 Flash. Фотореализм и точность.',
         config_key='gemini_image', is_popular=True),
    dict(name='Gemini 3 Pro Image', slug='gemini-3-pro-image', model_name='gemini-3-pro-image',
         cost_per_message=35, order=31,
         description='Флагманская модель Google для генерации изображений. Максимальное качество Imagen.',
         config_key='gemini_image'),
    dict(name='Gemini 2.5 Flash Image', slug='gemini-2-5-flash-image', model_name='gemini-2.5-flash-image',
         cost_per_message=15, order=32,
         description='Доступная генерация изображений через Gemini 2.5 Flash.',
         config_key='gemini_image'),

    # GPT Image 1.5 — промежуточная версия
    dict(name='GPT Image 1.5', slug='gpt-image-1-5', model_name='gpt-image-1.5',
         cost_per_message=35, order=5,
         description='Улучшенная версия GPT Image с повышенной детализацией и точностью.',
         config_key='gpt_image'),
]


NEW_TEXT_MODELS = [
    # DeepSeek V3.2 и V4
    dict(name='DeepSeek V3.2', slug='deepseek-v3-2', model_name='deepseek-v3.2', cost_per_message=5, order=43,
         description='Обновлённый DeepSeek V3 с улучшенными способностями рассуждения и кода.'),
    dict(name='DeepSeek V4 Flash', slug='deepseek-v4-flash', model_name='deepseek-v4-flash', cost_per_message=5, order=44,
         description='Быстрая версия DeepSeek V4 для оперативных ответов.'),
    dict(name='DeepSeek V4 Pro', slug='deepseek-v4-pro', model_name='deepseek-v4-pro', cost_per_message=15, order=45,
         description='Мощный DeepSeek V4 Pro для сложного анализа и кода.'),

    # Gemini новые версии
    dict(name='Gemini 3.5 Flash', slug='gemini-3-5-flash', model_name='gemini-3.5-flash', cost_per_message=5, order=33,
         description='Новейший быстрый Gemini с расширенными возможностями.',
         handle_photo=True),
    dict(name='Gemini 3.1 Pro', slug='gemini-3-1-pro', model_name='gemini-3.1-pro-preview', cost_per_message=25, order=34,
         description='Флагманский Gemini 3.1 Pro с глубоким мультимодальным пониманием.',
         handle_photo=True),

    # GLM новые версии
    dict(name='GLM 5', slug='glm-5', model_name='glm-5', cost_per_message=10, order=72,
         description='Новейший флагман Zhipu AI пятого поколения.'),
    dict(name='GLM 4.6', slug='glm-4-6', model_name='glm-4.6', cost_per_message=7, order=73,
         description='Мощная мультимодальная модель Zhipu AI.'),

    # GPT-5 расширение
    dict(name='GPT-5 Mini', slug='gpt-5-mini', model_name='gpt-5-mini', cost_per_message=15, order=7,
         description='Компактный GPT-5 — умный и быстрый для повседневных задач.',
         handle_photo=True, is_popular=True),
    dict(name='GPT-5 Pro', slug='gpt-5-pro', model_name='gpt-5-pro', cost_per_message=60, order=8,
         description='Самый мощный GPT-5 Pro для сложнейших профессиональных задач.',
         handle_photo=True),
    dict(name='GPT-5.1', slug='gpt-5-1', model_name='gpt-5.1', cost_per_message=50, order=9,
         description='GPT-5.1 — улучшенное поколение GPT-5 с расширенными возможностями.',
         handle_photo=True),

    # Grok 4.3
    dict(name='Grok 4.3', slug='grok-4-3', model_name='grok-4.3', cost_per_message=45, order=63,
         description='Передовой Grok 4.3 от xAI с доступом к реальным данным.',
         is_popular=True),

    # Kimi новые
    dict(name='Kimi K2.5', slug='kimi-k2-5', model_name='kimi-k2.5', cost_per_message=10, order=74,
         description='Усовершенствованный Kimi K2.5 с расширенным контекстом.'),
    dict(name='Kimi K2.6', slug='kimi-k2-6', model_name='kimi-k2.6', cost_per_message=12, order=75,
         description='Последняя версия Kimi K2 от Moonshot AI.'),

    # Qwen 3.5
    dict(name='Qwen 3.5 Flash', slug='qwen3-5-flash', model_name='qwen3.5-flash', cost_per_message=3, order=53,
         description='Сверхбыстрый и дешёвый Qwen 3.5 Flash.'),
    dict(name='Qwen 3.5 Plus', slug='qwen3-5-plus', model_name='qwen3.5-plus', cost_per_message=8, order=54,
         description='Улучшенный Qwen 3.5 Plus с расширенными возможностями.'),

    # MiniMax
    dict(name='MiniMax M2.7', slug='minimax-m2-7', model_name='MiniMax-M2.7', cost_per_message=15, order=76,
         description='Мощная модель MiniMax M2.7 с поддержкой длинного контекста.'),
    dict(name='MiniMax M2.5', slug='minimax-m2-5', model_name='MiniMax-M2.5', cost_per_message=10, order=77,
         description='Флагман предыдущего поколения MiniMax с высоким качеством.'),
]


class Command(BaseCommand):
    help = 'Добавляет новые модели: Seedream, Gemini Image, GPT Image 1.5, DeepSeek V4, Gemini 3.x, Grok 4.3 и др.'

    def _get_or_create_category(self, name, slug, icon, order):
        cat = Category.objects.filter(name=name).first()
        if cat:
            return cat
        base_slug = slug
        i = 1
        while Category.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{i}"
            i += 1
        return Category.objects.create(name=name, slug=slug, icon=icon, order=order)

    def handle(self, *args, **options):
        text_cat = self._get_or_create_category('Текст', 'text', 'fas fa-comment-dots', 1)
        image_cat = self._get_or_create_category('Изображения', 'images', 'fas fa-image', 2)

        # --- Изображения ---
        self.stdout.write('\n=== Новые модели изображений ===')
        for m in NEW_IMAGE_MODELS:
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
                    'order': m.get('order', 99),
                    'description': m.get('description', ''),
                    'provider': 'fal-ai',
                    'config_json': config,
                    'is_active': True,
                    'is_popular': m.get('is_popular', False),
                }
            )
            status = 'создана' if created else 'обновлена'
            self.stdout.write(f'  {status}: {network.name} ({network.model_name})')

        # --- Текст ---
        self.stdout.write('\n=== Новые текстовые модели ===')
        for m in NEW_TEXT_MODELS:
            network, created = NeuralNetwork.objects.update_or_create(
                slug=m['slug'],
                defaults={
                    'name': m['name'],
                    'category': text_cat,
                    'model_name': m['model_name'],
                    'cost_per_message': m['cost_per_message'],
                    'order': m.get('order', 99),
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

        total = len(NEW_IMAGE_MODELS) + len(NEW_TEXT_MODELS)
        self.stdout.write(f'\nГотово! Обработано: {total} моделей')
        self.stdout.write('\nДалее:')
        self.stdout.write('  1. Проверьте модели в Django Admin')
        self.stdout.write('  2. Загрузите аватары: python manage.py download_avatars')
        self.stdout.write('  3. Протестируйте: сделайте запрос к seedream-5-0, gemini-3.1-flash-image')
