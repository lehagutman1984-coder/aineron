"""
Видео-модели через apimart.ai.
Запуск: docker-compose exec web python manage.py add_video_models
"""
from django.core.management.base import BaseCommand
from aitext.models import Category, NeuralNetwork


VIDEO_CONFIG = {
    # Sora 2 — базовая модель: только 720p, duration 4/8/12/16/20 сек
    'sora2': {
        "name": "Sora 2",
        "api_defaults": {"duration": 4, "aspect_ratio": "16:9"},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    {
                        "name": "aspect_ratio",
                        "type": "select",
                        "label": "Формат",
                        "extra_cost": 0,
                        "options": [
                            {"value": "16:9", "label": "16:9 (горизонталь)", "extra_cost": 0},
                            {"value": "9:16", "label": "9:16 (вертикаль)", "extra_cost": 0},
                        ]
                    },
                    {
                        "name": "duration",
                        "type": "select",
                        "label": "Длительность",
                        "extra_cost": 0,
                        "options": [
                            {"value": "4", "label": "4 секунды", "extra_cost": 0},
                            {"value": "8", "label": "8 секунд", "extra_cost": 5},
                            {"value": "12", "label": "12 секунд", "extra_cost": 15},
                            {"value": "16", "label": "16 секунд", "extra_cost": 25},
                            {"value": "20", "label": "20 секунд", "extra_cost": 35},
                        ]
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {"output_type": "video", "video_api": "apimart"},
    },

    # Sora 2 Pro — Pro: выбор разрешения (720p / 1024p / 1080p)
    'sora2_pro': {
        "name": "Sora 2 Pro",
        "api_defaults": {"duration": 4, "aspect_ratio": "16:9", "resolution": "720p"},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    {
                        "name": "aspect_ratio",
                        "type": "select",
                        "label": "Формат",
                        "extra_cost": 0,
                        "options": [
                            {"value": "16:9", "label": "16:9 (горизонталь)", "extra_cost": 0},
                            {"value": "9:16", "label": "9:16 (вертикаль)", "extra_cost": 0},
                        ]
                    },
                    {
                        "name": "duration",
                        "type": "select",
                        "label": "Длительность",
                        "extra_cost": 0,
                        "options": [
                            {"value": "4", "label": "4 секунды", "extra_cost": 0},
                            {"value": "8", "label": "8 секунд", "extra_cost": 5},
                            {"value": "12", "label": "12 секунд", "extra_cost": 15},
                            {"value": "16", "label": "16 секунд", "extra_cost": 25},
                            {"value": "20", "label": "20 секунд", "extra_cost": 35},
                        ]
                    },
                    {
                        "name": "resolution",
                        "type": "select",
                        "label": "Разрешение",
                        "extra_cost": 0,
                        "options": [
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 0},
                            {"value": "1024p", "label": "1024p", "extra_cost": 10},
                            {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 15},
                        ]
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {"output_type": "video", "video_api": "apimart"},
    },

    # Veo 3.1 Fast — длительность фиксирована 8 сек, resolution 720p/1080p/4k
    'veo3_fast': {
        "name": "Veo 3.1 Fast",
        "api_defaults": {"duration": 8, "aspect_ratio": "16:9", "resolution": "720p"},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео (8 сек, фиксировано)",
                "fields": [
                    {
                        "name": "aspect_ratio",
                        "type": "select",
                        "label": "Формат",
                        "extra_cost": 0,
                        "options": [
                            {"value": "16:9", "label": "16:9 (горизонталь)", "extra_cost": 0},
                            {"value": "9:16", "label": "9:16 (вертикаль)", "extra_cost": 0},
                        ]
                    },
                    {
                        "name": "resolution",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 0},
                            {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 10},
                            {"value": "4k", "label": "4K (Ultra HD)", "extra_cost": 30},
                        ]
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {"output_type": "video", "video_api": "apimart"},
    },

    # Veo 3.1 Quality — те же опции, другое качество по умолчанию
    'veo3_quality': {
        "name": "Veo 3.1",
        "api_defaults": {"duration": 8, "aspect_ratio": "16:9", "resolution": "1080p"},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео (8 сек, фиксировано)",
                "fields": [
                    {
                        "name": "aspect_ratio",
                        "type": "select",
                        "label": "Формат",
                        "extra_cost": 0,
                        "options": [
                            {"value": "16:9", "label": "16:9 (горизонталь)", "extra_cost": 0},
                            {"value": "9:16", "label": "9:16 (вертикаль)", "extra_cost": 0},
                        ]
                    },
                    {
                        "name": "resolution",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 0},
                            {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 0},
                            {"value": "4k", "label": "4K (Ultra HD)", "extra_cost": 20},
                        ]
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {"output_type": "video", "video_api": "apimart"},
    },

    'kling_v26': {
        "name": "Kling v2.6",
        "api_defaults": {"mode": "std", "duration": 5, "aspect_ratio": "16:9", "audio": False},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    {
                        "name": "aspect_ratio",
                        "type": "select",
                        "label": "Формат",
                        "extra_cost": 0,
                        "options": [
                            {"value": "16:9", "label": "16:9 (горизонталь)", "extra_cost": 0},
                            {"value": "9:16", "label": "9:16 (вертикаль)", "extra_cost": 0},
                            {"value": "1:1", "label": "1:1 (квадрат)", "extra_cost": 0},
                        ]
                    },
                    {
                        "name": "duration",
                        "type": "select",
                        "label": "Длительность",
                        "extra_cost": 0,
                        "options": [
                            {"value": "5", "label": "5 секунд", "extra_cost": 0},
                            {"value": "10", "label": "10 секунд", "extra_cost": 8},
                        ]
                    },
                    {
                        "name": "mode",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "std", "label": "720p (стандарт)", "extra_cost": 0},
                            {"value": "pro", "label": "1080p (профессионал)", "extra_cost": 5},
                        ]
                    },
                    {
                        "name": "audio",
                        "type": "checkbox",
                        "label": "Сгенерировать аудио (требует режим 1080p)",
                        "extra_cost": 0,
                    },
                    {
                        "name": "negative_prompt",
                        "type": "text",
                        "label": "Negative prompt",
                        "extra_cost": 0,
                        "max_length": 2500,
                    },
                ]
            }]
        },
        "constraints": {"max_negative_prompt_length": 2500},
        "metadata": {"output_type": "video", "video_api": "apimart"},
    },
}


