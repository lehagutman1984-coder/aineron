"""
Проставляет metadata.image_max_reference_images — включает мультиреференс
(2+ фото за один запрос вместо жёсткого лимита в 1) для генерации
изображений. Читается фронтендом через api/serializers/catalog.py:get_image_refs()
как `image_refs.max_images`, форвардится в провайдера через image_urls
(см. _build_image_params / generate_image_apimart_async в fal_utils.py).

ТОЛЬКО модели, где формат image_urls подтверждён живым вызовом 2026-09-06
(2 реальных фото, задача дошла до completed с URL готового изображения):
  seedream-4-0 (laozhang.ai, extra_body.image_urls) — 200, реальный url
  qwen-image-3-0 (APIMart, image_urls в теле) — 200, completed, cost выше
    базового (провайдер реально посчитал доп. референс)
  wan-2-7-image (APIMart, image_urls в теле) — 200, completed

seedream-4-5 и seedream-5-0 НЕ тестировались отдельно, но используют тот же
API (doubao-seedream-*, тот же провайдер/эндпоинт) — включены по аналогии.
qwen-image-3-0-pro НЕ тестирован отдельно, но тот же API что qwen-image-3-0
(тот же аккаунт/эндпоинт apimart) — включена по аналогии.

НЕ включено: gemini-2-5-flash-image / gemini-3-pro-image / gemini-3-1-flash-image
(Nano Banana) — тот же тест на laozhang.ai вернул 200, но data:[] (изображение
не сгенерировано, модель просто что-то написала текстом). Рабочего формата
для мультиреференса у Nano Banana не найдено. Flux/GPT Image/DALL-E — это
edit-инструменты (одно исходное фото), не мультиреференс-генерация, не трогать.

max_images взяты из собственных маркетинговых материалов провайдеров
(IMAGE_PROVIDER_MIGRATION_PRICING_2026-09-05.html), НЕ проверены поштучно —
только механизм (2 фото) подтверждён вживую, не точный потолок:
  Seedream ×3: 10 (Seedream 5.0 Pro/4.5 заявляют "до 10 референсов")
  Qwen Image 3.0 / 3.0 Pro: 3 (официально "1-3 референса")
  Wan 2.7 Image: 4 (консервативно — точный потолок в источниках не указан)

Запуск: docker-compose exec web python manage.py add_image_multi_reference
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork

MAX_IMAGES = {
    'seedream-4-5': 10,
    'seedream-4-0': 10,
    'seedream-5-0': 10,
    'qwen-image-3-0': 3,
    'qwen-image-3-0-pro': 3,
    'wan-2-7-image': 4,
}


class Command(BaseCommand):
    help = "Включает мультиреференс (image_max_reference_images) для Seedream/Qwen 3.0/Wan 2.7"

    def handle(self, *args, **options):
        for slug, max_images in MAX_IMAGES.items():
            network = NeuralNetwork.objects.filter(slug=slug).first()
            if not network:
                self.stdout.write(self.style.WARNING(f'{slug}: не найдена в БД, пропуск'))
                continue
            config = network.config_json or {}
            metadata = config.setdefault('metadata', {})
            if metadata.get('image_max_reference_images') == max_images:
                self.stdout.write(f'{slug}: уже проставлено ({max_images}), пропуск')
                continue
            metadata['image_max_reference_images'] = max_images
            network.config_json = config
            network.save(update_fields=['config_json'])
            self.stdout.write(self.style.SUCCESS(f'{slug}: image_max_reference_images = {max_images}'))
