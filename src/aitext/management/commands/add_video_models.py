"""
Видео-модели через apimart.ai.
Запуск: docker-compose exec web python manage.py add_video_models
Также деактивирует устаревшие видео-модели laozhang.ai.
"""
from django.core.management.base import BaseCommand
from aitext.models import Category, NeuralNetwork


VIDEO_CONFIG = {
    # Sora 2 — базовая модель: только 720p, duration 4/8/12/16/20 сек
    'sora2': {
        "name": "Sora 2",
        "api_defaults": {"duration": "4", "aspect_ratio": "16:9"},
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

    # Sora 2 Pro — выбор разрешения (720p / 1024p / 1080p)
    'sora2_pro': {
        "name": "Sora 2 Pro",
        "api_defaults": {"duration": "4", "aspect_ratio": "16:9", "resolution": "720p"},
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

    # Veo 3.1 Fast — длительность фиксирована 8 сек
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

    # Kling v2.6 — std/pro mode, аудио только в pro
    'kling_v26': {
        "name": "Kling v2.6",
        "api_defaults": {"mode": "std", "duration": "5", "aspect_ratio": "16:9", "audio": False},
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

    # Seedance 1.5 Pro — ByteDance через apimart, audio bool, camerafixed
    'seedance15pro': {
        "name": "Seedance 1.5 Pro",
        "api_defaults": {"duration": "5", "aspect_ratio": "16:9", "resolution": "720p", "audio": False},
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
                            {"value": "4:3", "label": "4:3 (традиционный)", "extra_cost": 0},
                            {"value": "3:4", "label": "3:4 (вертикальный)", "extra_cost": 0},
                            {"value": "21:9", "label": "21:9 (сверхширокий)", "extra_cost": 0},
                        ]
                    },
                    {
                        "name": "duration",
                        "type": "select",
                        "label": "Длительность",
                        "extra_cost": 0,
                        "options": [
                            {"value": "4", "label": "4 секунды", "extra_cost": 0},
                            {"value": "5", "label": "5 секунд", "extra_cost": 0},
                            {"value": "6", "label": "6 секунд", "extra_cost": 3},
                            {"value": "8", "label": "8 секунд", "extra_cost": 8},
                            {"value": "10", "label": "10 секунд", "extra_cost": 15},
                            {"value": "12", "label": "12 секунд", "extra_cost": 20},
                        ]
                    },
                    {
                        "name": "resolution",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "480p", "label": "480p (стандарт)", "extra_cost": 0},
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 0},
                            {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 10},
                        ]
                    },
                    {
                        "name": "audio",
                        "type": "checkbox",
                        "label": "Сгенерировать аудиодорожку",
                        "extra_cost": 0,
                    },
                    {
                        "name": "camerafixed",
                        "type": "checkbox",
                        "label": "Фиксированная камера",
                        "extra_cost": 0,
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {"output_type": "video", "video_api": "apimart"},
    },

    # Seedance 2.0 — ByteDance через apimart, generate_audio, size (не aspect_ratio)
    'seedance20': {
        "name": "Seedance 2.0",
        "api_defaults": {"duration": "5", "size": "16:9", "resolution": "720p", "generate_audio": False},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    {
                        "name": "size",
                        "type": "select",
                        "label": "Формат",
                        "extra_cost": 0,
                        "options": [
                            {"value": "16:9", "label": "16:9 (горизонталь)", "extra_cost": 0},
                            {"value": "9:16", "label": "9:16 (вертикаль)", "extra_cost": 0},
                            {"value": "1:1", "label": "1:1 (квадрат)", "extra_cost": 0},
                            {"value": "4:3", "label": "4:3 (традиционный)", "extra_cost": 0},
                            {"value": "3:4", "label": "3:4 (вертикальный)", "extra_cost": 0},
                            {"value": "21:9", "label": "21:9 (сверхширокий)", "extra_cost": 0},
                            {"value": "adaptive", "label": "Адаптивный", "extra_cost": 0},
                        ]
                    },
                    {
                        "name": "duration",
                        "type": "select",
                        "label": "Длительность",
                        "extra_cost": 0,
                        "options": [
                            {"value": "4", "label": "4 секунды", "extra_cost": 0},
                            {"value": "5", "label": "5 секунд", "extra_cost": 0},
                            {"value": "6", "label": "6 секунд", "extra_cost": 3},
                            {"value": "8", "label": "8 секунд", "extra_cost": 8},
                            {"value": "10", "label": "10 секунд", "extra_cost": 15},
                            {"value": "12", "label": "12 секунд", "extra_cost": 20},
                            {"value": "15", "label": "15 секунд", "extra_cost": 30},
                        ]
                    },
                    {
                        "name": "resolution",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "480p", "label": "480p (стандарт)", "extra_cost": 0},
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 0},
                            {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 10},
                        ]
                    },
                    {
                        "name": "generate_audio",
                        "type": "checkbox",
                        "label": "Сгенерировать аудиодорожку",
                        "extra_cost": 0,
                    },
                ]
            }]
        },
        "constraints": {},
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
    dict(
        name='Seedance 1.5 Pro',
        slug='seedance-1-5-pro',
        model_name='doubao-seedance-1-5-pro',
        cost_per_message=35,
        order=6,
        description='Генерация видео от ByteDance. Поддержка аудио, фиксированной камеры и 6 форматов кадра.',
        config_key='seedance15pro',
        is_popular=True,
    ),
    dict(
        name='Seedance 2.0',
        slug='seedance-2-0',
        model_name='doubao-seedance-2.0',
        cost_per_message=45,
        order=7,
        description='Новейшая модель ByteDance Seedance 2.0. Длительность до 15 сек, аудиодорожка, адаптивный формат.',
        config_key='seedance20',
        is_popular=True,
    ),
]


class Command(BaseCommand):
    help = 'Добавляет видео-модели apimart.ai и деактивирует устаревшие laozhang-модели'

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
        active_slugs = []
        for m in VIDEO_MODELS:
            config_key = m.pop('config_key')
            config = dict(VIDEO_CONFIG[config_key])
            config['name'] = m['name']
            active_slugs.append(m['slug'])

            network, created = NeuralNetwork.objects.get_or_create(
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
            status = self.style.SUCCESS('создана') if created else 'уже есть (не тронута)'
            self.stdout.write(f'  {status}: {network.name} ({network.model_name})')

        # Деактивируем старые laozhang-видеомодели (не входят в наш список)
        self.stdout.write('\n=== Деактивация устаревших laozhang-моделей ===')
        old_models = NeuralNetwork.objects.filter(
            category=video_cat,
            is_active=True,
        ).exclude(slug__in=active_slugs)

        count = old_models.count()
        if count:
            names = list(old_models.values_list('name', flat=True))
            old_models.update(is_active=False)
            for name in names:
                self.stdout.write(self.style.WARNING(f'  деактивирована: {name}'))
            self.stdout.write(self.style.WARNING(f'Деактивировано: {count} моделей'))
        else:
            self.stdout.write('  Устаревших моделей не найдено')

        self.stdout.write(f'\nГотово! Активных видео-моделей: {len(VIDEO_MODELS)}')
        self.stdout.write('Убедись что APIMART_API_KEY задан в .env!')
