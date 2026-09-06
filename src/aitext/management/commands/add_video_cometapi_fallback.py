"""
Проставляет CometAPI-резерв (2-й уровень цепочки apimart→cometapi→laozhang)
для видео-моделей, где живьём подтверждена реальная РАБОЧАЯ генерация
(не просто приём задачи в очередь, а completed с video_url) — 2026-09-06.

Раунд 2 (после сверки с "Реестр цен APIMart видео.html" +
"Реестр цен на видео-модели.html" по просьбе пользователя — первый раунд
проверял только по публичному /api/models CometAPI, который оказался
неполным каталогом для видео): добавлена doubao-seedance-2-0-fast, найдены
и отброшены ещё 3 кандидата.

Проверено прямыми вызовами CometAPI /v1/videos, отдельно от нашего кода —
10 моделей дошли до status=completed с реальным video_url:
wan2.6, wan2.7, viduq3, viduq3-turbo, veo3.1-fast, veo3.1,
doubao-seedance-1-5-pro, doubao-seedance-2-0, doubao-seedance-2-0-fast,
seedance-2-5.

wan2.6, doubao-seedance-1-5-pro и doubao-seedance-2-0-fast первой попыткой
(input_reference файлом) либо падали ("please provide reference_video_urls
or reference_urls" / "Field required"), либо не были протестированы файлом
вовсе — со второй попытки (reference_urls строкой-URL вместо файла) все три
отработали до completed. metadata.cometapi_ref_param='reference_urls'
переключает generate_video_cometapi() на этот путь для них.

Проверено и ОТБРОШЕНО (реальные ошибки от CometAPI, не наша интеграция):
- kling-* (5 моделей apimart) — реестр цен CometAPI описывает единый
  эндпоинт kling_video с версией внутри параметра model_name, но это
  ДРУГОЙ путь/контракт, не /v1/videos — прямой POST kling-v2-6 на
  /v1/videos дал 503 model_not_found; 3 угаданных варианта пути
  (/v1/kling_video, /v1/videos/kling) дали 404 Invalid URL. Нужна реальная
  документация API CometAPI по Kling, не страница цен — не угадывать
  дальше вслепую.
- vidu-q3-pro — 503 model_not_found (страница цен CometAPI пишет "viduq3
  (viduq3-pro)", но литеральной модели viduq3-pro в API нет — pro явно не
  отдельный model id).
- grok-imagine-1-5 / grok-imagine-video-1.5 — оба варианта имени дали 400
  "unsupported relay mode: 31" мгновенно.
- hailuo-2-3/-fast (нет совпадающей версии в каталоге CometAPI),
  pixverse-v6 (модели нет у CometAPI вообще) — не перепроверялись повторно,
  причина та же, что и в раунде 1 (см. git log).

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
    'seedance-2-0-fast': ('doubao-seedance-2-0-fast', 'reference_urls'),
    'seedance-2-5': ('seedance-2-5', None),
}


class Command(BaseCommand):
    help = "Проставляет metadata.cometapi_fallback_model (+ cometapi_ref_param) для 10 видео-моделей с живьём подтверждённым резервом CometAPI"

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
