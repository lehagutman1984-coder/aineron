"""
Разовая перекалибровка цен видео-моделей apimart по верифицированным тарифам
CometAPI (реестр от 2026-09-04, https://claude.ai/code/artifact/63c7d016-...).

ВАЖНО: генерация видео у нас идёт через apimart, не CometAPI — реестр CometAPI
использован только как источник структуры тиров (какие разрешения/длительности
существуют и во сколько раз они дороже друг друга), пересчитанный в ₽ через
нашу стандартную формулу opt_$ × K(=105). Маржа держится, только если реальная
цена apimart за юнит близка к цене CometAPI за тот же юнит — это не проверено
по каждой модели отдельно, только сверено на уровне тарифной структуры.

Модели без чистого соответствия в реестре CometAPI (Kling v2.6, Kling 3.0 Turbo,
Hailuo 2.3 / Fast, Pixverse V6, Veo 3.1 Lite, Vidu Q3 Pro) НЕ трогаются командой —
их текущая цена (RouterAI-конкурентная, посчитанная ранее) остаётся как есть.

Kling: у CometAPI один эндпоинт kling_video, версия — параметр model_name.
Реестр даёт построчные цены только для v3 / v3-omni / o1. Маппинг на наши
6 SKU:
  kling-v3                -> CometAPI "v3 (Kling 3.0)"
  kling-v3-omni            -> CometAPI "v3-omni / o1" (без тира "видео-инпут" —
                               у нас нет отдельного тумблера под него)
  kling-video-o1            -> тот же "v3-omni / o1" ряд (о1 — тот же прайс, что omni)
  kling-v3-motion-control  -> тот же "v3 (Kling 3.0)" ряд (Comet не даёт отдельной
                               цены motion-control БЕЗ звука — по факту это тот
                               же v3-эндпоинт с другим режимом ввода)
  kling-v2-6, kling-3-0-turbo -> НЕ ТРОГАЕМ (в реестре CometAPI эти версии
                               существуют на странице, но не расписаны построчно)

extra_cost — рубли (см. src/aitext/tasks.py:739, ×100 при списании), округлены
до целого рубля, как и остальные значения в config_json по проекту.
Отрицательный extra_cost — легитимен: тир реально ДЕШЕВЛЕ базового (например
480p у Seedance 2.0 дешевле её базового 720p).

Модели без 1080p-данных у CometAPI (Seedance 2.0 Fast, Seedance 2.5) — их
1080p-тир НЕ трогаем (оставляем прежний extra_cost), помечено в PRICING ниже.

Запуск: docker-compose exec web python manage.py update_video_pricing
        docker-compose exec web python manage.py update_video_pricing --dry-run
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork


# slug -> {cost_kopecks, res_field, res_deltas, dur_deltas, audio_field, audio_delta}
PRICING = {
    'veo-3-1': {
        'cost_kopecks': 26880,
        'res_field': 'resolution',
        'res_deltas': {'720p': 0, '1080p': 0, '4k': 134},
        'dur_deltas': {'8': 0},
    },
    'veo-3-1-fast': {
        'cost_kopecks': 6720,
        'res_field': 'resolution',
        'res_deltas': {'720p': 0, '1080p': 13, '4k': 134},
        'dur_deltas': {'8': 0},
    },
    'kling-v3': {
        'cost_kopecks': 3528,
        'res_field': 'mode',
        'res_deltas': {'std': 0, 'pro': 12, '4k': 141},
        'dur_deltas': {'3': -14, '5': 0, '8': 21, '10': 35, '15': 71},
        'audio_field': 'audio', 'audio_delta': 18,
    },
    'kling-v3-motion-control': {
        'cost_kopecks': 3528,
        'res_field': 'mode',
        'res_deltas': {'std': 0, 'pro': 12, '4k': 141},
        'dur_deltas': {'3': -14, '5': 0, '8': 21, '10': 35, '15': 71},
        'audio_field': 'audio', 'audio_delta': 18,
    },
    'kling-v3-omni': {
        'cost_kopecks': 3528,
        'res_field': 'mode',
        'res_deltas': {'std': 0, 'pro': 12, '4k': 141},
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
        'cost_kopecks': 4200,
        'res_field': 'resolution',
        'res_deltas': {'720p': 0, '1080p': 21},
        'dur_deltas': {'5': 0, '10': 42, '15': 84},
    },
    'wan-2-7': {
        'cost_kopecks': 4200,
        'res_field': 'resolution',
        'res_deltas': {'720p': 0, '1080p': 21},
        'dur_deltas': {'5': 0, '10': 42, '15': 84},
    },
    'seedance-1-5-pro': {
        'cost_kopecks': 2184,
        'res_field': 'resolution',
        'res_deltas': {'480p': -12, '720p': 0, '1080p': 27},
        'dur_deltas': {'4': -4, '5': 0, '6': 4, '8': 13, '10': 22, '12': 31},
    },
    'seedance-2-0': {
        'cost_kopecks': 6384,
        'res_field': 'resolution',
        'res_deltas': {'480p': -34, '720p': 0, '1080p': 93, '4k': 264},
        'dur_deltas': {'4': -13, '5': 0, '6': 13, '8': 38, '10': 64, '12': 89, '15': 128},
    },
    'seedance-2-0-fast': {
        'cost_kopecks': 5040,
        'res_field': 'resolution',
        'res_deltas': {'480p': -27, '720p': 0},  # 1080p: нет данных Comet, не трогаем
        'dur_deltas': {'4': -10, '5': 0, '6': 10, '8': 30, '10': 50},
    },
    'seedance-2-5': {
        'cost_kopecks': 5408,
        'res_field': 'resolution',
        'res_deltas': {'480p': 0, '720p': 67},  # 1080p: нет данных Comet, не трогаем
        'dur_deltas': {'4': -11, '5': 0, '8': 32, '10': 54, '15': 108, '20': 162, '25': 216, '30': 270},
    },
    'vidu-q3': {
        'cost_kopecks': 2940,
        'res_field': 'resolution',
        'res_deltas': {'540p': 0, '720p': 35},
        'dur_deltas': {'4': -6, '5': 0, '8': 18},
    },
    'vidu-q3-turbo': {
        'cost_kopecks': 3234,
        'res_field': 'resolution',
        'res_deltas': {'540p': -18, '720p': 0, '1080p': 0},
        'dur_deltas': {'4': -6, '5': 0, '8': 19, '12': 45, '16': 71},
    },
    'grok-imagine-1-5': {
        'cost_kopecks': 4032,
        'res_field': 'quality',
        'res_deltas': {'480p': 0, '720p': 30},
        'dur_deltas': {'6': 0, '10': 27, '15': 60, '20': 94, '30': 161},
    },
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
    help = "Пересчитывает цены видео-моделей по тарифной структуре CometAPI (см. docstring файла)"

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

            res_changed = _patch_field(fields, spec['res_field'], spec['res_deltas'])
            dur_changed = _patch_field(fields, 'duration', spec['dur_deltas'])
            audio_changed = None
            if 'audio_field' in spec:
                audio_changed = _patch_field(fields, spec['audio_field'], {'__checkbox__': spec['audio_delta']})
                # чекбокс хранит extra_cost прямо на поле, не в options
                for f in fields:
                    if f.get('name') == spec['audio_field']:
                        old_a = f.get('extra_cost', 0)
                        f['extra_cost'] = spec['audio_delta']
                        audio_changed = [(spec['audio_field'], old_a, spec['audio_delta'])]

            self.stdout.write(f'{slug}: cost_kopecks {old_cost} -> {new_cost} ({old_cost/100:.2f}₽ -> {new_cost/100:.2f}₽)')
            if res_changed:
                self.stdout.write(f'  {spec["res_field"]}: ' + ', '.join(f'{v}: {o}->{n}' for v, o, n in res_changed))
            if dur_changed:
                self.stdout.write(f'  duration: ' + ', '.join(f'{v}s: {o}->{n}' for v, o, n in dur_changed))
            if audio_changed:
                self.stdout.write(f'  audio: ' + ', '.join(f'{v}: {o}->{n}' for v, o, n in audio_changed))

            if not dry_run:
                network.cost_kopecks = new_cost
                network.config_json = config
                network.save(update_fields=['cost_kopecks', 'config_json'])

        if dry_run:
            self.stdout.write(self.style.WARNING('\n--dry-run: изменения НЕ сохранены'))
        else:
            self.stdout.write(self.style.SUCCESS('\nГотово, сохранено в БД'))
