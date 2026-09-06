"""
Проставляет CometAPI-резерв (2-й уровень цепочки apimart→cometapi→laozhang)
для видео-моделей, где живьём подтверждена реальная РАБОЧАЯ генерация
(не просто приём задачи в очередь, а status=completed/succeed с реальным
video url) — 2026-09-06.

Раунд 3 (по прямой ссылке пользователя на cometapi.com/models/kling/kling-video/ —
раунд 2 сверялся только по странице цен, которая описывает контракт "на
словах", без технических деталей; раунд 1 — по публичному /api/models,
неполному именно для видео): у Kling оказался СВОЙ, полностью отдельный
эндпоинт и контракт — POST https://api.cometapi.com/kling/v1/videos/image2video
(JSON, НЕ /v1/videos и НЕ multipart), параметр модели — model_name, а не
model. См. generate_video_kling_cometapi() в fal_utils.py — там же вся
техническая специфика (image=URL строкой, task_status succeed/failed вместо
completed/error, task_result.videos[0].url). Живьём подтверждены до
succeed: kling-v2-6 и kling-v3 (2 из 5 моделей Kling в нашем каталоге).
kling-3.0-turbo/kling-v3-omni/kling-video-o1 и десяток опробованных
вариантов написания их имён — везде "invalid model name": CometAPI пока не
завёл эти версии под этим эндпоинтом, не гадать дальше без точных данных
от CometAPI.

Раунд 2 (после сверки с "Реестр цен APIMart видео.html" +
"Реестр цен на видео-модели.html"): добавлена doubao-seedance-2-0-fast,
плюс проверены и ОТБРОШЕНЫ vidu-q3-pro (503 model_not_found — литеральной
модели с этим id нет) и обе версии имени grok-imagine (400 "unsupported
relay mode" — маршрут в принципе не работает через /v1/videos).

Раунд 1: живьём проверены до status=completed с video_url — wan2.6, wan2.7,
viduq3, viduq3-turbo, veo3.1-fast, veo3.1, doubao-seedance-1-5-pro,
doubao-seedance-2-0, seedance-2-5. wan2.6 и doubao-seedance-1-5-pro (и
позже doubao-seedance-2-0-fast) требуют reference_urls строкой вместо
input_reference файлом — см. metadata.cometapi_ref_param в
generate_video_cometapi().

Итог на конец раунда 3: 12 из 21 apimart-моделей имеют реальный резерв
CometAPI. Без резерва остаются: kling-3.0-turbo/kling-v3-omni/kling-video-o1
(нужна точная документация от CometAPI), hailuo-2-3/-fast (несовместимая
линейка версий у CometAPI), vidu-q3-pro (нет такого id), pixverse-v6
(модели нет у CometAPI вообще), grok-imagine-1-5 (маршрут не работает).

veo3.1/veo3.1-fast сохраняют существующий laozhang_fallback_model —
теперь это 3-й уровень (после cometapi), не единственный резерв.

Запуск: docker-compose exec web python manage.py add_video_cometapi_fallback
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork

# slug -> {cometapi_fallback_model, cometapi_ref_param?, cometapi_contract?}
FALLBACKS = {
    'veo-3-1-fast': {'cometapi_fallback_model': 'veo3.1-fast'},
    'veo-3-1': {'cometapi_fallback_model': 'veo3.1'},
    'wan-2-6': {'cometapi_fallback_model': 'wan2.6', 'cometapi_ref_param': 'reference_urls'},
    'wan-2-7': {'cometapi_fallback_model': 'wan2.7'},
    'vidu-q3': {'cometapi_fallback_model': 'viduq3'},
    'vidu-q3-turbo': {'cometapi_fallback_model': 'viduq3-turbo'},
    'seedance-1-5-pro': {'cometapi_fallback_model': 'doubao-seedance-1-5-pro', 'cometapi_ref_param': 'reference_urls'},
    'seedance-2-0': {'cometapi_fallback_model': 'doubao-seedance-2-0'},
    'seedance-2-0-fast': {'cometapi_fallback_model': 'doubao-seedance-2-0-fast', 'cometapi_ref_param': 'reference_urls'},
    'seedance-2-5': {'cometapi_fallback_model': 'seedance-2-5'},
    'kling-v26': {'cometapi_fallback_model': 'kling-v2-6', 'cometapi_contract': 'kling'},
    'kling-v3': {'cometapi_fallback_model': 'kling-v3', 'cometapi_contract': 'kling'},
}


class Command(BaseCommand):
    help = "Проставляет metadata.cometapi_fallback_model (+ cometapi_ref_param/cometapi_contract) для видео-моделей с живьём подтверждённым резервом CometAPI"

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
