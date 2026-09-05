"""
Перекалибровка цен видео-моделей apimart — теперь по РЕАЛЬНЫМ выверенным
тарифам самого Apimart (реестр от 2026-09-05,
https://claude.ai/code/artifact/fb7b9382-...), а не по CometAPI-прокси.

История: первая версия этой команды (2026-09-04) считала цены по реестру
CometAPI как заглушке для Apimart — в тогдашнем докстринге было явно
написано "маржа держится, только если реальная цена apimart близка к
CometAPI — это не проверено". Проверка (эта версия) показала разброс от
-88% до +800% на разных моделях: часть моделей продавалась ниже опта.
Второй заход (эта версия) берёт цены напрямую с реестра Apimart —
формула-в-формулу совпадает со структурой первой версии, но числа другие.

ВАЖНОЕ ОТКРЫТИЕ: Veo 3.1 (veo-3-1, veo-3-1-fast, veo-3-1-lite) на самом деле
тарифицируется APIMART НЕ за секунду, а ФИКСИРОВАНО ЗА ВЫЗОВ (канал "-ext").
Подтверждено живым запросом к GET /v1/models на проде — наши model_name
(veo3.1-quality, veo3.1-fast, veo3.1-lite, без суффиксов) существуют в
реальном каталоге Apimart как отдельные ID, отличные от суффиксных
`-official` (тарифицируемых за секунду). Реестр APIMart называет
бессуффиксные ID каналом "-ext" в своей документации цен, хотя реальный
API ID суффикса не содержит. Раньше эти три модели считались по цене за
секунду (унаследовано из CometAPI-подхода) — это была фундаментальная
ошибка базиса, а не просто неточные цифры.

БАГ (найден и исправлен этой же командой, помимо цен): `grok-imagine-1-5`
имел в БД `model_name = "grok-imagine-1.5-video-ext"` — такого ID нет в
реальном каталоге Apimart вообще (проверено GET /v1/models). Живая история
сообщений подтвердила: 3 из 4 последних генераций падали с ошибкой (деньги
возвращались корректно, но фича не работала). Исправлено на
`grok-imagine-1.5-video-apimart` (реальный ID, подтверждён в каталоге).

Модели без чистого соответствия в реестре Apimart остаются нетронутыми:
`kling-v2-6`/`kling-3-0-turbo`/`vidu-q3` («полная сетка есть на сайте, но
в реестр попал только один тир — 1080P») — для `vidu-q3-pro` использован
единственный доступный тир (1080P, совпадает с нашим api_defaults), для
`vidu-q3`/`vidu-q3-turbo` данных под наш реальный базовый тир (540p) нет —
оставлены как есть (посчитаны в прошлой версии по CometAPI).

Kling: см. предыдущую версию докстрайна про маппинг на 6 SKU — не изменился.
ИСПРАВЛЕНИЕ к прошлой версии: `kling-v3-motion-control` ошибочно считался
по базовой ставке обычного Kling v3 ($0.0672/сек) — реальная ставка Apimart
для motion-control почти в 1.5 раза выше ($0.10288/сек), это отдельный SKU
с собственной ценой, не альтернативный режим ввода того же v3.
`kling-v3`/`kling-v3-omni`: тир std/pro подтверждён точным совпадением с
Apimart без изменений; тир 4K скорректирован — Apimart даёт только
бандл "4K+Sound" ($0.42856/сек), отдельной цены на 4K-без-звука нет.

extra_cost — рубли (см. src/aitext/tasks.py:739, ×100 при списании),
округлены до целого рубля. Отрицательный extra_cost легитимен (тир дешевле
базового).

Известное ограничение (не устранено в этой версии): у Kling v3/Omni при
одновременном выборе mode=pro/4k И audio=true доплаты складываются, хотя
по факту Apimart уже включает звук в цену этих тиров — небольшая переплата
для пользователя, выбравшего оба поля, не потеря маржи (в отличие от
mode=4k+audio, которое явно запрещено отдельным constraints.incompatible,
см. add_kling_4k_audio_constraint).

Запуск: docker-compose exec web python manage.py update_video_pricing
        docker-compose exec web python manage.py update_video_pricing --dry-run
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork


# slug -> {cost_kopecks, res_field, res_deltas, dur_deltas, audio_field, audio_delta}
PRICING = {
    'veo-3-1': {
        'cost_kopecks': 10500,
        'res_field': 'resolution',
        'res_deltas': {'720p': 0, '1080p': 0, '4k': 53},
        'dur_deltas': {'8': 0},
    },
    'veo-3-1-fast': {
        'cost_kopecks': 1470,
        'res_field': 'resolution',
        'res_deltas': {'720p': 0, '1080p': 0, '4k': 53},
        'dur_deltas': {'8': 0},
    },
    'veo-3-1-lite': {
        'cost_kopecks': 735,
    },
    'kling-v26': {
        'cost_kopecks': 1932,
        'res_field': 'mode',
        'res_deltas': {'std': 0, 'pro': 13},
        'dur_deltas': {'5': 0, '10': 19},
        'audio_field': 'audio', 'audio_delta': 46,
    },
    'kling-3-0-turbo': {
        'cost_kopecks': 6006,
        'res_field': 'resolution',
        'res_deltas': {'720p': 0, '1080p': 15},
        'dur_deltas': {'3': -24, '5': 0, '8': 36, '10': 60},
    },
    'hailuo-2-3': {
        'cost_kopecks': 3074,
        'res_field': 'resolution',
        'res_deltas': {'768p': 0, '1080p': 15},
        'dur_deltas': {'6': 0, '10': 21},
    },
    'hailuo-2-3-fast': {
        'cost_kopecks': 1562,
        'res_field': 'resolution',
        'res_deltas': {'768p': 0, '1080p': 11},
        'dur_deltas': {'6': 0, '10': 10},
    },
    'pixverse-v6': {
        'cost_kopecks': 1260,
        'res_field': 'resolution',
        'res_deltas': {'360p': -4, '540p': 0, '720p': 4, '1080p': 21},
        'dur_deltas': {'3': -5, '5': 0, '8': 8, '10': 13, '15': 25},
        'audio_field': 'audio', 'audio_delta': 4,
    },
    'kling-v3': {
        'cost_kopecks': 3528,
        'res_field': 'mode',
        'res_deltas': {'std': 0, 'pro': 35, '4k': 190},
        'dur_deltas': {'3': -14, '5': 0, '8': 21, '10': 35, '15': 71},
        'audio_field': 'audio', 'audio_delta': 35,
    },
    'kling-v3-motion-control': {
        'cost_kopecks': 5401,
        'res_field': 'mode',
        'res_deltas': {'std': 0, 'pro': 18},  # 4k: нет данных Apimart для этого SKU, не трогаем
        'dur_deltas': {'3': -22, '5': 0, '8': 32, '10': 54, '15': 108},
        # audio: нет данных Apimart для этого SKU, не трогаем
    },
    'kling-v3-omni': {
        'cost_kopecks': 3528,
        'res_field': 'mode',
        'res_deltas': {'std': 0, 'pro': 35, '4k': 190},
        'dur_deltas': {'3': -14, '5': 0, '8': 21, '10': 35, '15': 71},
        'audio_field': 'audio', 'audio_delta': 12,
    },
    'kling-video-o1': {
        'cost_kopecks': 3528,
        'res_field': 'mode',
        'res_deltas': {'std': 0, 'pro': 12},
        'dur_deltas': {'3': -14, '5': 0, '8': 21, '10': 35},
    },
    'wan-2-6': {
        'cost_kopecks': 2625,
        'res_field': 'resolution',
        'res_deltas': {'720p': 0, '1080p': 18},
        'dur_deltas': {'5': 0, '10': 26, '15': 53},
    },
    'wan-2-7': {
        'cost_kopecks': 3486,
        'res_field': 'resolution',
        'res_deltas': {'720p': 0, '1080p': 23},
        'dur_deltas': {'5': 0, '10': 35, '15': 70},
    },
    'seedance-1-5-pro': {
        'cost_kopecks': 2310,
        'res_field': 'resolution',
        'res_deltas': {'480p': -12, '720p': 0, '1080p': 34},
        'dur_deltas': {'4': -5, '5': 0, '6': 5, '8': 14, '10': 23, '12': 32},
    },
    'seedance-2-0': {
        'cost_kopecks': 7455,
        'res_field': 'resolution',
        'res_deltas': {'480p': -40, '720p': 0, '1080p': 112, '4k': 305},
        'dur_deltas': {'4': -15, '5': 0, '6': 15, '8': 45, '10': 75, '12': 104, '15': 149},
    },
    'seedance-2-0-fast': {
        'cost_kopecks': 4494,
        'res_field': 'resolution',
        'res_deltas': {'480p': -24, '720p': 0},  # 1080p: нет данных Apimart, не трогаем
        'dur_deltas': {'4': -9, '5': 0, '6': 9, '8': 27, '10': 45},
    },
    'seedance-2-5': {
        'cost_kopecks': 5044,
        'res_field': 'resolution',
        'res_deltas': {'480p': 0, '720p': 63, '1080p': 152},
        'dur_deltas': {'4': -10, '5': 0, '8': 30, '10': 50, '15': 101, '20': 151, '25': 202, '30': 252},
    },
    'vidu-q3-pro': {
        'cost_kopecks': 6720,
        'res_field': 'resolution',
        'res_deltas': {'1080p': 0},  # 720p: нет данных Apimart (сайт даёт только 1080P), не трогаем
        'dur_deltas': {'4': -13, '5': 0, '8': 40, '12': 94, '16': 148},
    },
    'grok-imagine-1-5': {
        'cost_kopecks': 643,
        'res_field': 'quality',
        'res_deltas': {'480p': 0, '720p': 6},
        'dur_deltas': {'6': 0, '10': 4, '15': 10, '20': 15, '30': 26},
    },
}

# grok-imagine-1-5: model_name в БД был невалидным (см. докстринг выше) — правим
# отдельно от ценовой матрицы, тем же прогоном.
MODEL_NAME_FIXES = {
    'grok-imagine-1-5': 'grok-imagine-1.5-video-apimart',
}


def _patch_field(fields, field_name, value_deltas):
    for f in fields:
        if f.get('name') != field_name:
            continue
        changed = []
        for opt in f.get('options', []):
            if opt['value'] in value_deltas:
                old = opt.get('extra_cost', 0)
                new = value_deltas[opt['value']]
                opt['extra_cost'] = new
                changed.append((opt['value'], old, new))
        return changed
    return None


class Command(BaseCommand):
    help = "Пересчитывает цены видео-моделей по реальным тарифам Apimart (см. docstring файла)"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Только показать изменения, не сохранять')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        for slug, spec in PRICING.items():
            network = NeuralNetwork.objects.filter(slug=slug).first()
            if not network:
                self.stdout.write(self.style.WARNING(f'{slug}: не найдена в БД, пропуск'))
                continue

            config = network.config_json or {}
            fields = config.get('ui_settings', {}).get('sections', [{}])[0].get('fields', [])

            old_cost = network.cost_kopecks
            new_cost = spec['cost_kopecks']

            res_changed = _patch_field(fields, spec['res_field'], spec['res_deltas']) if 'res_field' in spec else None
            dur_changed = _patch_field(fields, 'duration', spec['dur_deltas']) if 'dur_deltas' in spec else None
            audio_changed = None
            if 'audio_field' in spec:
                for f in fields:
                    if f.get('name') == spec['audio_field']:
                        old_a = f.get('extra_cost', 0)
                        f['extra_cost'] = spec['audio_delta']
                        audio_changed = [(spec['audio_field'], old_a, spec['audio_delta'])]

            old_model_name = network.model_name
            new_model_name = MODEL_NAME_FIXES.get(slug)

            self.stdout.write(f'{slug}: cost_kopecks {old_cost} -> {new_cost} ({old_cost/100:.2f}₽ -> {new_cost/100:.2f}₽)')
            if res_changed:
                self.stdout.write(f'  {spec["res_field"]}: ' + ', '.join(f'{v}: {o}->{n}' for v, o, n in res_changed))
            if dur_changed:
                self.stdout.write(f'  duration: ' + ', '.join(f'{v}s: {o}->{n}' for v, o, n in dur_changed))
            if audio_changed:
                self.stdout.write(f'  audio: ' + ', '.join(f'{v}: {o}->{n}' for v, o, n in audio_changed))
            if new_model_name and new_model_name != old_model_name:
                self.stdout.write(self.style.WARNING(f'  model_name (БАГ): {old_model_name!r} -> {new_model_name!r}'))

            if not dry_run:
                network.cost_kopecks = new_cost
                network.config_json = config
                update_fields = ['cost_kopecks', 'config_json']
                if new_model_name and new_model_name != old_model_name:
                    network.model_name = new_model_name
                    update_fields.append('model_name')
                network.save(update_fields=update_fields)

        if dry_run:
            self.stdout.write(self.style.WARNING('\n--dry-run: изменения НЕ сохранены'))
        else:
            self.stdout.write(self.style.SUCCESS('\nГотово, сохранено в БД'))
