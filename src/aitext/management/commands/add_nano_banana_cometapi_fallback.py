"""
Проставляет CometAPI-резерв для всех трёх моделей Nano Banana (config_key=
'gemini_image'). Стандартный /v1/images/generations у CometAPI эту линейку
не принимает вообще (500 "only imagen models are supported" — проверено на
разных вариантах имени модели, это не вопрос алиаса). Рабочий контракт —
POST /v1/chat/completions с обычным user-сообщением, модель отдаёт
markdown-картинку прямо в content ("![image](data:image/jpeg;base64,...)").
Подтверждено живыми вызовами 2026-09-06 на всех трёх моделях под их родными
именами (без алиасов) — валидный JPEG на выходе у каждой:
  gemini-2.5-flash-image, gemini-3.1-flash-image, gemini-3-pro-image

metadata.cometapi_via_chat=True переключает generate_image_cometapi() на
этот контракт вместо стандартного (см. docstring функции в fal_utils.py).
metadata.cometapi_fallback_model — то же имя, что у нас (алиасы не нужны).

Резерв срабатывает, только если ОБА текущих провайдера (laozhang и apimart,
через уже существующий FallbackClient) не ответили — см. точку вызова в
generate_with_falai() рядом с client.images.generate().

Запуск: docker-compose exec web python manage.py add_nano_banana_cometapi_fallback
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork

SLUGS = ['gemini-2-5-flash-image', 'gemini-3-1-flash-image', 'gemini-3-pro-image']


class Command(BaseCommand):
    help = "Проставляет cometapi_via_chat + cometapi_fallback_model для Nano Banana v1/2/Pro"

    def handle(self, *args, **options):
        for slug in SLUGS:
            network = NeuralNetwork.objects.filter(slug=slug).first()
            if not network:
                self.stdout.write(self.style.WARNING(f'{slug}: не найдена в БД, пропуск'))
                continue
            config = network.config_json or {}
            metadata = config.setdefault('metadata', {})
            changed = False
            if metadata.get('cometapi_via_chat') is not True:
                metadata['cometapi_via_chat'] = True
                changed = True
            if metadata.get('cometapi_fallback_model') != network.model_name:
                metadata['cometapi_fallback_model'] = network.model_name
                changed = True
            if not changed:
                self.stdout.write(f'{slug}: уже проставлено, пропуск')
                continue
            network.config_json = config
            network.save(update_fields=['config_json'])
            self.stdout.write(self.style.SUCCESS(f'{slug}: cometapi_via_chat=True, fallback_model={network.model_name}'))
