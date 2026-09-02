"""
Видео-модели через apimart.ai.
Запуск: docker-compose exec web python manage.py add_video_models

Конфиги сверены с официальной документацией apimart (video API):
допустимые параметры, диапазоны длительности, разрешения и способ
передачи изображения для image-to-video заданы per-model.

Повторный запуск обновляет config_json/название/описание/порядок
существующих моделей (цены не трогает), создаёт недостающие и
деактивирует видео-модели, которых нет в списке.
"""
from django.core.management.base import BaseCommand
from aitext.models import Category, NeuralNetwork


def _aspect_field(values):
    """Поле «Формат кадра» из списка соотношений сторон."""
    labels = {
        '16:9': '16:9 (горизонталь)',
        '9:16': '9:16 (вертикаль)',
        '1:1': '1:1 (квадрат)',
        '4:3': '4:3 (традиционный)',
        '3:4': '3:4 (вертикальный)',
        '21:9': '21:9 (сверхширокий)',
        '3:2': '3:2 (альбомный)',
        '2:3': '2:3 (портретный)',
        'adaptive': 'Адаптивный (по фото)',
    }
    return {
        "name": "aspect_ratio",
        "type": "select",
        "label": "Формат",
        "extra_cost": 0,
        "options": [
            {"value": v, "label": labels.get(v, v), "extra_cost": 0} for v in values
        ],
    }


def _duration_field(options):
    """Поле «Длительность»: options = [(секунды, доплата), ...]."""
    return {
        "name": "duration",
        "type": "select",
        "label": "Длительность",
        "extra_cost": 0,
        "options": [
            {"value": str(sec), "label": f"{sec} сек", "extra_cost": cost}
            for sec, cost in options
        ],
    }


