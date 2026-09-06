"""
Проставляет CometAPI-резерв (2-й уровень цепочки apimart→cometapi→laozhang)
для видео-моделей, где живьём подтверждена реальная РАБОЧАЯ генерация
(не просто приём задачи в очередь, а completed с video_url) — 2026-09-06.

Проверено прямыми вызовами CometAPI /v1/videos, отдельно от нашего кода:
- wan2.6, wan2.7, viduq3, viduq3-turbo, veo3.1-fast, veo3.1,
  doubao-seedance-1-5-pro, doubao-seedance-2-0, seedance-2-5 — все дошли
  до status=completed с реальным video_url.
- wan2.6 и doubao-seedance-1-5-pro первой попыткой (input_reference файлом)
  упали с "please provide reference_video_urls or reference_urls" /
  "Field required" — со второй попытки (reference_urls строкой-URL вместо
  файла) оба отработали до completed. metadata.cometapi_ref_param='reference_urls'
  переключает generate_video_cometapi() на этот путь для них.
- kling-* (5 моделей, только generic kling_video без версии — контракт не
  проверен), hailuo-2-3/-fast (нет совпадающей версии в каталоге CometAPI),
  vidu-q3-pro (нет pro-тира), pixverse-v6 (модели нет в каталоге вообще),
  seedance-2-0-fast (нет fast-тира), grok-imagine-1-5 (400 "unsupported
  relay mode" сразу при отправке) — резерва НЕТ, остаются apimart-only, как
  раньше. Не угадывать имя/контракт для них без отдельной живой проверки.

veo3.1/veo3.1-fast сохраняют существующий laozhang_fallback_model —
теперь это 3-й уровень (после cometapi), не единственный резерв.

Запуск: docker-compose exec web python manage.py add_video_cometapi_fallback
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork

# slug -> (cometapi_fallback_model, cometapi_ref_param | None)
FALLBACKS = {
    'veo-3-1-fast': ('veo3.1-fast', None),
    'veo-3-1': ('veo3.1', None),
    'wan-2-6': ('wan2.6', 'reference_urls'),
    'wan-2-7': ('wan2.7', None),
    'vidu-q3': ('viduq3', None),
    'vidu-q3-turbo': ('viduq3-turbo', None),
    'seedance-1-5-pro': ('doubao-seedance-1-5-pro', 'reference_urls'),
    'seedance-2-0': ('doubao-seedance-2-0', None),
    'seedance-2-5': ('seedance-2-5', None),
}


class Command(BaseCommand):
    help = "Проставляет metadata.cometapi_fallback_model (+ cometapi_ref_param) для 9 видео-моделей с живьём подтверждённым резервом CometAPI"

    def handle(self, *args, **options):
        for slug, (fb_model, ref_param) in FALLBACKS.items():
            network = NeuralNetwork.objects.filter(slug=slug).first()
            if not network:
                self.stdout.write(self.style.WARNING(f'{slug}: не найдена в БД, пропуск'))
                continue
            config = network.config_json or {}
            metadata = config.setdefault('metadata', {})
            changed = False
            if metadata.get('cometapi_fallback_model') != fb_model:
                metadata['cometapi_fallback_model'] = fb_model
                changed = True
            if ref_param and metadata.get('cometapi_ref_param') != ref_param:
                metadata['cometapi_ref_param'] = ref_param
                changed = True
            if not changed:
                self.stdout.write(f'{slug}: уже проставлено, пропуск')
                continue
            network.config_json = config
            network.save(update_fields=['config_json'])
            self.stdout.write(self.style.SUCCESS(
                f'{slug}: cometapi_fallback_model={fb_model}' + (f', cometapi_ref_param={ref_param}' if ref_param else '')
            ))
