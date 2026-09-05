"""
Проставляет metadata.cometapi_fallback_model точечно двум моделям изображений
из группы apimart_async — Grok Imagine и Grok Imagine Quality. Это единственные
две модели apimart_async, для которых контракт CometAPI /v1/images/generations
подтверждён живым тестовым вызовом 2026-09-06 (200, {"data":[{"url": ...}]},
то же имя модели работает на обеих сторонах). См. generate_image_cometapi()
и её вызов в generate_with_falai() (src/aitext/fal_utils.py).

Остальные 5 моделей apimart_async (Qwen Image 2.0/3.0/3.0 Pro, Wan 2.7 Image,
Z-Image Turbo) сознательно НЕ трогаются — ни у CometAPI, ни у laozhang.ai
их нет в каталоге (проверено 2026-09-06 по обновлённому
all_models_laozhang.ai.txt), фолбэк ставить не на что.

Запуск: docker-compose exec web python manage.py add_image_cometapi_fallback
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork

# slug -> имя модели у CometAPI (совпадает с нашим/apimart для обеих)
FALLBACK = {
    'grok-imagine-image': 'grok-imagine-image',
    'grok-imagine-image-quality': 'grok-imagine-image-quality',
}


class Command(BaseCommand):
    help = "Проставляет metadata.cometapi_fallback_model для Grok Imagine / Grok Imagine Quality"

    def handle(self, *args, **options):
        for slug, fb_model in FALLBACK.items():
            network = NeuralNetwork.objects.filter(slug=slug).first()
            if not network:
                self.stdout.write(self.style.WARNING(f'{slug}: не найдена в БД, пропуск'))
                continue
            config = network.config_json or {}
            metadata = config.setdefault('metadata', {})
            if metadata.get('cometapi_fallback_model') == fb_model:
                self.stdout.write(f'{slug}: уже проставлено, пропуск')
                continue
            metadata['cometapi_fallback_model'] = fb_model
            network.config_json = config
            network.save(update_fields=['config_json'])
            self.stdout.write(self.style.SUCCESS(f'{slug}: cometapi_fallback_model = {fb_model}'))
