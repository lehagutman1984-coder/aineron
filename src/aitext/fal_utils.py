import json
import os
import base64
import logging
import uuid
import time
import requests
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

_image_client = None


def get_laozhang_image_client():
    global _image_client
    if _image_client is None:
        _image_client = OpenAI(
            api_key=settings.LAOZHANG_API_KEY,
            base_url=settings.LAOZHANG_API_URL,
        )
    return _image_client


def validate_and_merge_settings(config, user_settings):
    """
    Валидирует пользовательские настройки на основе конфигурации модели.
    Возвращает (final_args, errors, extra_cost), где final_args — словарь с аргументами для API,
    errors — список ошибок валидации, extra_cost — дополнительная стоимость (целое или float).
    """
    api_defaults = config.get('api_defaults', {}).copy()
    ui_settings = config.get('ui_settings', {})
    constraints = config.get('constraints', {})

    errors = []
    final_args = {}
    extra_cost = 0

    # Сначала копируем дефолтные настройки
    final_args.update(api_defaults)

    # Функция для обновления значения с проверкой
    def set_value(name, value):
        final_args[name] = value

    # Функция для добавления extra_cost
    def add_extra_cost(field, value):
        nonlocal extra_cost
        if field.get('type') == 'checkbox' and value:
            extra_cost += float(field.get('extra_cost', 0))
        elif field.get('type') == 'select':
            for opt in field.get('options', []):
                if str(opt.get('value')) == str(value):
                    extra_cost += float(opt.get('extra_cost', 0))
                    break
        elif field.get('type') in ('slider', 'number'):
            extra_cost += float(field.get('extra_cost', 0))

    # Проходим по всем секциям и полям UI
    for section in ui_settings.get('sections', []):
        for field in section.get('fields', []):
            name = field.get('name')
            if not name:
                continue

            # Получаем значение от пользователя (если есть)
            user_value = user_settings.get(name)
            if user_value is None:
                continue

            # Обработка в зависимости от типа поля
            field_type = field.get('type')

            # 1. Slider
            if field_type == 'slider':
                try:
                    num_val = float(user_value)
                    min_val = field.get('min', constraints.get(f'min_{name}', 0))
                    max_val = field.get('max', constraints.get(f'max_{name}', 100))
                    step = field.get('step', 1)
                    if num_val < min_val or num_val > max_val:
                        errors.append(f"Поле '{field.get('label', name)}' должно быть в диапазоне от {min_val} до {max_val}")
                    else:
                        if step > 0:
                            num_val = round(num_val / step) * step
                            num_val = max(min_val, min(num_val, max_val))
                        set_value(name, num_val)
                        add_extra_cost(field, num_val)
                except ValueError:
                    errors.append(f"Поле '{field.get('label', name)}' должно быть числом")

            # 2. Select — сравниваем как строки, чтобы int 5 == "5"
            elif field_type == 'select':
                allowed = [str(opt['value']) for opt in field.get('options', [])]
                str_val = str(user_value)
                if str_val in allowed:
                    set_value(name, str_val)
                    add_extra_cost(field, str_val)
                else:
                    errors.append(f"Недопустимое значение для поля '{field.get('label', name)}'")

            # 3. Checkbox
            elif field_type == 'checkbox':
                bool_val = bool(user_value)
                set_value(name, bool_val)
                add_extra_cost(field, bool_val)

            # 4. Number (простое число)
            elif field_type == 'number':
                try:
                    num_val = float(user_value)
                    min_val = field.get('min')
                    max_val = field.get('max')
                    if min_val is not None and num_val < min_val:
                        errors.append(f"Поле '{field.get('label', name)}' не может быть меньше {min_val}")
                    elif max_val is not None and num_val > max_val:
                        errors.append(f"Поле '{field.get('label', name)}' не может быть больше {max_val}")
                    else:
                        set_value(name, num_val)
                        add_extra_cost(field, num_val)
                except ValueError:
                    errors.append(f"Поле '{field.get('label', name)}' должно быть числом")

            # 5. Text или Textarea
            elif field_type in ('text', 'textarea'):
                max_len = field.get('max_length')
                if max_len and len(user_value) > max_len:
                    errors.append(f"Поле '{field.get('label', name)}' не может быть длиннее {max_len} символов")
                else:
                    set_value(name, user_value)
                    add_extra_cost(field, user_value)

            # 6. Специальная обработка для image_size (select с кастомными размерами)
            elif name == 'image_size' and field_type == 'select':
                if user_value == 'custom':
                    custom_width = user_settings.get('custom_width')
                    custom_height = user_settings.get('custom_height')
                    if custom_width is None or custom_height is None:
                        errors.append("Для пользовательского размера необходимо указать ширину и высоту")
                    else:
                        try:
                            width = int(custom_width)
                            height = int(custom_height)
                            min_w = constraints.get('min_custom_width', 64)
                            max_w = constraints.get('max_custom_width', 4096)
                            min_h = constraints.get('min_custom_height', 64)
                            max_h = constraints.get('max_custom_height', 4096)
                            if width < min_w or width > max_w:
                                errors.append(f"Ширина должна быть от {min_w} до {max_w}")
                            if height < min_h or height > max_h:
                                errors.append(f"Высота должна быть от {min_h} до {max_h}")
                            aspect_min = constraints.get('custom_aspect_ratio_min', 0.1)
                            aspect_max = constraints.get('custom_aspect_ratio_max', 10.0)
                            aspect = width / height if height != 0 else 0
                            if aspect < aspect_min or aspect > aspect_max:
                                errors.append(f"Соотношение сторон должно быть между {aspect_min} и {aspect_max}")
                            area = width * height
                            area_min = constraints.get('custom_size_min_area', 4096)
                            area_max = constraints.get('custom_size_max_area', 16777216)
                            if area < area_min or area > area_max:
                                errors.append(f"Площадь изображения должна быть между {area_min} и {area_max}")
                            set_value('image_size', {'width': width, 'height': height})
                            add_extra_cost(field, user_value)
                        except ValueError:
                            errors.append("Ширина и высота должны быть числами")
                else:
                    set_value(name, user_value)
                    add_extra_cost(field, user_value)

            # 7. Обработка seed
            elif name == 'seed':
                if user_value is not None and str(user_value).strip():
                    try:
                        seed_int = int(user_value)
                        min_seed = constraints.get('min_seed')
                        max_seed = constraints.get('max_seed')
                        if min_seed is not None and seed_int < min_seed:
                            errors.append(f"Seed должен быть не меньше {min_seed}")
                        elif max_seed is not None and seed_int > max_seed:
                            errors.append(f"Seed должен быть не больше {max_seed}")
                        else:
                            set_value(name, seed_int)
                            add_extra_cost(field, seed_int)
                    except ValueError:
                        errors.append("Seed должен быть числом")

            # 8. Обработка negative_prompt и system_prompt (с проверкой длины)
            elif name in ('negative_prompt', 'system_prompt'):
                max_len = constraints.get(f'max_{name}_length', 2000)
                if len(user_value) > max_len:
                    errors.append(f"Поле '{field.get('label', name)}' не может быть длиннее {max_len} символов")
                else:
                    set_value(name, user_value)
                    add_extra_cost(field, user_value)

            # 9. Обработка colors (JSON массив)
            elif name == 'colors':
                if isinstance(user_value, str) and user_value.strip():
                    try:
                        colors_array = json.loads(user_value)
                        if not isinstance(colors_array, list):
                            errors.append("Colors должен быть массивом")
                        else:
                            max_colors = constraints.get('max_colors', 10)
                            if len(colors_array) > max_colors:
                                errors.append(f"Слишком много цветов. Максимум: {max_colors}")
                            for idx, color in enumerate(colors_array):
                                if not isinstance(color, dict):
                                    errors.append(f"Цвет {idx + 1} должен быть объектом")
                                else:
                                    for channel in ['r', 'g', 'b']:
                                        if channel not in color:
                                            errors.append(f"Цвет {idx + 1} не содержит канал {channel}")
                                        else:
                                            try:
                                                val = int(color[channel])
                                                if val < 0 or val > 255:
                                                    errors.append(f"Канал {channel} цвета {idx + 1} должен быть от 0 до 255")
                                            except ValueError:
                                                errors.append(f"Канал {channel} цвета {idx + 1} должен быть числом")
                            if not errors:
                                set_value(name, colors_array)
                                add_extra_cost(field, colors_array)
                    except json.JSONDecodeError:
                        errors.append("Colors должен быть валидным JSON массивом")
                elif isinstance(user_value, list):
                    max_colors = constraints.get('max_colors', 10)
                    if len(user_value) > max_colors:
                        errors.append(f"Слишком много цветов. Максимум: {max_colors}")
                    else:
                        set_value(name, user_value)
                        add_extra_cost(field, user_value)

            # 10. Специальные зависимости: num_images и max_images
            elif name == 'num_images':
                if 'max_images' in user_settings:
                    # Отложим проверку до конца
                    pass
                if 'num_images' in final_args:
                    final_args[name] = user_value
                else:
                    set_value(name, user_value)
                add_extra_cost(field, user_value)

            # 11. Для всех остальных полей просто сохраняем как есть
            else:
                set_value(name, user_value)
                add_extra_cost(field, user_value)

    # Дополнительные проверки зависимостей (без изменений)
    # 1. Проверка num_images и max_images
    if 'num_images' in final_args and 'max_images' in final_args:
        if constraints.get('max_images_gte_num_images', False):
            if final_args['max_images'] < final_args['num_images']:
                errors.append("max_images должен быть больше или равен num_images")
                del final_args['num_images']
                del final_args['max_images']

    # 2. Проверка временных отрезков для аудио
    sound_start = final_args.get('sound_start_time')
    sound_end = final_args.get('sound_end_time')
    sound_insert = final_args.get('sound_insert_time')
    if sound_start is not None and sound_end is not None:
        if sound_end <= sound_start:
            errors.append("sound_end_time должен быть больше sound_start_time")
        else:
            segment_duration = sound_end - sound_start
            min_segment = constraints.get('min_audio_segment_ms', 2000)
            if segment_duration < min_segment:
                errors.append(f"Аудио отрезок должен быть не менее {min_segment} мс ({min_segment / 1000} секунд)")

    has_cropping = (sound_start is not None or sound_end is not None)
    if has_cropping:
        if sound_start is None:
            errors.append("При указании времени обрезки аудио необходимо указать sound_start_time")
        if sound_end is None:
            errors.append("При указании времени обрезки аудио необходимо указать sound_end_time")
        if sound_insert is None:
            errors.append("При указании времени обрезки аудио необходимо указать sound_insert_time")

    # Проверка: если есть image_url и требуется input image
    metadata = config.get('metadata', {})
    if metadata.get('requires_input_images', False):
        has_image_url = final_args.get('image_url')
        has_image_urls = final_args.get('image_urls')
        if not has_image_url and not has_image_urls:
            errors.append("Эта модель требует загруженное изображение (image_url или image_urls)")

    return final_args, errors, extra_cost


