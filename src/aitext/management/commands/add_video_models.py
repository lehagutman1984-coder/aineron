"""
Управление видео-моделями на laozhang.ai.
Запуск: docker-compose exec web python manage.py add_video_models
"""
from django.core.management.base import BaseCommand
from aitext.models import Category, NeuralNetwork


# ── Конфиги для video API (через client.images.generate) ─────────────────────

VIDEO_CONFIG = {
    'sora': {
        "name": "Sora",
        "api_defaults": {"size": "1280x720", "n": 1},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    {
                        "name": "size",
                        "type": "select",
                        "label": "Разрешение",
                        "extra_cost": 0,
                        "options": [
                            {"value": "1280x720", "label": "1280×720 (HD горизонталь)", "extra_cost": 0},
                            {"value": "720x1280", "label": "720×1280 (HD вертикаль)", "extra_cost": 0},
                            {"value": "1080x1080", "label": "1080×1080 (квадрат)", "extra_cost": 0},
                        ]
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {"output_type": "video", "requires_input_images": False},
    },
    'veo': {
        "name": "Veo",
        "api_defaults": {"size": "1280x720", "n": 1},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    {
                        "name": "size",
                        "type": "select",
                        "label": "Разрешение",
                        "extra_cost": 0,
                        "options": [
                            {"value": "1280x720", "label": "1280×720 (HD горизонталь)", "extra_cost": 0},
                            {"value": "720x1280", "label": "720×1280 (HD вертикаль)", "extra_cost": 0},
                            {"value": "1920x1080", "label": "1920×1080 (Full HD)", "extra_cost": 5},
                            {"value": "1080x1920", "label": "1080×1920 (Full HD вертикаль)", "extra_cost": 5},
                        ]
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {"output_type": "video", "requires_input_images": False},
    },
}

# ── Список видео-моделей для добавления ───────────────────────────────────────
# model_name — точное имя из all_models_laozhang.ai.txt

VIDEO_MODELS = [
    dict(
        name='Sora',
        slug='sora-character',
        model_name='sora-character',
        cost_per_message=60,
        order=1,
        description='Генерация видео от OpenAI. Создаёт реалистичные короткие видеоролики по текстовому описанию.',
        config_key='sora',
        is_popular=True,
    ),
    dict(
        name='Sora 2',
        slug='sora-2-character',
        model_name='sora-2-character',
        cost_per_message=80,
        order=2,
        description='Новая версия Sora от OpenAI — улучшенная детализация и движение персонажей.',
        config_key='sora',
        is_popular=False,
    ),
    dict(
        name='Veo 3.1 Fast',
        slug='veo-3-1-fast',
        model_name='veo-3.1-fast-generate-preview',
        cost_per_message=50,
        order=3,
        description='Быстрая генерация видео от Google DeepMind. Высокое качество движения и деталей.',
        config_key='veo',
        is_popular=True,
    ),
]


class Command(BaseCommand):
    help = 'Добавляет видео-модели laozhang.ai в базу данных'

    def handle(self, *args, **options):
        # Получаем или создаём категорию "Видео"
        video_cat, created = Category.objects.get_or_create(
            slug='video',
            defaults={'name': 'Видео', 'icon': 'fas fa-video', 'order': 3},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Создана категория "Видео" (id={video_cat.id})'))
        else:
            self.stdout.write(f'Категория "Видео" уже есть (id={video_cat.id})')

        self.stdout.write('\n=== Видео-модели ===')
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
        self.stdout.write('Проверь в /admin → NeuralNetworks что модели активны.')
