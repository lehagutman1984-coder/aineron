"""
Раунд 2 резерва CometAPI для изображений — по прямому запросу пользователя
"подключи резерв где ещё не сделано" (2026-09-07).

Живьём подтверждено (POST /v1/images/generations, стандартный синхронный
контракт generate_image_cometapi, via_chat=False):
- gpt-image-2, gpt-image-1-mini, gpt-image-1.5 — 200, b64_json (gpt-image-1
  уже был подтверждён раньше и подключён отдельно).
- doubao-seedream-4-5-251128, doubao-seedream-5-0-260128 — 200, url
  (doubao-seedream-4-0-250828 уже был подтверждён раньше и подключён отдельно).

Flux Kontext — ОТДЕЛЬНЫЙ контракт (POST /flux/v1/flux-kontext-{pro,max}),
не /v1/images/generations: тот эндпоинт прямо отвечает "must be called via
the flux format" на попытку вызвать его как обычную модель. Контракт внутри
похож на flux-2-x (тот же /flux/v1/{model} + polling), но тело другое —
aspect_ratio вместо width/height ("does not support width/height", живьём
подтверждено). generate_image_flux_cometapi() обновлена на приём обоих
вариантов через metadata.cometapi_contract:
  'flux'         — flux-2-pro/-max/-flex (width/height)
  'flux_kontext' — flux-kontext-pro/-max (aspect_ratio + input_image)
Оба Kontext подтверждены живьём до полного результата (status=Ready,
result.sample — реальный URL).

НЕ подключено (проверено и отброшено в этом же раунде):
- qwen-image-3.0 — числится в каталоге CometAPI, но реальный вызов даёт 503
  model_not_found (channel недоступен) — каталог ≠ реальная доступность.
- qwen-image-2.0, qwen-image-3.0-pro, z-image-turbo, wan-2.7-image —
  повторно не проверялись, уже задокументированы как "нет модели у
  CometAPI" в первом раунде (см. IMAGE_PROVIDER_MIGRATION_PRICING_2026-09-05.html).

ВАЖНО (структурный пробел, НЕ устраняется этой командой): резерв
CometAPI работает только для генерации С НУЛЯ (client.images.generate()).
Путь редактирования изображений (generate_image_edit(), img2img — когда
пользователь передаёт исходное фото) вообще не проверяет
cometapi_fallback_model — резерва там нет НИ У ОДНОЙ модели, включая уже
подключённые Nano Banana/Grok Imagine/Midjourney. Flux Kontext по
умолчанию не требует исходного фото (requires_input_images=False) и при
чистой генерации с нуля (без фото) резерв реально сработает; при
редактировании существующего фото — нет. Отдельная, более крупная задача.

Запуск: docker-compose exec web python manage.py add_image_cometapi_fallback_round2
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork

# slug -> {cometapi_fallback_model, cometapi_contract?}
FALLBACKS = {
    'gpt-image-1': {'cometapi_fallback_model': 'gpt-image-1'},
    'gpt-image-2': {'cometapi_fallback_model': 'gpt-image-2'},
    'gpt-image-1-mini': {'cometapi_fallback_model': 'gpt-image-1-mini'},
    'gpt-image-1-5': {'cometapi_fallback_model': 'gpt-image-1.5'},
    'seedream-4-0': {'cometapi_fallback_model': 'doubao-seedream-4-0-250828'},
    'seedream-4-5': {'cometapi_fallback_model': 'doubao-seedream-4-5-251128'},
    'seedream-5-0': {'cometapi_fallback_model': 'doubao-seedream-5-0-260128'},
    'flux-kontext-pro': {'cometapi_fallback_model': 'flux-kontext-pro', 'cometapi_contract': 'flux_kontext'},
    'flux-kontext-max': {'cometapi_fallback_model': 'flux-kontext-max', 'cometapi_contract': 'flux_kontext'},
}


class Command(BaseCommand):
    help = "Раунд 2: проставляет metadata.cometapi_fallback_model (+ cometapi_contract) для 9 моделей изображений с живьём подтверждённым резервом CometAPI"

    def handle(self, *args, **options):
        for slug, fields in FALLBACKS.items():
            network = NeuralNetwork.objects.filter(slug=slug).first()
            if not network:
                self.stdout.write(self.style.WARNING(f'{slug}: не найдена в БД, пропуск'))
                continue
            config = network.config_json or {}
            metadata = config.setdefault('metadata', {})
            changed = False
            for key, value in fields.items():
                if metadata.get(key) != value:
                    metadata[key] = value
                    changed = True
            if not changed:
                self.stdout.write(f'{slug}: уже проставлено, пропуск')
                continue
            network.config_json = config
            network.save(update_fields=['config_json'])
            self.stdout.write(self.style.SUCCESS(f'{slug}: {fields}'))
