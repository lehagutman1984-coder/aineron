"""
Добавляет 3 модели изображений и 3 модели видео (по запросу пользователя,
2026-11-21): Seedream 5.5, Flux 3 Image, Nano Banana 2.1, Seedance 2.5 Flash,
Kling v4, Wan 3.0.

ОТБОР: свежие модели apimart (основной провайдер медиа), которых нет в БД.
Отклонено: Vidu Q4 Preview (у CometAPI только image-to-video/video-editing —
для текстового запроса не подходит), Kling 4.0 / Qwen 3.9 и пр. (у CometAPI —
заглушки с ценой 75/75), flux-3-video/happyhorse/muse — не проверялись.

ДОКАЗАТЕЛЬСТВО (по правилу из заметок: «200 submitted» — не доказательство):
каждая из 6 моделей прогнана РЕАЛЬНОЙ генерацией до status=completed и
скачан файл по ссылке результата (HTTP 200, реальный размер):
  seedream-5-5       12 с   PNG 5.2 МБ    опт $0.0280 / изображение
  flux-3-image       21 с   PNG 1.4 МБ    опт $0.0384 / изображение
  nano-banana-2.1    32 с   JPG 0.6 МБ    опт $0.0320 / изображение
  seedance-2-5-flash 91 с   MP4 2.8 МБ    опт $0.3183 / 5 с, 480p, без звука
  wan3.0-video      108 с   MP4 3.9 МБ    опт $0.3288 / 5 с, 720p
  kling-v4          191 с   MP4 2.4 МБ    опт $0.7000 / 5 с, 720p
Опт — поле `cost` (USD) из GET /v1/tasks/{id} (billing_status=settled), т.е.
реальное списание apimart, а не оценка.

ЦЕНА = опт_$ × K(105) — то же правило «опт×K», что для витрины в
pricingPreviewModels.ts (PRICING_SIMPLIFICATION_PLAN.md §2.1). Для видео —
ФИКСИРОВАННАЯ конфигурация (5 с, указанное разрешение) без доплат: опт для
других длительностей/разрешений не измерялся, линейную зависимость не
предполагаем. Выбор пользователя — только формат кадра.
  seedream-5-5        0.0280 × 105 =  2.94 ₽ ->  294 коп.
  flux-3-image        0.0384 × 105 =  4.03 ₽ ->  403 коп.
  nano-banana-2.1     0.0320 × 105 =  3.36 ₽ ->  336 коп.
  seedance-2-5-flash  0.3183 × 105 = 33.42 ₽ -> 3342 коп.
  wan3.0-video        0.3288 × 105 = 34.52 ₽ -> 3452 коп.
  kling-v4            0.7000 × 105 = 73.50 ₽ -> 7350 коп.
Сверка с конкурентами и коррекция цен — отдельным заходом.

НЕ ЗАЯВЛЕНО (не проверялось): image-to-video, мультиреференс, редактирование,
резерв через CometAPI (у CometAPI имена/контракты этих моделей не подтверждены
живым вызовом) — поэтому cometapi_fallback_model не задан.

Подписи настроек: на aineron.net (INTL_MODE) — английские, на .ru — русские
(config_json фронт показывает как есть, без перевода — см. утечку RU на .net).
Описания: description_ru И description_en явно (см. c09ed68).

Запуск: docker compose exec web python manage.py add_media_models_2026_11_21 [--dry-run]
Идемпотентна; чужие модели не трогает (НЕ запускать add_video_models/
add_laozhang_models целиком — update_or_create сбросит ручные цены).
"""
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from aitext.models import Category, NeuralNetwork

EN = bool(getattr(settings, 'INTL_MODE', False))


def L(ru, en):
    return en if EN else ru


def _aspect_field(name, values):
    names = {'16:9': L('16:9 (горизонталь)', '16:9 (landscape)'),
             '9:16': L('9:16 (вертикаль)', '9:16 (portrait)'),
             '1:1': L('1:1 (квадрат)', '1:1 (square)')}
    if name == 'size':
        names['adaptive'] = L('Адаптивный', 'Adaptive')
    return {
        'name': name, 'type': 'select', 'label': L('Формат', 'Format'),
        'options': [{'label': names[v], 'value': v, 'extra_cost': 0} for v in values],
        'extra_cost': 0,
    }


def _video_config(name, api_defaults, field):
    return {
        'name': name,
        'metadata': {'video_api': 'apimart', 'output_type': 'video', 'supports_image_to_video': False},
        'constraints': {},
        'ui_settings': {'sections': [{
            'title': L('Настройки видео (5 сек, фиксировано)', 'Video settings (fixed 5 sec)'),
            'fields': [field],
        }]},
        'api_defaults': api_defaults,
    }


def _image_config(name):
    # minimal_params: apimart получает только model+prompt (как qwen-image-3.0).
    return {
        'name': name,
        'metadata': {'image_api': 'apimart_async', 'output_type': 'image',
                     'minimal_params': True, 'requires_input_images': False},
        'constraints': {}, 'api_defaults': {},
    }