VIDEO_CONFIG = {
    # ------------------------------------------------------------------
    # Sora 2 — базовая модель OpenAI: только 720p, duration 4/8/12/16/20.
    # i2v: image_urls (1 фото, до 10 МБ); aspect_ratio при фото игнорируется.
    # ------------------------------------------------------------------
    'sora2': {
        "name": "Sora 2",
        "api_defaults": {"duration": "4", "aspect_ratio": "16:9"},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    _aspect_field(["16:9", "9:16"]),
                    _duration_field([(4, 0), (8, 5), (12, 15), (16, 25), (20, 35)]),
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "image_urls",
        },
    },

    # ------------------------------------------------------------------
    # Sora 2 Pro — выбор разрешения (720p / 1024p / 1080p)
    # ------------------------------------------------------------------
    'sora2_pro': {
        "name": "Sora 2 Pro",
        "api_defaults": {"duration": "4", "aspect_ratio": "16:9", "resolution": "720p"},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    _aspect_field(["16:9", "9:16"]),
                    _duration_field([(4, 0), (8, 5), (12, 15), (16, 25), (20, 35)]),
                    {
                        "name": "resolution",
                        "type": "select",
                        "label": "Разрешение",
                        "extra_cost": 0,
                        "options": [
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 0},
                            {"value": "1024p", "label": "1024p", "extra_cost": 10},
                            {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 15},
                        ]
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "image_urls",
        },
    },

    # ------------------------------------------------------------------
    # Veo 3.1 Fast — длительность фиксирована 8 сек; i2v image_urls (до 3)
    # ------------------------------------------------------------------
    'veo3_fast': {
        "name": "Veo 3.1 Fast",
        "api_defaults": {"duration": 8, "aspect_ratio": "16:9", "resolution": "720p"},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео (8 сек, фиксировано)",
                "fields": [
                    _aspect_field(["16:9", "9:16"]),
                    {
                        "name": "resolution",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 0},
                            {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 10},
                            {"value": "4k", "label": "4K (Ultra HD)", "extra_cost": 30},
                        ]
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "image_urls",
            "i2v_max_images": 3, "i2v_mode": "reference",
            # B14: единственные 2 модели с подтверждённым вживую фолбэком на
            # laozhang (см. generate_video_laozhang) — для остальных 11 laozhang
            # не провижинировал канал под наш аккаунт (503 no available channels),
            # проставлять им этот ключ значит тихо ловить гарантированную ошибку.
            "laozhang_fallback_model": "veo-3.1-fast-generate-preview",
        },
    },

    # ------------------------------------------------------------------
    # Veo 3.1 Quality — те же опции, другое качество по умолчанию
    # ------------------------------------------------------------------
    'veo3_quality': {
        "name": "Veo 3.1",
        "api_defaults": {"duration": 8, "aspect_ratio": "16:9", "resolution": "1080p"},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео (8 сек, фиксировано)",
                "fields": [
                    _aspect_field(["16:9", "9:16"]),
                    {
                        "name": "resolution",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 0},
                            {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 0},
                            {"value": "4k", "label": "4K (Ultra HD)", "extra_cost": 20},
                        ]
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "image_urls",
            # 2026-09-02: по документации apimart Quality НЕ поддерживает
            # generation_type=reference (было ошибочно как у veo3_fast,
            # max_images:3) — только frame-режим (первый+последний, до 2 фото).
            "i2v_max_images": 2, "i2v_mode": "first_last",
            "laozhang_fallback_model": "veo-3.1-generate-preview",  # B14, см. veo3_fast
        },
    },

    # ------------------------------------------------------------------
    # Kling v2.6 — std(720p)/pro(1080p), duration 5|10, аудио только в pro
    # (при включённом аудио fal_utils сам переключает mode в pro).
    # i2v: image_urls (1-2 фото; 2 = первый+последний кадр, только pro).
    # ------------------------------------------------------------------
    'kling_v26': {
        "name": "Kling v2.6",
        "api_defaults": {"mode": "std", "duration": "5", "aspect_ratio": "16:9", "audio": False},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    _aspect_field(["16:9", "9:16", "1:1"]),
                    _duration_field([(5, 0), (10, 8)]),
                    {
                        "name": "mode",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "std", "label": "720p (стандарт)", "extra_cost": 0},
                            {"value": "pro", "label": "1080p (профессионал)", "extra_cost": 5},
                        ]
                    },
                    {
                        "name": "audio",
                        "type": "checkbox",
                        "label": "Звук (автоматически включает режим 1080p)",
                        "extra_cost": 5,
                    },
                    {
                        "name": "negative_prompt",
                        "type": "text",
                        "label": "Negative prompt",
                        "extra_cost": 0,
                        "max_length": 2500,
                    },
                ]
            }]
        },
        "constraints": {"max_negative_prompt_length": 2500},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "image_urls",
            "i2v_max_images": 2, "i2v_mode": "first_last",
        },
    },

    # ------------------------------------------------------------------
    # Kling v3 — режимы std/pro/4k, duration 3-15, аудио во ВСЕХ режимах
    # ------------------------------------------------------------------
    'kling_v3': {
        "name": "Kling v3",
        "api_defaults": {"mode": "std", "duration": "5", "aspect_ratio": "16:9", "audio": False},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    _aspect_field(["16:9", "9:16", "1:1"]),
                    _duration_field([(3, 0), (5, 0), (8, 10), (10, 18), (15, 30)]),
                    {
                        "name": "mode",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "std", "label": "720p (стандарт)", "extra_cost": 0},
                            {"value": "pro", "label": "1080p (профессионал)", "extra_cost": 15},
                            {"value": "4k", "label": "4K (Ultra HD)", "extra_cost": 40},
                        ]
                    },
                    {
                        "name": "audio",
                        "type": "checkbox",
                        "label": "Сгенерировать звук",
                        "extra_cost": 5,
                    },
                    {
                        "name": "negative_prompt",
                        "type": "text",
                        "label": "Negative prompt",
                        "extra_cost": 0,
                        "max_length": 2500,
                    },
                ]
            }]
        },
        "constraints": {"max_negative_prompt_length": 2500},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "image_urls",
            "i2v_max_images": 2, "i2v_mode": "first_last",
        },
    },

    # ------------------------------------------------------------------
    # Seedance 1.5 Pro — ByteDance, duration 4-12, audio, camerafixed
    # ------------------------------------------------------------------
    'seedance15pro': {
        "name": "Seedance 1.5 Pro",
        "api_defaults": {"duration": "5", "aspect_ratio": "16:9", "resolution": "720p", "audio": False},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    _aspect_field(["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"]),
                    _duration_field([(4, 0), (5, 0), (6, 3), (8, 8), (10, 15), (12, 20)]),
                    {
                        "name": "resolution",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "480p", "label": "480p (стандарт)", "extra_cost": 0},
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 0},
                            {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 10},
                        ]
                    },
                    {
                        "name": "audio",
                        "type": "checkbox",
                        "label": "Сгенерировать аудиодорожку",
                        "extra_cost": 0,
                    },
                    {
                        "name": "camerafixed",
                        "type": "checkbox",
                        "label": "Фиксированная камера",
                        "extra_cost": 0,
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "image_urls",
        },
    },

    # ------------------------------------------------------------------
    # Seedance 2.0 — size (не aspect_ratio!) вкл. adaptive, до 4K,
    # generate_audio; i2v image_urls (до 9 референсов)
    # ------------------------------------------------------------------
    'seedance20': {
        "name": "Seedance 2.0",
        "api_defaults": {"duration": "5", "size": "adaptive", "resolution": "720p", "generate_audio": False, "camerafixed": False},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    {
                        "name": "size",
                        "type": "select",
                        "label": "Формат",
                        "extra_cost": 0,
                        "options": [
                            {"value": "adaptive", "label": "Адаптивный", "extra_cost": 0},
                            {"value": "16:9", "label": "16:9 (горизонталь)", "extra_cost": 0},
                            {"value": "9:16", "label": "9:16 (вертикаль)", "extra_cost": 0},
                            {"value": "1:1", "label": "1:1 (квадрат)", "extra_cost": 0},
                            {"value": "4:3", "label": "4:3 (традиционный)", "extra_cost": 0},
                            {"value": "3:4", "label": "3:4 (вертикальный)", "extra_cost": 0},
                            {"value": "21:9", "label": "21:9 (сверхширокий)", "extra_cost": 0},
                        ]
                    },
                    _duration_field([(4, 0), (5, 0), (6, 3), (8, 8), (10, 15), (12, 20), (15, 30)]),
                    {
                        "name": "resolution",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "480p", "label": "480p (стандарт)", "extra_cost": 0},
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 0},
                            {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 10},
                            {"value": "4k", "label": "4K (Ultra HD)", "extra_cost": 30},
                        ]
                    },
                    {
                        "name": "generate_audio",
                        "type": "checkbox",
                        "label": "Сгенерировать аудиодорожку",
                        "extra_cost": 0,
                    },
                    {
                        "name": "camerafixed",
                        "type": "checkbox",
                        "label": "Фиксированная камера",
                        "extra_cost": 0,
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "image_urls",
            "i2v_max_images": 9, "i2v_mode": "reference",
        },
    },

    # ------------------------------------------------------------------
    # MiniMax Hailuo 2.3 — duration 6|10, resolution 768p|1080p
    # (1080p только для 6 сек — fal_utils сам понижает длительность).
    # i2v: first_frame_image (URL).
    # ------------------------------------------------------------------
    'hailuo23': {
        "name": "Hailuo 2.3",
        "api_defaults": {"duration": "6", "resolution": "768p", "prompt_optimizer": True},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    _duration_field([(6, 0), (10, 10)]),
                    {
                        "name": "resolution",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "768p", "label": "768p (HD)", "extra_cost": 0},
                            {"value": "1080p", "label": "1080p (Full HD, только 6 сек)", "extra_cost": 10},
                        ]
                    },
                    {
                        "name": "prompt_optimizer",
                        "type": "checkbox",
                        "label": "Автоулучшение промта",
                        "extra_cost": 0,
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "first_frame_image",
        },
    },

    # ------------------------------------------------------------------
    # Wan 2.6 — duration 5|10|15, звук, шаблоны-эффекты (template),
    # мультикадровая съёмка (shot_type). i2v: image_urls (1 фото).
    # ------------------------------------------------------------------
    'wan26': {
        "name": "Wan 2.6",
        "api_defaults": {"duration": "5", "resolution": "720p", "aspect_ratio": "16:9", "audio": False},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    _aspect_field(["16:9", "9:16", "1:1", "4:3", "3:4"]),
                    _duration_field([(5, 0), (10, 8), (15, 15)]),
                    {
                        "name": "resolution",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 0},
                            {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 10},
                        ]
                    },
                    {
                        "name": "audio",
                        "type": "checkbox",
                        "label": "Сгенерировать звук",
                        "extra_cost": 0,
                    },
                    {
                        "name": "shot_type",
                        "type": "select",
                        "label": "Съёмка",
                        "extra_cost": 0,
                        "options": [
                            {"value": "single", "label": "Один план", "extra_cost": 0},
                            {"value": "multi", "label": "Смена планов", "extra_cost": 0},
                        ]
                    },
                    {
                        "name": "template",
                        "type": "select",
                        "label": "Эффект (для оживления фото)",
                        "extra_cost": 0,
                        "options": [
                            {"value": "none", "label": "Без эффекта", "extra_cost": 0},
                            {"value": "squish", "label": "Сжатие", "extra_cost": 0},
                            {"value": "rotation", "label": "Вращение", "extra_cost": 0},
                            {"value": "poke", "label": "Тычок", "extra_cost": 0},
                            {"value": "inflate", "label": "Надувание", "extra_cost": 0},
                            {"value": "dissolve", "label": "Растворение", "extra_cost": 0},
                            {"value": "melt", "label": "Таяние", "extra_cost": 0},
                            {"value": "icecream", "label": "Мороженое", "extra_cost": 0},
                            {"value": "flying", "label": "Полёт", "extra_cost": 0},
                            {"value": "carousel", "label": "Карусель", "extra_cost": 0},
                            {"value": "singleheart", "label": "Сердце", "extra_cost": 0},
                            {"value": "dance1", "label": "Танец 1", "extra_cost": 0},
                            {"value": "dance2", "label": "Танец 2", "extra_cost": 0},
                        ]
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "image_urls",
        },
    },

    # ------------------------------------------------------------------
    # Pixverse v6 — бюджетная модель: 360p-1080p, duration 3-15, звук,
    # 8 форматов кадра. i2v: image_urls.
    # ------------------------------------------------------------------
    'pixverse6': {
        "name": "Pixverse v6",
        "api_defaults": {"duration": "5", "resolution": "540p", "size": "16:9", "audio": False},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    {
                        "name": "size",
                        "type": "select",
                        "label": "Формат",
                        "extra_cost": 0,
                        "options": [
                            {"value": "16:9", "label": "16:9 (горизонталь)", "extra_cost": 0},
                            {"value": "9:16", "label": "9:16 (вертикаль)", "extra_cost": 0},
                            {"value": "1:1", "label": "1:1 (квадрат)", "extra_cost": 0},
                            {"value": "4:3", "label": "4:3 (традиционный)", "extra_cost": 0},
                            {"value": "3:4", "label": "3:4 (вертикальный)", "extra_cost": 0},
                            {"value": "3:2", "label": "3:2 (альбомный)", "extra_cost": 0},
                            {"value": "2:3", "label": "2:3 (портретный)", "extra_cost": 0},
                            {"value": "21:9", "label": "21:9 (сверхширокий)", "extra_cost": 0},
                        ]
                    },
                    _duration_field([(3, 0), (5, 0), (8, 5), (10, 8), (15, 12)]),
                    {
                        "name": "resolution",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "360p", "label": "360p (эконом)", "extra_cost": 0},
                            {"value": "540p", "label": "540p (стандарт)", "extra_cost": 0},
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 5},
                            {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 12},
                        ]
                    },
                    {
                        "name": "audio",
                        "type": "checkbox",
                        "label": "Сгенерировать звук",
                        "extra_cost": 0,
                    },
                    {
                        "name": "negative_prompt",
                        "type": "text",
                        "label": "Negative prompt",
                        "extra_cost": 0,
                        "max_length": 2048,
                    },
                ]
            }]
        },
        "constraints": {"max_negative_prompt_length": 2048},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "image_urls",
        },
    },

    # ------------------------------------------------------------------
    # Vidu Q3 Turbo — duration до 16 сек, звук включён по умолчанию.
    # i2v: image_urls (1 = первый кадр, 2 = первый+последний).
    # ------------------------------------------------------------------
    'viduq3_turbo': {
        "name": "Vidu Q3 Turbo",
        "api_defaults": {"duration": "5", "resolution": "720p", "aspect_ratio": "16:9", "audio": True},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    _aspect_field(["16:9", "9:16", "1:1", "4:3", "3:4"]),
                    _duration_field([(4, 0), (5, 0), (8, 6), (12, 12), (16, 18)]),
                    {
                        "name": "resolution",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "540p", "label": "540p (стандарт)", "extra_cost": 0},
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 0},
                            {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 10},
                        ]
                    },
                    {
                        "name": "audio",
                        "type": "checkbox",
                        "label": "Сгенерировать звук",
                        "extra_cost": 0,
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "image_urls",
            "i2v_max_images": 2, "i2v_mode": "first_last",
        },
    },

    # ------------------------------------------------------------------
    # Grok Imagine 1.5 (xAI) — параметр качества называется quality
    # (не resolution!), длительность 6-30 сек. i2v: image_urls (до 7).
    # ------------------------------------------------------------------
    'grok15': {
        "name": "Grok Imagine 1.5",
        "api_defaults": {"duration": "6", "quality": "480p", "size": "16:9"},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    {
                        "name": "size",
                        "type": "select",
                        "label": "Формат",
                        "extra_cost": 0,
                        "options": [
                            {"value": "16:9", "label": "16:9 (горизонталь)", "extra_cost": 0},
                            {"value": "9:16", "label": "9:16 (вертикаль)", "extra_cost": 0},
                            {"value": "1:1", "label": "1:1 (квадрат)", "extra_cost": 0},
                            {"value": "3:2", "label": "3:2 (альбомный)", "extra_cost": 0},
                            {"value": "2:3", "label": "2:3 (портретный)", "extra_cost": 0},
                        ]
                    },
                    _duration_field([(6, 0), (10, 5), (15, 10), (20, 18), (30, 30)]),
                    {
                        "name": "quality",
                        "type": "select",
                        "label": "Качество",
                        "extra_cost": 0,
                        "options": [
                            {"value": "480p", "label": "480p (стандарт)", "extra_cost": 0},
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 10},
                        ]
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "image_urls",
            "i2v_max_images": 7, "i2v_mode": "reference",
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # B14 (2026-07-24) — расширение каталога. Настройки для моделей,
    # которые являются старшей версией уже интегрированной модели того же
    # вендора (wan27, klingturbo, hailuo23fast, viduq3pro,
    # seedance20fast, veo3lite) — скопированы с проверенного на практике
    # конфига-донора, тот же вендор почти наверняка сохраняет контракт
    # параметров между поколениями. Для моделей с уникальной, ранее не
    # интегрированной способностью (kling-v3-motion-control, kling-v3-omni)
    # сознательно даём БАЗОВЫЙ набор полей (общий с
    # ближайшим родственником), а не гадаем экзотические имена параметров
    # под саму уникальную способность (motion trajectory / multi-reference
    # omni) — это не проверено вживую, добавить отдельным полем можно после
    # реальной проверки контракта, чем сейчас рисковать отклонённым запросом
    # на придуманном имени параметра.
    # ══════════════════════════════════════════════════════════════════

    # Wan 2.7 — следующее поколение Wan после уже интегрированного wan2.6,
    # тот же вендор (Alibaba), тот же набор полей.
    'wan27': {
        "name": "Wan 2.7",
        "api_defaults": {"duration": "5", "resolution": "720p", "aspect_ratio": "16:9", "audio": False},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    _aspect_field(["16:9", "9:16", "1:1", "4:3", "3:4"]),
                    _duration_field([(5, 0), (10, 8), (15, 15)]),
                    {
                        "name": "resolution", "type": "select", "label": "Качество", "extra_cost": 0,
                        "options": [
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 0},
                            {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 10},
                        ]
                    },
                    {"name": "audio", "type": "checkbox", "label": "Сгенерировать звук", "extra_cost": 0},
                    {
                        "name": "shot_type", "type": "select", "label": "Съёмка", "extra_cost": 0,
                        "options": [
                            {"value": "single", "label": "Один план", "extra_cost": 0},
                            {"value": "multi", "label": "Смена планов", "extra_cost": 0},
                        ]
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "image_urls",
        },
    },

    # Seedance 2.5 — 2026-09-02: заменяет прежнюю запись "Seedance 4.5"
    # (model_name doubao-seedance-4-5) — такой модели у apimart не
    # существует вообще, актуальная новейшая версия линейки Seedance
    # называется seedance-2.5 (подтверждено документацией и баннером
    # "APIMart Officially Launches doubao seedance 2.5 API"). В отличие
    # от 2.0: нет 4K (макс. 1080p), диапазон duration шире (4-30 сек,
    # либо -1 — автовыбор моделью), до 30 референсных изображений
    # (не 9), новое поле watermark. Поле camerafixed для 2.5 в
    # документации отсутствует — не переносим из конфига 2.0.
    'seedance25': {
        "name": "Seedance 2.5",
        "api_defaults": {"duration": "5", "size": "adaptive", "resolution": "480p", "generate_audio": True},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    {
                        "name": "size", "type": "select", "label": "Формат", "extra_cost": 0,
                        "options": [
                            {"value": "adaptive", "label": "Адаптивный", "extra_cost": 0},
                            {"value": "16:9", "label": "16:9 (горизонталь)", "extra_cost": 0},
                            {"value": "9:16", "label": "9:16 (вертикаль)", "extra_cost": 0},
                            {"value": "1:1", "label": "1:1 (квадрат)", "extra_cost": 0},
                            {"value": "4:3", "label": "4:3 (традиционный)", "extra_cost": 0},
                            {"value": "3:4", "label": "3:4 (вертикальный)", "extra_cost": 0},
                            {"value": "21:9", "label": "21:9 (сверхширокий)", "extra_cost": 0},
                        ]
                    },
                    _duration_field([(4, 0), (5, 0), (8, 10), (10, 15), (15, 25), (20, 35), (25, 45), (30, 55)]),
                    {
                        "name": "resolution", "type": "select", "label": "Качество", "extra_cost": 0,
                        "options": [
                            {"value": "480p", "label": "480p (стандарт)", "extra_cost": 0},
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 10},
                            {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 20},
                        ]
                    },
                    {"name": "generate_audio", "type": "checkbox", "label": "Сгенерировать аудиодорожку", "extra_cost": 0},
                    {"name": "watermark", "type": "checkbox", "label": "Водяной знак «AI generated»", "extra_cost": 0},
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "image_urls",
            "i2v_max_images": 30, "i2v_mode": "reference",
        },
    },

    # Kling 3.0 Turbo — новый флагман Kuaishou (турбо-тир). У этой модели
    # ДРУГОЙ контракт API, чем у остальных Kling: качество регулируется
    # `resolution` (не `mode`), фото передаётся `first_frame_image`
    # (одна строка, не массив `image_urls`), audio/negative_prompt на её
    # странице документации не встречаются — раньше был ошибочно
    # скопирован набор полей kling_v3, из-за чего доплата за "pro"-качество
    # (extra_cost 15) не долетала до провайдера как ожидаемый параметр.
    # Исправлено 2026-09-02.
    'kling30turbo': {
        "name": "Kling 3.0 Turbo",
        "api_defaults": {"resolution": "720p", "duration": "5", "aspect_ratio": "16:9"},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    _aspect_field(["16:9", "9:16", "1:1"]),
                    _duration_field([(3, 0), (5, 0), (8, 10), (10, 18)]),
                    {
                        "name": "resolution", "type": "select", "label": "Качество", "extra_cost": 0,
                        "options": [
                            {"value": "720p", "label": "720p (стандарт)", "extra_cost": 0},
                            {"value": "1080p", "label": "1080p (профессионал)", "extra_cost": 15},
                        ]
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "first_frame_image",
        },
    },

    # Kling v3 Motion Control — базовый набор полей идентичен kling_v3.
    # ПРОВЕРЕНО ВЖИВУЮ (2026-07-27): модель НЕ принимает фото. apimart
    # отвечает 400 "video_url is required for kling motion-control models" —
    # это перенос движения/траектории камеры с ИСХОДНОГО ВИДЕО, не img2video
    # по фото. Загрузки видео в проекте нет, поэтому img2video-метаданные
    # сюда сознательно не добавляем (раньше здесь ошибочно стояли
    # image_urls/i2v_max_images — снято той же правкой).
    'klingv3motion': {
        "name": "Kling v3 Motion Control",
        "api_defaults": {"mode": "std", "duration": "5", "aspect_ratio": "16:9", "audio": False},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    _aspect_field(["16:9", "9:16", "1:1"]),
                    _duration_field([(3, 0), (5, 0), (8, 10), (10, 18), (15, 30)]),
                    {
                        "name": "mode", "type": "select", "label": "Качество", "extra_cost": 0,
                        "options": [
                            {"value": "std", "label": "720p (стандарт)", "extra_cost": 0},
                            {"value": "pro", "label": "1080p (профессионал)", "extra_cost": 15},
                            {"value": "4k", "label": "4K (Ultra HD)", "extra_cost": 40},
                        ]
                    },
                    {"name": "audio", "type": "checkbox", "label": "Сгенерировать звук", "extra_cost": 5},
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
        },
    },

    # Kling v3 Omni — многореференсный режим (персонаж+сцена); базовый набор
    # полей идентичен kling_v3, параметры мульти-референса не проверены
    # вживую и намеренно не добавлены (см. комментарий выше блока).
    'klingv3omni': {
        "name": "Kling v3 Omni",
        "api_defaults": {"mode": "std", "duration": "5", "aspect_ratio": "16:9", "audio": False},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    _aspect_field(["16:9", "9:16", "1:1"]),
                    _duration_field([(3, 0), (5, 0), (8, 10), (10, 18), (15, 30)]),
                    {
                        "name": "mode", "type": "select", "label": "Качество", "extra_cost": 0,
                        "options": [
                            {"value": "std", "label": "720p (стандарт)", "extra_cost": 0},
                            {"value": "pro", "label": "1080p (профессионал)", "extra_cost": 15},
                            {"value": "4k", "label": "4K (Ultra HD)", "extra_cost": 40},
                        ]
                    },
                    {"name": "audio", "type": "checkbox", "label": "Сгенерировать звук", "extra_cost": 5},
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "image_urls",
            "i2v_max_images": 2, "i2v_mode": "first_last",
        },
    },

    # MiniMax Hailuo 2.3 Fast — бюджетный/быстрый тир уже интегрированного
    # Hailuo 2.3, тот же набор полей. 2026-09-02: по документации apimart
    # Fast-тир обязательно требует first_frame_image (чистый text-to-video
    # недоступен) — добавлен requires_input_images, иначе пользователь мог
    # отправить только текст и получить гарантированный сбой без объяснения.
    'hailuo23fast': {
        "name": "Hailuo 2.3 Fast",
        "api_defaults": {"duration": "6", "resolution": "768p", "prompt_optimizer": True},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    _duration_field([(6, 0), (10, 6)]),
                    {
                        "name": "resolution", "type": "select", "label": "Качество", "extra_cost": 0,
                        "options": [
                            {"value": "768p", "label": "768p (HD)", "extra_cost": 0},
                            {"value": "1080p", "label": "1080p (Full HD, только 6 сек)", "extra_cost": 8},
                        ]
                    },
                    {"name": "prompt_optimizer", "type": "checkbox", "label": "Автоулучшение промта", "extra_cost": 0},
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "requires_input_images": True,
            "supports_image_to_video": True, "i2v_param": "first_frame_image",
        },
    },

    # Vidu Q3 Pro — старший тир над уже интегрированным viduq3-turbo.
    'viduq3pro': {
        "name": "Vidu Q3 Pro",
        "api_defaults": {"duration": "5", "resolution": "1080p", "aspect_ratio": "16:9", "audio": True},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    _aspect_field(["16:9", "9:16", "1:1", "4:3", "3:4"]),
                    _duration_field([(4, 0), (5, 0), (8, 8), (12, 15), (16, 22)]),
                    {
                        "name": "resolution", "type": "select", "label": "Качество", "extra_cost": 0,
                        "options": [
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 0},
                            {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 0},
                        ]
                    },
                    {"name": "audio", "type": "checkbox", "label": "Сгенерировать звук", "extra_cost": 0},
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "image_urls",
            "i2v_max_images": 2, "i2v_mode": "first_last",
        },
    },

    # Seedance 2.0 Fast — быстрый/дешёвый тир уже интегрированного seedance20,
    # тот же набор полей (без 4K — быстрый тир его не даёт).
    'seedance20fast': {
        "name": "Seedance 2.0 Fast",
        "api_defaults": {"duration": "5", "size": "adaptive", "resolution": "720p", "generate_audio": False},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    {
                        "name": "size", "type": "select", "label": "Формат", "extra_cost": 0,
                        "options": [
                            {"value": "adaptive", "label": "Адаптивный", "extra_cost": 0},
                            {"value": "16:9", "label": "16:9 (горизонталь)", "extra_cost": 0},
                            {"value": "9:16", "label": "9:16 (вертикаль)", "extra_cost": 0},
                            {"value": "1:1", "label": "1:1 (квадрат)", "extra_cost": 0},
                        ]
                    },
                    _duration_field([(4, 0), (5, 0), (6, 3), (8, 6), (10, 10)]),
                    {
                        "name": "resolution", "type": "select", "label": "Качество", "extra_cost": 0,
                        "options": [
                            {"value": "480p", "label": "480p (стандарт)", "extra_cost": 0},
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 0},
                            {"value": "1080p", "label": "1080p (Full HD)", "extra_cost": 8},
                        ]
                    },
                    {"name": "generate_audio", "type": "checkbox", "label": "Сгенерировать аудиодорожку", "extra_cost": 0},
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "supports_image_to_video": True, "i2v_param": "image_urls",
            "i2v_max_images": 9, "i2v_mode": "reference",
        },
    },

    # Veo 3.1 Lite — бюджетный тир Veo 3.1 ниже уже интегрированного Fast.
    # 2026-09-02: по документации apimart Lite вообще не принимает
    # image_urls/generation_type/official_fallback — img2video для неё
    # снят (раньше стоял ошибочно скопированный с veo3_fast конфиг).
    'veo3lite': {
        "name": "Veo 3.1 Lite",
        "api_defaults": {"duration": 8, "aspect_ratio": "16:9", "resolution": "720p"},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео (8 сек, фиксировано)",
                "fields": [
                    _aspect_field(["16:9", "9:16"]),
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # Добавлено 2026-07-27, каждый конфиг проверен вживую до status=completed
    # с реальным URL готового видео (не просто "create-запрос принят") — см.
    # project_model_catalog_2026_07_27 в памяти сессии про предыдущий баг
    # (kling-v3-motion-control), где "200 submitted" оказалось недостаточным
    # доказательством и модель на деле всегда падала.
    # ══════════════════════════════════════════════════════════════════

    # Kling Video O1 — новое поколение Kling поверх уже интегрированного v3.
    # Проверено вживую ТОЛЬКО text-to-video (mode=std) — img2video-контракт
    # для этой модели не проверялся, поэтому img2video-метаданные сознательно
    # не проставлены (см. комментарий про kling-v3-motion-control выше).
    # 2026-09-02: убрана доплата за "audio" (extra_cost 5) — по документации
    # apimart параметр audio для этой модели не встречается вообще, в отличие
    # от kling_v2_6/kling_v3, где он явно задокументирован.
    'klingvideoo1': {
        "name": "Kling Video O1",
        "api_defaults": {"mode": "std", "duration": "5", "aspect_ratio": "16:9"},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    _aspect_field(["16:9", "9:16", "1:1"]),
                    _duration_field([(3, 0), (5, 0), (8, 10), (10, 18)]),
                    {
                        "name": "mode", "type": "select", "label": "Качество", "extra_cost": 0,
                        "options": [
                            {"value": "std", "label": "720p (стандарт)", "extra_cost": 0},
                            {"value": "pro", "label": "1080p (профессионал)", "extra_cost": 15},
                        ]
                    },
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
        },
    },

    # Vidu Q3 (базовый тир) — в отличие от Turbo/Pro этот тир ТОЛЬКО
    # reference2video: apimart отклоняет запрос без фото ("requires 1 to 7
    # reference images"), чистого text-to-video здесь нет. requires_input_images
    # заставляет validate_and_merge_settings отклонить запрос без фото ДО
    # отправки — иначе пользователь заплатит и получит гарантированный сбой.
    'viduq3base': {
        "name": "Vidu Q3",
        "api_defaults": {"duration": "5", "resolution": "540p", "aspect_ratio": "16:9", "audio": False},
        "ui_settings": {
            "sections": [{
                "title": "Настройки видео",
                "fields": [
                    _aspect_field(["16:9", "9:16", "1:1", "4:3", "3:4"]),
                    _duration_field([(4, 0), (5, 0), (8, 6)]),
                    {
                        "name": "resolution", "type": "select", "label": "Качество", "extra_cost": 0,
                        "options": [
                            {"value": "540p", "label": "540p (стандарт)", "extra_cost": 0},
                            {"value": "720p", "label": "720p (HD)", "extra_cost": 0},
                        ]
                    },
                    {"name": "audio", "type": "checkbox", "label": "Сгенерировать звук", "extra_cost": 0},
                ]
            }]
        },
        "constraints": {},
        "metadata": {
            "output_type": "video", "video_api": "apimart",
            "requires_input_images": True,
            "supports_image_to_video": True, "i2v_param": "image_urls",
            "i2v_max_images": 7, "i2v_mode": "reference",
        },
    },
}


