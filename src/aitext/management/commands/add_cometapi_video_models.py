"""
Добавляет Veo 3 и Veo 3 Fast через CometAPI — единственный провайдер, у
которого они вообще продаются (apimart даёт только 3.1). Контракт
подтверждён живым тестовым вызовом 2026-09-05 (POST /v1/videos, multipart,
GET /v1/videos/{id} для поллинга) — см. generate_video_cometapi() в
aitext/fal_utils.py.

Поддерживает и text-to-video, и image-to-video (одно референс-фото —
CometAPI принимает его файлом через input_reference, не ссылкой; скачивание
и переотправка — _download_file_for_upload() в fal_utils.py).

Повторный запуск обновляет config_json существующих записей (is_active не
трогает) — используйте для докатки этого флага/цен без создания дублей.

Запуск: docker-compose exec web python manage.py add_cometapi_video_models
"""
from django.core.management.base import BaseCommand
from aitext.models import Category, NeuralNetwork


def _aspect_field():
    return {
        "name": "aspect_ratio", "type": "select", "label": "Формат", "extra_cost": 0,
        "options": [
            {"value": "16:9", "label": "16:9 (горизонталь)", "extra_cost": 0},
            {"value": "9:16", "label": "9:16 (вертикаль)", "extra_cost": 0},
        ],
    }


MODELS = [
    {
        'slug': 'veo-3', 'name': 'Veo 3', 'model_name': 'veo3',
        'description': 'Полная версия Veo 3 от Google DeepMind. Нативный синхронный звук, до 4K. Через CometAPI — у Apimart этой версии нет, только 3.1.',
        'cost_kopecks': 26880,  # 268.80₽ = $0.32/сек × 105 × 8 сек (CometAPI, подтверждено живым вызовом)
        'res_4k_delta': 134,
        'order': 60,
    },
    {
        'slug': 'veo-3-fast', 'name': 'Veo 3 Fast', 'model_name': 'veo3-fast',
        'description': 'Ускоренная версия Veo 3 от Google DeepMind. Нативный синхронный звук. Через CometAPI — у Apimart этой версии нет, только 3.1.',
        'cost_kopecks': 6720,  # 67.20₽ = $0.08/сек × 105 × 8 сек (CometAPI, подтверждено живым вызовом)
        'res_4k_delta': 134,
        'order': 61,
    },
]

# CometAPI принимает ровно 1 референс-фото файлом (input_reference), не
# ссылкой и не несколько штук, как часть моделей apimart — отсюда max_images=1.
I2V_METADATA = {
    "supports_image_to_video": True,
    "i2v_param": "input_reference",
    "i2v_mode": "reference",
    "i2v_max_images": 1,
}


class Command(BaseCommand):
    help = "Добавляет Veo 3 / Veo 3 Fast через CometAPI (is_active=False до ручной проверки)"

    def handle(self, *args, **options):
        video_cat, _ = Category.objects.get_or_create(
            slug='video', defaults={'name': 'Видео', 'icon': 'fas fa-video', 'order': 3},
        )

        for m in MODELS:
            config = {
                "name": m['name'],
                "api_defaults": {"duration": 8, "resolution": "1080p", "aspect_ratio": "16:9"},
                "ui_settings": {
                    "sections": [{
                        "title": "Настройки видео (8 сек, фиксировано)",
                        "fields": [
                            _aspect_field(),
                            {
                                "name": "resolution", "type": "select", "label": "Качество", "extra_cost": 0,
                                "options": [
                                    {"value": "720p", "label": "720p (HD)", "extra_cost": 0},
                                    {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 0},
                                    {"value": "4k", "label": "4K (Ultra HD)", "extra_cost": m['res_4k_delta']},
                                ],
                            },
                        ],
                    }],
                },
                "constraints": {},
                "metadata": {
                    "output_type": "video",
                    "video_api": "cometapi",
                    **I2V_METADATA,
                },
            }

            network = NeuralNetwork.objects.filter(slug=m['slug']).first()
            if network is None:
                network = NeuralNetwork.objects.create(
                    slug=m['slug'], name=m['name'], category=video_cat,
                    model_name=m['model_name'], provider='fal-ai',
                    cost_kopecks=m['cost_kopecks'],
                    cost_per_message=round(m['cost_kopecks'] / 100),
                    order=m['order'], description_ru=m['description'],
                    config_json=config, is_active=False, is_popular=False,
                )
                self.stdout.write(self.style.SUCCESS(f"создана (неактивна): {network.name} ({network.model_name})"))
            else:
                network.name = m['name']
                network.category = video_cat
                network.model_name = m['model_name']
                network.provider = 'fal-ai'
                network.config_json = config
                network.description_ru = m['description']
                network.save(update_fields=['name', 'category', 'model_name', 'provider', 'config_json', 'description_ru'])
                self.stdout.write(f"обновлена: {network.name} ({network.model_name}) — is_active не тронут ({network.is_active})")