VIDEO_MODELS = [
    dict(
        name='Sora 2',
        slug='sora-character',
        model_name='sora-2',
        cost_per_message=60,
        order=1,
        description='Генерация видео от OpenAI. Создаёт реалистичные короткие видеоролики по текстовому описанию.',
        config_key='sora2',
        is_popular=True,
    ),
    dict(
        name='Sora 2 Pro',
        slug='sora-2-character',
        model_name='sora-2-pro',
        cost_per_message=100,
        order=2,
        description='Продвинутая версия Sora 2 от OpenAI — выбор разрешения до 1080p, максимальная детализация.',
        config_key='sora2_pro',
        is_popular=False,
    ),
    dict(
        name='Veo 3.1 Fast',
        slug='veo-3-1-fast',
        model_name='veo3.1-fast',
        cost_per_message=50,
        order=3,
        description='Быстрая генерация видео от Google DeepMind. Высокое качество движения и деталей.',
        config_key='veo3_fast',
        is_popular=True,
    ),
    dict(
        name='Veo 3.1',
        slug='veo-3-1',
        model_name='veo3.1-quality',
        cost_per_message=100,
        order=4,
        description='Полное качество Veo 3.1 от Google DeepMind. Максимальная детализация и фотореализм.',
        config_key='veo3_quality',
        is_popular=False,
    ),
    dict(
        name='Kling v2.6',
        slug='kling-v26',
        model_name='kling-v2-6',
        cost_per_message=40,
        order=5,
        description='Генерация видео от Kuaishou с поддержкой аудиосопровождения. Быстрый и качественный результат.',
        config_key='kling_v26',
        is_popular=True,
    ),
]


class Command(BaseCommand):
    help = 'Добавляет видео-модели apimart.ai в базу данных'

    def handle(self, *args, **options):
        video_cat, created = Category.objects.get_or_create(
            slug='video',
            defaults={'name': 'Видео', 'icon': 'fas fa-video', 'order': 3},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Создана категория "Видео" (id={video_cat.id})'))
        else:
            self.stdout.write(f'Категория "Видео" уже есть (id={video_cat.id})')

        self.stdout.write('\n=== Видео-модели (apimart.ai) ===')
        for m in VIDEO_MODELS:
            config_key = m.pop('config_key')
            config = dict(VIDEO_CONFIG[config_key])
            config['name'] = m['name']

            network, created = NeuralNetwork.objects.update_or_create(
                slug=m['slug'],
                defaults={
                    'name': m['name'],
                    'category': video_cat,
                    'model_name': m['model_name'],
                    'cost_per_message': m['cost_per_message'],
                    'order': m.get('order', 0),
                    'description': m.get('description', ''),
                    'provider': 'fal-ai',
                    'config_json': config,
                    'is_active': True,
                    'is_popular': m.get('is_popular', False),
                }
            )
            status = self.style.SUCCESS('создана') if created else 'обновлена'
            self.stdout.write(f'  {status}: {network.name} ({network.model_name})')

        self.stdout.write(f'\nГотово! Обработано видео-моделей: {len(VIDEO_MODELS)}')
        self.stdout.write('Проверь в /admin -> NeuralNetworks что модели активны.')
        self.stdout.write('Убедись что APIMART_API_KEY задан в .env!')