VIDEO_MODELS = [
    dict(
        name='Sora 2',
        slug='sora-character',
        model_name='sora-2',
        cost_per_message=60,
        order=1,
        description='Генерация видео от OpenAI. Создаёт реалистичные короткие видеоролики по текстовому описанию.',
        config_key='sora2',
        is_popular=True,
    ),
    dict(
        name='Sora 2 Pro',
        slug='sora-2-character',
        model_name='sora-2-pro',
        cost_per_message=100,
        order=2,
        description='Продвинутая версия Sora 2 от OpenAI — выбор разрешения до 1080p, максимальная детализация.',
        config_key='sora2_pro',
        is_popular=False,
    ),
    dict(
        name='Veo 3.1 Fast',
        slug='veo-3-1-fast',
        model_name='veo3.1-fast',
        cost_per_message=50,
        order=3,
        description='Быстрая генерация видео от Google DeepMind. Высокое качество движения и деталей.',
        config_key='veo3_fast',
        is_popular=True,
    ),
    dict(
        name='Veo 3.1',
        slug='veo-3-1',
        model_name='veo3.1-quality',
        cost_per_message=100,
        order=4,
        description='Полное качество Veo 3.1 от Google DeepMind. Максимальная детализация и фотореализм.',
        config_key='veo3_quality',
        is_popular=False,
    ),
    dict(
        name='Kling v2.6',
        slug='kling-v26',
        model_name='kling-v2-6',
        cost_per_message=40,
        order=5,
        description='Генерация видео от Kuaishou с поддержкой аудиосопровождения. Быстрый и качественный результат.',
        config_key='kling_v26',
        is_popular=True,
    ),
    dict(
        name='Kling v3',
        slug='kling-v3',
        model_name='kling-v3',
        cost_per_message=60,
        order=6,
        description='Флагман Kuaishou: до 15 секунд, режимы вплоть до 4K, звук во всех режимах, оживление фото.',
        config_key='kling_v3',
        is_popular=True,
    ),
    dict(
        name='Seedance 1.5 Pro',
        slug='seedance-1-5-pro',
        model_name='doubao-seedance-1-5-pro',
        cost_per_message=35,
        order=7,
        description='Генерация видео от ByteDance. Поддержка аудио, фиксированной камеры и 6 форматов кадра.',
        config_key='seedance15pro',
        is_popular=True,
    ),
    dict(
        name='Seedance 2.0',
        slug='seedance-2-0',
        model_name='doubao-seedance-2.0',
        cost_per_message=45,
        order=8,
        description='Новейшая модель ByteDance Seedance 2.0. Длительность до 15 сек, 4K, аудиодорожка, адаптивный формат.',
        config_key='seedance20',
        is_popular=True,
    ),
    dict(
        name='Hailuo 2.3',
        slug='hailuo-2-3',
        model_name='MiniMax-Hailuo-2.3',
        cost_per_message=40,
        order=9,
        description='MiniMax Hailuo 2.3 — кинематографичное движение и точная физика. Отлично оживляет фото.',
        config_key='hailuo23',
        is_popular=False,
    ),
    dict(
        name='Wan 2.6',
        slug='wan-2-6',
        model_name='wan2.6',
        cost_per_message=40,
        order=10,
        description='Alibaba Wan 2.6 — до 15 секунд со звуком, смена планов и весёлые эффекты для оживления фото.',
        config_key='wan26',
        is_popular=False,
    ),
    dict(
        name='Vidu Q3 Turbo',
        slug='vidu-q3-turbo',
        model_name='viduq3-turbo',
        cost_per_message=30,
        order=11,
        description='Vidu Q3 Turbo — быстрые видео до 16 секунд со звуком по умолчанию.',
        config_key='viduq3_turbo',
        is_popular=False,
    ),
    dict(
        name='Grok Imagine 1.5',
        slug='grok-imagine-1-5',
        model_name='grok-imagine-1.5-video-apimart',
        cost_per_message=30,
        order=12,
        description='Видео-модель xAI Grok — ролики до 30 секунд, необычные форматы кадра, оживление фото.',
        config_key='grok15',
        is_popular=True,
    ),
    dict(
        name='Pixverse v6',
        slug='pixverse-v6',
        model_name='pixverse-v6',
        cost_per_message=25,
        order=13,
        description='Pixverse v6 — самая доступная видео-модель: до 15 секунд, звук, 8 форматов кадра.',
        config_key='pixverse6',
        is_popular=False,
    ),

    # ── B14 (2026-07-24) — расширение каталога ──────────────────────────
    dict(
        name='Wan 2.7',
        slug='wan-2-7',
        model_name='wan2.7',
        cost_per_message=45,
        order=14,
        description='Alibaba Wan 2.7 — новое поколение: до 15 секунд со звуком, смена планов.',
        config_key='wan27',
        is_popular=False,
    ),
    dict(
        name='Seedance 2.5',
        slug='seedance-2-5',
        model_name='seedance-2.5',
        cost_per_message=50,
        order=15,
        description='Новейшая версия ByteDance Seedance — до 30 секунд, звук, до 30 референсных изображений.',
        config_key='seedance25',
        is_popular=True,
    ),
    dict(
        name='Kling 3.0 Turbo',
        slug='kling-3-0-turbo',
        model_name='kling-3.0-turbo',
        cost_per_message=65,
        order=16,
        description='Новый флагман Kuaishou — турбо-режим для более быстрой генерации в высоком качестве.',
        config_key='kling30turbo',
        is_popular=True,
    ),
    dict(
        name='Kling v3 Motion Control',
        slug='kling-v3-motion-control',
        model_name='kling-v3-motion-control',
        cost_per_message=75,
        order=17,
        description='Kling v3 с управлением траекторией камеры — для сложной операторской работы.',
        config_key='klingv3motion',
        is_popular=False,
    ),
    dict(
        name='Kling v3 Omni',
        slug='kling-v3-omni',
        model_name='kling-v3-omni',
        cost_per_message=75,
        order=18,
        description='Kling v3 в мультиреференсном режиме — согласованность персонажа и сцены между кадрами.',
        config_key='klingv3omni',
        is_popular=False,
    ),
    dict(
        name='Hailuo 2.3 Fast',
        slug='hailuo-2-3-fast',
        model_name='MiniMax-Hailuo-2.3-Fast',
        cost_per_message=25,
        order=19,
        description='Быстрый и бюджетный тир MiniMax Hailuo 2.3 — то же кинематографичное движение, дешевле.',
        config_key='hailuo23fast',
        is_popular=False,
    ),
    dict(
        name='Vidu Q3 Pro',
        slug='vidu-q3-pro',
        model_name='viduq3-pro',
        cost_per_message=45,
        order=20,
        description='Старший тир Vidu Q3 — более высокое качество, чем Turbo, до 1080p.',
        config_key='viduq3pro',
        is_popular=False,
    ),
    dict(
        name='Seedance 2.0 Fast',
        slug='seedance-2-0-fast',
        model_name='doubao-seedance-2.0-fast',
        cost_per_message=28,
        order=22,
        description='Быстрый и доступный тир Seedance 2.0 — тот же движок ByteDance, ниже цена.',
        config_key='seedance20fast',
        is_popular=False,
    ),
    dict(
        name='Veo 3.1 Lite',
        slug='veo-3-1-lite',
        model_name='veo3.1-lite',
        cost_per_message=30,
        order=23,
        description='Бюджетная версия Veo 3.1 от Google DeepMind — доступный вход в экосистему Veo.',
        config_key='veo3lite',
        is_popular=False,
    ),

    # Добавлено 2026-07-27, проверено вживую до status=completed с реальным видео.
    dict(
        name='Kling Video O1',
        slug='kling-video-o1',
        model_name='kling-video-o1',
        cost_per_message=70,
        order=24,
        description='Новое поколение Kling — флагманская модель Kuaishou для видео.',
        config_key='klingvideoo1',
        is_popular=False,
    ),
    dict(
        name='Vidu Q3',
        slug='vidu-q3',
        model_name='viduq3',
        cost_per_message=25,
        order=25,
        description='Базовый тир Vidu Q3 — объединяет несколько референсных фото в одну сцену.',
        config_key='viduq3base',
        is_popular=False,
    ),
]