def save_image_from_b64(b64_data, message, prompt):
    """Сохраняет изображение из base64 строки"""
    try:
        img_data = base64.b64decode(b64_data)
        filename = f"generated_{uuid.uuid4()}.png"
        path = f"generated_images/{filename}"
        default_storage.save(path, ContentFile(img_data))
        from .models import GeneratedImage
        gen_img = GeneratedImage.objects.create(
            message=message,
            image=path,
            prompt=prompt,
            media_type='image'
        )
        logger.info(f"Изображение из base64 сохранено: {path}")
        return gen_img
    except Exception as e:
        logger.error(f"Ошибка сохранения base64 изображения: {e}")
        return None


def save_media_from_url(url, message, prompt, media_type='image', max_retries=3, timeout=60):
    """
    Скачивает медиа по URL с повторными попытками и сохраняет в GeneratedImage.
    Поддерживает видео (mp4, webm, avi, mov, mkv) и изображения (png, jpg, jpeg, webp, gif, bmp, tiff).
    """
    for attempt in range(max_retries):
        try:
            logger.info(f"[RECV] Скачивание медиа из {url}, попытка {attempt + 1}/{max_retries}")
            response = requests.get(url, timeout=timeout, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()

            content_type = response.headers.get('content-type', '').lower()
            file_data = response.content
            logger.info(f"[OK] Медиа скачано, размер: {len(file_data)} байт, тип: {content_type}")

            # Если тип не определён или application/octet-stream, определяем по расширению URL
            if content_type == 'application/octet-stream' or not content_type:
                if url.endswith('.mp4'):
                    content_type = 'video/mp4'
                elif url.endswith('.webm'):
                    content_type = 'video/webm'
                elif url.endswith('.avi'):
                    content_type = 'video/x-msvideo'
                elif url.endswith('.mov'):
                    content_type = 'video/quicktime'
                elif url.endswith('.mkv'):
                    content_type = 'video/x-matroska'
                elif url.endswith('.png'):
                    content_type = 'image/png'
                elif url.endswith('.jpg') or url.endswith('.jpeg'):
                    content_type = 'image/jpeg'
                elif url.endswith('.webp'):
                    content_type = 'image/webp'
                elif url.endswith('.gif'):
                    content_type = 'image/gif'
                elif url.endswith('.bmp'):
                    content_type = 'image/bmp'
                elif url.endswith('.tiff') or url.endswith('.tif'):
                    content_type = 'image/tiff'

            # Определяем тип медиа и расширение
            if 'video' in content_type:
                media_type = 'video'
                ext = 'mp4'
                if 'webm' in content_type:
                    ext = 'webm'
                elif 'avi' in content_type:
                    ext = 'avi'
                elif 'quicktime' in content_type:
                    ext = 'mov'
                elif 'matroska' in content_type:
                    ext = 'mkv'
                path = f"generated_videos/generated_{uuid.uuid4()}.{ext}"
            elif 'image' in content_type:
                media_type = 'image'
                ext = 'png'
                if 'jpeg' in content_type or 'jpg' in content_type:
                    ext = 'jpg'
                elif 'webp' in content_type:
                    ext = 'webp'
                elif 'gif' in content_type:
                    ext = 'gif'
                elif 'bmp' in content_type:
                    ext = 'bmp'
                elif 'tiff' in content_type:
                    ext = 'tiff'
                path = f"generated_images/generated_{uuid.uuid4()}.{ext}"
            else:
                logger.warning(f"Неизвестный тип медиа: {content_type}")
                return None

            default_storage.save(path, ContentFile(file_data))
            from .models import GeneratedImage  # если ещё не импортирован
            gen_img = GeneratedImage.objects.create(
                message=message,
                image=path,
                prompt=prompt,
                media_type=media_type
            )
            logger.info(f"Медиа сохранено: {path} (тип: {media_type})")
            return gen_img

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.RequestException) as e:
            logger.error(f"[ERR] Ошибка скачивания (попытка {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                logger.error(f"Не удалось скачать {url} после {max_retries} попыток")
                return None
            time.sleep(3)
        except Exception as e:
            logger.error(f"[ERR] Неожиданная ошибка при скачивании {url}: {e}")
            return None

    return None


def _build_image_params(model_id, prompt, final_args):
    """Формирует параметры для client.images.generate() из config api_defaults."""
    params = {
        'model': model_id,
        'prompt': prompt,
    }

    # size: приоритет — прямой 'size', затем 'image_size', затем width+height
    if 'size' in final_args:
        params['size'] = str(final_args['size'])
    elif 'image_size' in final_args:
        size_val = final_args['image_size']
        if isinstance(size_val, dict) and 'width' in size_val and 'height' in size_val:
            params['size'] = f"{size_val['width']}x{size_val['height']}"
        elif isinstance(size_val, str):
            params['size'] = size_val
    elif 'width' in final_args and 'height' in final_args:
        params['size'] = f"{int(final_args['width'])}x{int(final_args['height'])}"

    # Стандартные параметры images API
    if 'quality' in final_args:
        params['quality'] = final_args['quality']
    if 'style' in final_args:
        params['style'] = final_args['style']
    if 'n' in final_args:
        params['n'] = int(final_args['n'])
    else:
        params['n'] = 1

    return params


def _size_to_resolution_and_ratio(size_str):
    """Из '1280x720' возвращает ('720p', '16:9')"""
    try:
        w, h = (int(x) for x in str(size_str).lower().split('x'))
    except Exception:
        return '720p', '16:9'
    if max(w, h) >= 3000:
        res = '4k'
    elif max(w, h) >= 1900:
        res = '1080p'
    else:
        res = '720p'
    ratio_map = {(16, 9): '16:9', (9, 16): '9:16', (1, 1): '1:1', (4, 3): '4:3', (3, 4): '3:4'}
    from math import gcd
    g = gcd(w, h)
    ratio = ratio_map.get((w // g, h // g), '16:9' if w > h else ('9:16' if h > w else '1:1'))
    return res, ratio


def _save_video_binary(content, message, prompt):
    """Сохраняет бинарные данные как mp4, возвращает GeneratedImage."""
    path = f"generated_videos/generated_{uuid.uuid4()}.mp4"
    default_storage.save(path, ContentFile(content))
    from .models import GeneratedImage
    return GeneratedImage.objects.create(message=message, image=path, prompt=prompt, media_type='video')


def generate_video_laozhang(network, user_msg, message, user_settings=None):
    """
    Генерирует видео через laozhang.ai.
    Правильный эндпоинт: POST /v1/videos (multipart/form-data).
    Статус: GET /v1/videos/{id}
    Скачать: GET /v1/videos/{id}/content
    """
    config = network.config_json or {}
    model_id = network.model_name
    prompt = user_msg.content if user_msg else ""
    base_cost = network.cost_per_message

    if user_settings:
        final_args, errors, extra_cost = validate_and_merge_settings(config, user_settings)
        if errors:
            raise Exception("Ошибки в настройках: " + "; ".join(errors))
    else:
        final_args = config.get('api_defaults', {}).copy()
        extra_cost = 0

    total_cost = base_cost + extra_cost

    base_url = settings.LAOZHANG_API_URL.rstrip('/')  # https://api.laozhang.ai/v1
    auth_headers = {"Authorization": f"Bearer {settings.LAOZHANG_API_KEY}"}

    size = str(final_args.get('size', '1280x720'))
    seconds = str(final_args.get('seconds', '8'))
    resolution, aspect_ratio = _size_to_resolution_and_ratio(size)

    # multipart/form-data — requests задаёт Content-Type автоматически через files=
    fields = {
        "model": model_id,
        "prompt": prompt,
        "seconds": seconds,
        "duration": seconds,
        "size": size,
        "resolution": resolution,
        "aspectRatio": aspect_ratio,
    }
    if final_args.get('negativePrompt'):
        fields['negativePrompt'] = str(final_args['negativePrompt'])

    logger.info(f"Video POST /v1/videos model={model_id} size={size} seconds={seconds}")
    resp = requests.post(
        f"{base_url}/videos",
        headers=auth_headers,
        files={k: (None, v) for k, v in fields.items()},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    logger.info(f"Video creation response: {str(data)[:400]}")

    saved_media_direct = []
    video_urls = []

    # Синхронный ответ
    for item in (data.get('data') or []):
        url = item.get('url') or item.get('video_url')
        if url and str(url).startswith('http'):
            video_urls.append(url)

    # Асинхронный polling
    if not video_urls:
        job_id = data.get('id') or data.get('task_id')
        if job_id:
            logger.info(f"Video async job_id={job_id}, polling /v1/videos/{job_id}")
            for attempt in range(60):  # до 15 мин (15 сек × 60)
                time.sleep(15)
                poll = requests.get(f"{base_url}/videos/{job_id}", headers=auth_headers, timeout=30)
                poll.raise_for_status()
                pd = poll.json()
                status = (pd.get('status') or '').lower()
                logger.info(f"Video poll {attempt + 1}/60: status={status} progress={pd.get('progress', '?')}")

                if status == 'completed':
                    logger.info(f"Video completed response: {str(pd)[:600]}")
                    # Скачиваем бинарный MP4 через /v1/videos/{id}/content
                    content_url = f"{base_url}/videos/{job_id}/content"
                    logger.info(f"Downloading video: GET {content_url}")
                    try:
                        cr = requests.get(content_url, headers=auth_headers, timeout=180, allow_redirects=True)
                        cr.raise_for_status()
                        ct = cr.headers.get('content-type', '')
                        logger.info(f"Download: status={cr.status_code} content-type={ct} size={len(cr.content)}")
                        if 'video' in ct or str(cr.url).endswith('.mp4') or len(cr.content) > 100_000:
                            gen = _save_video_binary(cr.content, message, prompt)
                            saved_media_direct.append(gen)
                        elif 'json' in ct:
                            dj = cr.json()
                            logger.info(f"Download JSON: {str(dj)[:400]}")
                            for k in ('url', 'video_url', 'download_url', 'src'):
                                u = dj.get(k)
                                if u and str(u).startswith('http'):
                                    video_urls.append(u)
                                    break
                        else:
                            logger.warning(f"Unexpected content-type: {ct}, bytes: {cr.content[:200]}")
                    except Exception as ce:
                        logger.error(f"Video download failed: {ce}")
                    break
                elif status in ('failed', 'error', 'cancelled'):
                    raise Exception(f"Видео завершилось ошибкой: {pd.get('error', status)}")

    model_name = config.get('name', network.name)
    saved_media = list(saved_media_direct)
    for url in video_urls:
        gen = save_media_from_url(url, message, prompt, media_type='video')
        if gen:
            saved_media.append(gen)

    if saved_media:
        text_parts = [f"Сгенерировано {len(saved_media)} видео моделью \"{model_name}\"."]
        for m in saved_media:
            text_parts.append(
                f"<video src='{m.image.url}' controls width='100%' style='max-width:100%; border-radius:12px;'></video>"
            )
        final_text = "\n\n".join(text_parts)
    else:
        final_text = f"Модель \"{model_name}\" не вернула видео. Попробуйте изменить промт."

    return final_text, saved_media, total_cost


def generate_seedance_video(network, user_msg, message, user_settings=None):
    """
    Генерирует видео через Seedance API (ByteDance).
    Эндпоинт: https://api.laozhang.ai/seedance/api/v3/
    Скачать: GET /v1/videos/{id}/content
    """
    config = network.config_json or {}
    model_id = network.model_name
    prompt = user_msg.content if user_msg else ""
    base_cost = network.cost_per_message

    if user_settings:
        final_args, errors, extra_cost = validate_and_merge_settings(config, user_settings)
        if errors:
            raise Exception("Ошибки в настройках: " + "; ".join(errors))
    else:
        final_args = config.get('api_defaults', {}).copy()
        extra_cost = 0

    total_cost = base_cost + extra_cost

    seedance_base = "https://api.laozhang.ai/seedance/api/v3"
    # Seedance требует отдельный токен группы SeeDance2 (SEEDANCE_API_KEY в .env)
    seedance_key = getattr(settings, 'SEEDANCE_API_KEY', '') or settings.LAOZHANG_API_KEY
    auth_headers = {
        "Authorization": f"Bearer {seedance_key}",
        "Content-Type": "application/json",
    }

    body = {
        "model": model_id,
        "content": [{"type": "text", "text": prompt}],
        "ratio": str(final_args.get('ratio', '16:9')),
        "duration": int(final_args.get('duration', 5)),
        "resolution": str(final_args.get('resolution', '720p')),
    }

    logger.info(f"Seedance POST {seedance_base}/contents/generations/tasks model={model_id}")
    resp = requests.post(
        f"{seedance_base}/contents/generations/tasks",
        headers=auth_headers,
        json=body,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    logger.info(f"Seedance creation response: {str(data)[:400]}")

    job_id = data.get('id')
    if not job_id:
        raise Exception(f"Нет task id в ответе Seedance: {str(data)[:200]}")

    saved_media_direct = []
    video_urls = []

    logger.info(f"Seedance polling tasks/{job_id}")
    for attempt in range(60):
        time.sleep(15)
        poll = requests.get(
            f"{seedance_base}/contents/generations/tasks/{job_id}",
            headers=auth_headers,
            timeout=30,
        )
        poll.raise_for_status()
        pd = poll.json()
        status = (pd.get('status') or '').lower()
        logger.info(f"Seedance poll {attempt + 1}/60: status={status}")

        if status == 'succeeded':
            logger.info(f"Seedance completed: {str(pd)[:600]}")
            # URL в content.video_url
            content_obj = pd.get('content') or {}
            video_url = content_obj.get('video_url') if isinstance(content_obj, dict) else None
            if video_url and str(video_url).startswith('http'):
                logger.info(f"Seedance video_url: {video_url[:100]}")
                video_urls.append(video_url)
            else:
                # Запасной вариант — /v1/videos/{id}/content
                dl_url = f"{settings.LAOZHANG_API_URL.rstrip('/')}/videos/{job_id}/content"
                logger.info(f"Seedance fallback download: GET {dl_url}")
                try:
                    cr = requests.get(
                        dl_url,
                        headers={"Authorization": f"Bearer {seedance_key}"},
                        timeout=180,
                        allow_redirects=True,
                    )
                    cr.raise_for_status()
                    ct = cr.headers.get('content-type', '')
                    if 'video' in ct or len(cr.content) > 100_000:
                        gen = _save_video_binary(cr.content, message, prompt)
                        saved_media_direct.append(gen)
                    else:
                        logger.warning(f"Seedance fallback unexpected: {ct} size={len(cr.content)}")
                except Exception as ce:
                    logger.error(f"Seedance fallback download failed: {ce}")
            break
        elif status in ('failed', 'error', 'expired'):
            raise Exception(f"Seedance генерация завершилась ошибкой: {pd.get('error', status)}")

    model_name = config.get('name', network.name)
    saved_media = list(saved_media_direct)
    for url in video_urls:
        gen = save_media_from_url(url, message, prompt, media_type='video')
        if gen:
            saved_media.append(gen)

    if saved_media:
        text_parts = [f"Сгенерировано {len(saved_media)} видео моделью \"{model_name}\"."]
        for m in saved_media:
            text_parts.append(
                f"<video src='{m.image.url}' controls width='100%' style='max-width:100%; border-radius:12px;'></video>"
            )
        final_text = "\n\n".join(text_parts)
    else:
        final_text = f"Модель \"{model_name}\" не вернула видео. Попробуйте изменить промт."

    return final_text, saved_media, total_cost


def generate_video_apimart(network, user_msg, message, user_settings=None):
    """
    Генерирует видео через apimart.ai.
    POST /v1/videos/generations → task_id
    GET  /v1/tasks/{task_id}    → status → result.videos[].url
    """
    config = network.config_json or {}
    model_id = network.model_name
    prompt = user_msg.content if user_msg else ""
    base_cost = network.cost_per_message

    if user_settings:
        final_args, errors, extra_cost = validate_and_merge_settings(config, user_settings)
        if errors:
            raise Exception("Ошибки в настройках: " + "; ".join(errors))
    else:
        final_args = config.get('api_defaults', {}).copy()
        extra_cost = 0

    total_cost = base_cost + extra_cost

    api_key = getattr(settings, 'APIMART_API_KEY', '')
    base_url = getattr(settings, 'APIMART_API_URL', 'https://api.apimart.ai/v1').rstrip('/')
    auth_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    body = {"model": model_id, "prompt": prompt}
    for param in ['duration', 'aspect_ratio', 'resolution', 'audio', 'mode',
                  'negative_prompt', 'generation_type', 'enable_gif', 'official_fallback']:
        if param in final_args and final_args[param] is not None:
            body[param] = final_args[param]

    # duration должен быть integer (apimart ожидает число, select возвращает строку)
    if 'duration' in body:
        try:
            body['duration'] = int(body['duration'])
        except (ValueError, TypeError):
            pass

    # Kling: аудио работает только в pro mode — принудительно переключаем
    if body.get('audio'):
        body['mode'] = 'pro'

    logger.info(f"APIMart Video POST model={model_id} params={body}")
    resp = requests.post(
        f"{base_url}/videos/generations",
        headers=auth_headers,
        json=body,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    logger.info(f"APIMart creation response: {str(data)[:400]}")

    # data.data — список [{status, task_id}]
    task_id = None
    items = data.get('data') or []
    if isinstance(items, list):
        for item in items:
            task_id = item.get('task_id')
            if task_id:
                break
    elif isinstance(items, dict):
        task_id = items.get('task_id')

    if not task_id:
        raise Exception(f"Нет task_id в ответе APIMart: {str(data)[:200]}")

    logger.info(f"APIMart task_id={task_id}, polling...")
    video_urls = []

    for attempt in range(60):
        time.sleep(15)
        poll_resp = requests.get(
            f"{base_url}/tasks/{task_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        poll_resp.raise_for_status()
        pd = poll_resp.json()

        # Поддержка как top-level, так и вложенного в data
        status_obj = pd['data'] if isinstance(pd.get('data'), dict) else pd
        status = (status_obj.get('status') or '').lower()
        progress = status_obj.get('progress', '?')
        logger.info(f"APIMart poll {attempt + 1}/60: status={status} progress={progress}")

        if status == 'completed':
            result = status_obj.get('result') or {}
            videos = result.get('videos', [])
            for v in videos:
                url = v.get('url')
                if isinstance(url, list):
                    url = url[0] if url else None
                if url and str(url).startswith('http'):
                    video_urls.append(url)
            if not video_urls:
                logger.warning(f"APIMart completed но нет видео URL. result={str(result)[:400]}")
            break
        elif status in ('failed', 'error', 'cancelled'):
            raise Exception(f"APIMart генерация завершилась ошибкой: {status_obj.get('message', status)}")

    model_name = config.get('name', network.name)
    saved_media = []
    for url in video_urls:
        gen = save_media_from_url(url, message, prompt, media_type='video')
        if gen:
            saved_media.append(gen)

    if saved_media:
        text_parts = [f"Сгенерировано {len(saved_media)} видео моделью \"{model_name}\"."]
        for m in saved_media:
            text_parts.append(
                f"<video src='{m.image.url}' controls width='100%' style='max-width:100%; border-radius:12px;'></video>"
            )
        return "\n\n".join(text_parts), saved_media, total_cost

    return f"Модель \"{model_name}\" не вернула видео. Попробуйте изменить промт.", [], total_cost


def generate_with_falai(network, user_msg, message, user_settings=None):
    """
    Генерирует изображения/видео через laozhang.ai.
    Имя функции сохранено для совместимости с tasks.py.
    Возвращает (final_text, saved_media, total_cost)
    """
    config = network.config_json
    if not config:
        raise Exception("Отсутствует конфигурация для модели")

    # Видео-модели — роутинг по video_api
    if config.get('metadata', {}).get('output_type') == 'video':
        video_api = config.get('metadata', {}).get('video_api', '')
        if video_api == 'apimart':
            return generate_video_apimart(network, user_msg, message, user_settings)
        if video_api == 'seedance':
            return generate_seedance_video(network, user_msg, message, user_settings)
        return generate_video_laozhang(network, user_msg, message, user_settings)

    model_id = network.model_name
    if not model_id:
        raise Exception("Не указан model_name для модели изображений")

    base_cost = network.cost_per_message

    # Валидируем и сливаем настройки
    if user_settings:
        final_args, errors, extra_cost = validate_and_merge_settings(config, user_settings)
        if errors:
            raise Exception("Ошибки в настройках: " + "; ".join(errors))
    else:
        final_args = config.get('api_defaults', {}).copy()
        extra_cost = 0

    total_cost = base_cost + extra_cost

    prompt = user_msg.content if user_msg else ""

    image_params = _build_image_params(model_id, prompt, final_args)

    logger.info(f"Запуск laozhang.ai images API: model={model_id}, params={image_params}")
    client = get_laozhang_image_client()

    try:
        response = client.images.generate(**image_params)
    except Exception as e:
        logger.error(f"Ошибка вызова laozhang.ai images API: {e}")
        raise

    # Обрабатываем результат
    saved_media = []
    for img_data in response.data:
        gen_img = None
        if img_data.url:
            gen_img = save_media_from_url(img_data.url, message, prompt)
        elif img_data.b64_json:
            gen_img = save_image_from_b64(img_data.b64_json, message, prompt)
        if gen_img:
            saved_media.append(gen_img)

    # Формируем текст ответа
    model_name = config.get('name', network.name)
    media_count = len(saved_media)
    is_video_output = config.get('metadata', {}).get('output_type') == 'video'
    if media_count > 0:
        media_word = 'видео' if is_video_output else 'изображений'
        text_parts = [f"Сгенерировано {media_count} {media_word} моделью \"{model_name}\"."]
        for media in saved_media:
            if media.media_type == 'video':
                text_parts.append(
                    f"<video src='{media.image.url}' controls width='100%' style='max-width:100%; border-radius:12px;'></video>"
                )
            else:
                text_parts.append(
                    f"<img src='{media.image.url}' alt='Сгенерированное изображение' style='max-width:100%; border-radius:12px;'>"
                )
        final_text = "\n\n".join(text_parts)
    else:
        media_word = 'видео' if is_video_output else 'изображений'
        final_text = f"Модель \"{model_name}\" обработала запрос: \"{prompt[:100]}\". (Нет {media_word} в ответе)"

    return final_text, saved_media, total_cost
