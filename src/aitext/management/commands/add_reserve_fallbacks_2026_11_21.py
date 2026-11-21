"""
Резервные провайдеры для медиа-моделей, державшихся ТОЛЬКО на apimart
(инцидент 2026-11-21: баланс apimart обнулён -> 22 из 54 платных медиа-моделей
не работали вовсе). Меняет ТОЛЬКО config_json['metadata'] (merge), остальное не
трогает. Идемпотентна.

ПРОВЕРЕНО ЖИВЬЁМ (реальный отказ apimart 402 -> настоящий фолбэк через наш
API /chats/, файл получен, 2026-11-21):
  nano-banana-2-1  -> CometAPI gemini-nano-banana-2.1 (cometapi_via_chat), 53 с
  qwen-image-3-0   -> CometAPI qwen-image-3.0, 64 с
  veo-3-fast       -> CometAPI veo3-fast, 106 с
  wan-3-0          -> CometAPI wan3.0, 117 с
Отклонено после проверки: flux-3-image -> CometAPI (images/generations висит
>120 с и падает по таймауту) и laozhang (503 «no available channels»).

laozhang как третий уровень для apimart_async-картинок (fal_utils:
_generate_image_via_laozhang_sync) — модели, которые laozhang отдаёт по
обычному images.generations (проверено прямым вызовом 2026-11-21, 200):
  seedream-5-5     -> seedream-5-5-261028 (у CometAPI для 5.5 только заглушка)
  nano-banana-2-1  -> gemini-nano-banana-2.1 (b64)

НЕ ПРОВЕРЕНО живьём (добавлено сознательно, при отказе результат тот же, что без
резерва — ошибка + возврат средств): veo-3 -> CometAPI veo3 (контракт тот же, что
у проверенных veo3.1-fast и veo3-fast; тест 8 с стоит ~$2.6).

Без резерва остаются (нет эквивалента у CometAPI/laozhang или он — заглушка с
ценой 75/75): kling-v4, kling-3-0-turbo, kling-v3-omni, kling-video-o1,
seedance-2-5-flash, hailuo-2-3(-fast), pixverse-v6, vidu-q3-pro, veo-3-1-lite,
grok-imagine-1-5, qwen-image-2-0, qwen-image-3-0-pro, wan-2-7-image, z-image-turbo,
flux-3-image.

Запуск: docker compose exec web python manage.py add_reserve_fallbacks_2026_11_21 [--dry-run]
"""
from django.core.management.base import BaseCommand

from aitext.models import NeuralNetwork

FALLBACKS = {
    'nano-banana-2-1': {'cometapi_fallback_model': 'gemini-nano-banana-2.1', 'cometapi_via_chat': True,
                        'laozhang_image_fallback_model': 'gemini-nano-banana-2.1'},
    'seedream-5-5': {'laozhang_image_fallback_model': 'seedream-5-5-261028'},
    'qwen-image-3-0': {'cometapi_fallback_model': 'qwen-image-3.0'},
    'veo-3-fast': {'cometapi_fallback_model': 'veo3-fast'},
    'wan-3-0': {'cometapi_fallback_model': 'wan3.0'},
    'veo-3': {'cometapi_fallback_model': 'veo3'},
}


class Command(BaseCommand):
    help = 'Добавляет резервные провайдеры (metadata) медиа-моделям, державшимся на одном apimart'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry = options['dry_run']
        for slug, add in FALLBACKS.items():
            n = NeuralNetwork.objects.filter(slug=slug).first()
            if not n:
                self.stdout.write(self.style.WARNING(f'{slug}: нет такой модели, пропуск'))
                continue
            cfg = dict(n.config_json or {})
            md = dict(cfg.get('metadata') or {})
            missing = {k: v for k, v in add.items() if md.get(k) != v}
            if not missing:
                self.stdout.write(f'{slug}: уже настроено')
                continue
            self.stdout.write(f'{slug}: +{missing}')
            if dry:
                continue
            md.update(missing)
            cfg['metadata'] = md
            NeuralNetwork.objects.filter(pk=n.pk).update(config_json=cfg)
        self.stdout.write(self.style.WARNING('\n--dry-run: не сохранено') if dry else self.style.SUCCESS('\nГотово'))