class Command(BaseCommand):
    help = 'Добавляет/обновляет видео-модели apimart.ai и деактивирует устаревшие'

    def handle(self, *args, **options):
        video_cat, created = Category.objects.get_or_create(
            slug='video',
            defaults={'name': 'Видео', 'icon': 'fas fa-video', 'order': 3},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Создана категория "Видео" (id={video_cat.id})'))
        else:
            self.stdout.write(f'Категория "Видео" уже есть (id={video_cat.id})')

        self.stdout.write('\n=== Видео-модели (apimart.ai) ===')
        active_slugs = []
        for m in VIDEO_MODELS:
            config_key = m.pop('config_key')
            config = dict(VIDEO_CONFIG[config_key])
            config['name'] = m['name']
            active_slugs.append(m['slug'])

            network = NeuralNetwork.objects.filter(slug=m['slug']).first()
            if network is None:
                network = NeuralNetwork.objects.create(
                    slug=m['slug'],
                    name=m['name'],
                    category=video_cat,
                    model_name=m['model_name'],
                    cost_per_message=m['cost_per_message'],
                    order=m.get('order', 0),
                    description_ru=m.get('description', ''),
                    provider='fal-ai',
                    config_json=config,
                    is_active=True,
                    is_popular=m.get('is_popular', False),
                )
                self.stdout.write(f"  {self.style.SUCCESS('создана')}: {network.name} ({network.model_name})")
            else:
                # Обновляем конфиг и метаданные, но НЕ трогаем цену —
                # cost_per_message/cost_kopecks могли поправить в админке
                network.name = m['name']
                network.category = video_cat
                network.model_name = m['model_name']
                network.order = m.get('order', 0)
                network.description_ru = m.get('description', '')
                network.provider = 'fal-ai'
                network.config_json = config
                network.is_active = True
                network.is_popular = m.get('is_popular', False)
                network.save(update_fields=[
                    'name', 'category', 'model_name', 'order', 'description_ru',
                    'provider', 'config_json', 'is_active', 'is_popular',
                ])
                self.stdout.write(f'  обновлена: {network.name} ({network.model_name})')

        # Деактивируем видео-модели, которых нет в нашем списке
        self.stdout.write('\n=== Деактивация устаревших моделей ===')
        old_models = NeuralNetwork.objects.filter(
            category=video_cat,
            is_active=True,
        ).exclude(slug__in=active_slugs)

        count = old_models.count()
        if count:
            names = list(old_models.values_list('name', flat=True))
            old_models.update(is_active=False)
            for name in names:
                self.stdout.write(self.style.WARNING(f'  деактивирована: {name}'))
            self.stdout.write(self.style.WARNING(f'Деактивировано: {count} моделей'))
        else:
            self.stdout.write('  Устаревших моделей не найдено')

        self.stdout.write(f'\nГотово! Активных видео-моделей: {len(VIDEO_MODELS)}')
        self.stdout.write('Убедись что APIMART_API_KEY задан в .env!')