MODELS = [
    {
        'name': 'Seedream 5.5', 'slug': 'seedream-5-5', 'model_name': 'seedream-5-5', 'cat': 'Изображения',
        'order': 97, 'cost_kopecks': 294, 'avatar_from': 'seedream-5-0',
        'config': _image_config('Seedream 5.5'),
        'description_ru': 'Новая версия Seedream от ByteDance — детальные изображения по текстовому описанию.',
        'description_en': 'The new Seedream release from ByteDance — detailed images from a text prompt.',
    },
    {
        'name': 'Flux 3 Image', 'slug': 'flux-3-image', 'model_name': 'flux-3-image', 'cat': 'Изображения',
        'order': 98, 'cost_kopecks': 403, 'avatar_from': 'flux-2-pro',
        'config': _image_config('Flux 3 Image'),
        'description_ru': 'Flux 3 — новое поколение модели Flux для генерации изображений по тексту.',
        'description_en': 'Flux 3 — the new generation of the Flux image model for text-to-image.',
    },
    {
        'name': 'Nano Banana 2.1', 'slug': 'nano-banana-2-1', 'model_name': 'gemini-nano-banana-2.1', 'cat': 'Изображения',
        'order': 99, 'cost_kopecks': 336, 'avatar_from': 'gemini-3-1-flash-image',
        'config': _image_config('Nano Banana 2.1'),
        'description_ru': 'Новая версия Nano Banana от Google (Gemini) — генерация изображений по тексту.',
        'description_en': 'The new Nano Banana release from Google (Gemini) — text-to-image generation.',
    },
    {
        'name': 'Seedance 2.5 Flash', 'slug': 'seedance-2-5-flash', 'model_name': 'seedance-2-5-flash', 'cat': 'Видео',
        'order': 100, 'cost_kopecks': 3342, 'avatar_from': 'seedance-2-5',
        'config': _video_config('Seedance 2.5 Flash',
                                {'size': 'adaptive', 'duration': '5', 'resolution': '480p', 'generate_audio': False},
                                _aspect_field('size', ['adaptive', '16:9', '9:16'])),
        'description_ru': 'Быстрая и доступная версия Seedance 2.5 от ByteDance — короткие видео по тексту (5 сек, 480p).',
        'description_en': 'The fast, affordable Seedance 2.5 variant from ByteDance — short text-to-video clips (5 sec, 480p).',
    },
    {
        'name': 'Wan 3.0', 'slug': 'wan-3-0', 'model_name': 'wan3.0-video', 'cat': 'Видео',
        'order': 101, 'cost_kopecks': 3452, 'avatar_from': 'wan-2-7',
        'config': _video_config('Wan 3.0',
                                {'duration': '5', 'resolution': '720p', 'aspect_ratio': '16:9'},
                                _aspect_field('aspect_ratio', ['16:9', '9:16'])),
        'description_ru': 'Новое поколение видеомодели Wan — видео по тексту (5 сек, 720p).',
        'description_en': 'The new generation of the Wan video model — text-to-video clips (5 sec, 720p).',
    },
    {
        'name': 'Kling v4', 'slug': 'kling-v4', 'model_name': 'kling-v4', 'cat': 'Видео',
        'order': 102, 'cost_kopecks': 7350, 'avatar_from': 'kling-3-0-turbo',
        'config': _video_config('Kling v4',
                                {'duration': '5', 'resolution': '720p', 'aspect_ratio': '16:9'},
                                _aspect_field('aspect_ratio', ['16:9', '9:16', '1:1'])),
        'description_ru': 'Новое поколение Kling — видео по тексту (5 сек, 720p).',
        'description_en': 'The new generation of Kling — text-to-video clips (5 sec, 720p).',
    },
]


class Command(BaseCommand):
    help = 'Добавляет 3 модели изображений и 3 модели видео (get_or_create по slug)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def _attach_avatar(self, network, spec):
        sib = NeuralNetwork.objects.filter(slug=spec['avatar_from']).first()
        if not (sib and sib.avatar):
            self.stdout.write(self.style.WARNING(f"  [WARN] {spec['slug']}: аватар-источник не найден"))
            return
        try:
            network.avatar.save(f"{spec['slug']}.png", ContentFile(sib.avatar.read()), save=True)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  [WARN] {spec['slug']}: аватар не скопирован: {e}"))

    def handle(self, *args, **options):
        dry = options['dry_run']
        created = 0
        for spec in MODELS:
            found = NeuralNetwork.objects.filter(slug=spec['slug']).first() \
                or NeuralNetwork.objects.filter(model_name=spec['model_name']).first()
            if found:
                self.stdout.write(self.style.WARNING(f"{spec['slug']}: уже существует (slug={found.slug}, id={found.id}), пропуск"))
                continue
            self.stdout.write(f"{spec['slug']}: создать \"{spec['name']}\" [{spec['cat']}] model_name={spec['model_name']} "
                              f"cost_kopecks={spec['cost_kopecks']} ({spec['cost_kopecks']/100:.2f}₽)")
            if dry:
                continue
            category = Category.objects.filter(name_ru=spec['cat']).first() \
                or Category.objects.get_or_create(name=spec['cat'])[0]
            network = NeuralNetwork.objects.create(
                name=spec['name'], slug=spec['slug'], category=category,
                description_ru=spec['description_ru'], description_en=spec['description_en'],
                model_name=spec['model_name'], provider='fal-ai', order=spec['order'],
                cost_per_message=max(spec['cost_kopecks'] // 100, 1), cost_kopecks=spec['cost_kopecks'],
                is_active=True, is_new=True, handle_photo=False, handle_text_files=False,
                translate_to_english=False, config_json=spec['config'],
            )
            self._attach_avatar(network, spec)
            created += 1
        self.stdout.write(self.style.WARNING('\n--dry-run: не сохранено') if dry
                          else self.style.SUCCESS(f'\nГотово: создано {created}'))
