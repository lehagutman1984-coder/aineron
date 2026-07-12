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
    """
    Клиент для генерации изображений. Возвращает FallbackClient: основной сервис —
    laozhang, при его недоступности прозрачно переключается на apimart.
    Управляется флагом settings.AI_PROVIDER_FALLBACK.
    """
    global _image_client
    if _image_client is None:
        from aitext.providers import FallbackClient
        _image_client = FallbackClient('laozhang')
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


def _apply_watermark(image_bytes: bytes, text: str = None) -> bytes:
    """Накладывает водяной знак в правый нижний угол (для бесплатных тарифов)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        from urllib.parse import urlparse
        import io
        if text is None:
            site_url = getattr(settings, 'SITE_URL', 'https://aineron.ru')
            text = urlparse(site_url).netloc or 'aineron.ru'
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font_size = max(14, min(img.width, img.height) // 28)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
        padding = max(10, font_size // 2)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x, y = img.width - tw - padding, img.height - th - padding
        draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 140))
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 180))
        watermarked = Image.alpha_composite(img, overlay)
        out = io.BytesIO()
        watermarked.convert("RGB").save(out, format="PNG")
        return out.getvalue()
    except Exception as e:
        logger.warning(f"[watermark] Ошибка наложения: {e}")
        return image_bytes


def _is_free_user(message) -> bool:
    """True если сообщение принадлежит пользователю на бесплатном тарифе."""
    try:
        if message and getattr(message, 'chat_id', None):
            tariff = message.chat.user.tariff
            return tariff is not None and getattr(tariff, 'is_free', False)
    except Exception:
        pass
    return False


def save_image_from_b64(b64_data, message, prompt):
    """Сохраняет изображение из base64 строки"""
    try:
        img_data = base64.b64decode(b64_data)
        if _is_free_user(message):
            img_data = _apply_watermark(img_data)
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


def save_media_from_url(url, message, prompt, media_type='image', max_retries=3, timeout=60, gen=None):
    """
    Скачивает медиа по URL с повторными попытками и сохраняет в GeneratedImage.
    Поддерживает видео (mp4, webm, avi, mov, mkv) и изображения (png, jpg, jpeg, webp, gif, bmp, tiff).

    Если передан ``gen`` — дозаполняет существующую placeholder-строку (для img2video
    и трекинга прогресса) вместо создания новой.
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

            if media_type == 'image' and _is_free_user(message):
                file_data = _apply_watermark(file_data)
            default_storage.save(path, ContentFile(file_data))
            from .models import GeneratedImage  # если ещё не импортирован
            if gen is not None:
                # Дозаполняем placeholder-строку (img2video / progress-трекинг)
                gen.image = path
                gen.media_type = media_type
                gen.save(update_fields=['image', 'media_type'])
                gen_img = gen
            else:
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
    """Формирует параметры для client.images.generate() из config api_defaults.

    Если final_args содержит '_minimal_params': True — отправляем только model+prompt
    (нужно для моделей вроде Seedream, которые не принимают size/n).
    """
    params = {
        'model': model_id,
        'prompt': prompt,
    }

    if final_args.get('_minimal_params'):
        # Только model + prompt, никаких стандартных параметров
        return params

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
    # num_images — UI-алиас для 'n' (имеет приоритет над api_defaults 'n')
    if 'num_images' in final_args and final_args['num_images'] is not None:
        try:
            params['n'] = int(final_args['num_images'])
        except (ValueError, TypeError):
            params['n'] = int(final_args.get('n', 1))
    elif 'n' in final_args:
        params['n'] = int(final_args['n'])
    else:
        params['n'] = 1

    # Доп. параметры генерации (seed / negative_prompt) НЕ являются стандартными
    # kwargs у client.images.generate() в openai>=1.x — top-level вызов поднял бы
    # TypeError. Передаём их через extra_body: openai-SDK сливает его в JSON-тело
    # запроса, а laozhang-прокси форвардит в провайдера (Flux). Та же конвенция
    # «provider-shape», что и в video-путях S2/S3.
    extra_body = {}
    if 'seed' in final_args and final_args['seed'] is not None:
        try:
            extra_body['seed'] = int(final_args['seed'])
        except (ValueError, TypeError):
            pass
    if 'negative_prompt' in final_args and final_args['negative_prompt']:
        extra_body['negative_prompt'] = final_args['negative_prompt']
    # Sprint 6: референс стиля для генерации с нуля (без исходника)
    style_ref = final_args.get('style_image_url')
    if style_ref:
        extra_body['style_image_url'] = style_ref
        extra_body['style_reference'] = style_ref
    if extra_body:
        params['extra_body'] = extra_body

    if 'image_url' in final_args and final_args['image_url']:
        params['image'] = final_args['image_url']  # for edit flow (latent: routed away ранее)

    return params


# Поддерживаемые размеры для моделей с фиксированными size-значениями.
# Произвольные размеры (flux, etc.) — не в словаре, принимаются как есть.
_MODEL_SUPPORTED_SIZES = {
    'gpt-image-1':      [(1024, 1024), (1536, 1024), (1024, 1536)],
    'gpt-image-1-mini': [(1024, 1024), (1536, 1024), (1024, 1536)],
    'gpt-image-1.5':    [(1024, 1024), (1536, 1024), (1024, 1536)],
    'gpt-image-2':      [(1024, 1024), (1536, 1024), (1024, 1536)],
    'dall-e-3':         [(1024, 1024), (1792, 1024), (1024, 1792)],
    'dall-e-2':         [(256, 256),   (512, 512),   (1024, 1024)],
}


def _snap_size_to_supported(model_id, width, height):
    """Возвращает (w, h) ближайшего поддерживаемого размера по aspect ratio.
    Если модель не в списке — возвращает оригинальный размер без изменений.
    """
    sizes = _MODEL_SUPPORTED_SIZES.get(model_id)
    if not sizes:
        return width, height
    target_ratio = width / max(1, height)
    best_w, best_h = sizes[0]
    best_diff = float('inf')
    for sw, sh in sizes:
        diff = abs(sw / sh - target_ratio)
        if diff < best_diff:
            best_diff = diff
            best_w, best_h = sw, sh
    return best_w, best_h


def _prepare_outpaint_canvas(image_bytes, direction, expand_ratio=0.25):
    """Строит расширенный холст для outpaint через PIL (Pillow).

    direction: 'left' | 'right' | 'up' | 'down' | 'all'.
    expand_ratio: доля расширения относительно исходного размера (0.25 = +25%).

    Возвращает (expanded_png_bytes, mask_png_bytes), где:
      * expanded — RGBA PNG: оригинал вставлен на прозрачный (alpha=0) фон,
        новая область прозрачна — это запасной alpha-mask для провайдеров,
        читающих прозрачность как зону дорисовки.
      * mask — L (grayscale) PNG: БЕЛЫЙ (255) в новой области (которую модель
        должна дорисовать), ЧЁРНЫЙ (0) поверх исходного изображения.

    Конвенция «белое = область редактирования» совпадает с MaskEditor на фронте.
    """
    from PIL import Image
    import io as _io

    src = Image.open(_io.BytesIO(image_bytes)).convert("RGBA")
    w, h = src.size
    ratio = max(0.0, float(expand_ratio))
    dx = max(1, int(round(w * ratio)))
    dy = max(1, int(round(h * ratio)))

    if direction == 'left':
        new_w, new_h, paste_x, paste_y = w + dx, h, dx, 0
    elif direction == 'right':
        new_w, new_h, paste_x, paste_y = w + dx, h, 0, 0
    elif direction == 'up':
        new_w, new_h, paste_x, paste_y = w, h + dy, 0, dy
    elif direction == 'down':
        new_w, new_h, paste_x, paste_y = w, h + dy, 0, 0
    else:  # 'all'
        new_w, new_h, paste_x, paste_y = w + 2 * dx, h + 2 * dy, dx, dy

    # Расширенное изображение: прозрачный холст + оригинал
    expanded = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
    expanded.paste(src, (paste_x, paste_y))

    # Маска: белая везде (новая область), чёрная — там, где оригинал
    mask = Image.new("L", (new_w, new_h), 255)
    mask.paste(Image.new("L", (w, h), 0), (paste_x, paste_y))

    out_img = _io.BytesIO()
    expanded.save(out_img, format="PNG")
    out_mask = _io.BytesIO()
    mask.save(out_mask, format="PNG")
    return out_img.getvalue(), out_mask.getvalue()


def _prepare_expand_to_ratio(image_bytes, target_ratio_str):
    """Расширяет холст до целевого соотношения сторон (16:9, 4:3, 1:1, 3:4, 9:16, 21:9).

    Оригинал размещается по центру расширенного холста.
    Возвращает (expanded_png_bytes, mask_png_bytes) — тот же формат что _prepare_outpaint_canvas.
    """
    from PIL import Image
    import io as _io

    rw, rh = (int(x) for x in target_ratio_str.split(':'))
    target_wh = rw / rh

    src = Image.open(_io.BytesIO(image_bytes)).convert('RGBA')
    sw, sh = src.size
    current_wh = sw / sh

    if abs(current_wh - target_wh) < 0.01:
        mask = Image.new('L', (sw, sh), 0)  # nothing to paint
        buf_i = _io.BytesIO(); src.save(buf_i, format='PNG')
        buf_m = _io.BytesIO(); mask.save(buf_m, format='PNG')
        return buf_i.getvalue(), buf_m.getvalue()

    if current_wh < target_wh:
        new_w = max(sw + 1, int(round(sh * target_wh)))
        new_h = sh
    else:
        new_w = sw
        new_h = max(sh + 1, int(round(sw / target_wh)))

    paste_x = (new_w - sw) // 2
    paste_y = (new_h - sh) // 2

    expanded = Image.new('RGBA', (new_w, new_h), (0, 0, 0, 0))
    expanded.paste(src, (paste_x, paste_y))

    mask = Image.new('L', (new_w, new_h), 255)
    mask.paste(Image.new('L', (sw, sh), 0), (paste_x, paste_y))

    out_img = _io.BytesIO(); expanded.save(out_img, format='PNG')
    out_mask = _io.BytesIO(); mask.save(out_mask, format='PNG')
    return out_img.getvalue(), out_mask.getvalue()


# Flux 2 (generation-only) не сохраняет лицо/личность при редактировании — проверено
# эмпирически 2026-07-12: images.edit() формально успешен (настоящий ответ BFL, без
# исключения и без фолбэка на generate), но результат — другой человек. Flux Kontext —
# отдельная линейка BFL специально для identity-preserving правок, при том же промте
# на том же фото лицо сохраняется корректно. Поэтому реальный вызов редиректим на
# Kontext-аналог, а пользователю в ответе сообщаем о замене.
_FLUX_EDIT_REDIRECT = {
    'flux-2-pro': 'flux-kontext-pro',
    'flux-2-max': 'flux-kontext-max',
    'flux-2-flex': 'flux-kontext-pro',
}
_FLUX_EDIT_REDIRECT_NOTE = (
    "Для сохранения лица на исходном фото использована модель Flux Kontext "
    "(эта версия Flux точнее редактирует существующие фотографии)."
)


def generate_image_edit(network, user_msg, message, user_settings=None):
    """Img2img: редактирование изображения через laozhang /images/edits (multipart)
    с фолбэком на /images/generations + image_url в теле.
    Возвращает (final_text, saved_media, total_cost)."""
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

    image_url = final_args.get('image_url') or (user_settings or {}).get('image_url', '')
    if not image_url:
        raise Exception("image_url обязателен для редактирования изображения")

    # mask_url / outpaint_direction читаем напрямую из user_settings —
    # их нет в ui_settings.sections, поэтому validate_and_merge_settings их не выдаёт
    mask_url = final_args.get('mask_url') or (user_settings or {}).get('mask_url', '')
    outpaint_direction = (
        final_args.get('outpaint_direction') or (user_settings or {}).get('outpaint_direction', '')
    )
    target_ratio = (user_settings or {}).get('target_ratio', '')
    # Sprint 6: style/character reference — референс стиля, проброс провайдеру.
    # Точное имя параметра провайдер-зависимо, поэтому шлём через extra_body
    # под несколькими распространёнными ключами.
    style_image_url = (
        final_args.get('style_image_url') or (user_settings or {}).get('style_image_url', '')
    )

    client = get_laozhang_image_client()

    # Скачиваем исходное изображение для multipart /images/edits
    import io as _io
    import requests as _req

    def _make_absolute(url: str) -> str:
        """Конвертирует относительный URL (/media/...) в абсолютный."""
        if url and url.startswith('/'):
            _site = (getattr(settings, 'SITE_URL', '') or 'https://aineron.ru').rstrip('/')
            return _site + url
        return url

    image_url = _make_absolute(image_url)

    try:
        resp = _req.get(image_url, timeout=30)
        resp.raise_for_status()
        img_bytes = resp.content
        img_file = _io.BytesIO(img_bytes)
        img_file.name = 'source.png'
    except Exception as e:
        raise Exception(f"Не удалось скачать исходное изображение: {e}")

    # Маска: outpaint > target_ratio > ручная маска — взаимоисключающие режимы.
    # target_ratio строит расширенный холст аналогично outpaint, но по целевому соотношению.
    mask_file = None
    size_override = None
    if target_ratio and not outpaint_direction:
        try:
            from PIL import Image as _PILImage
            exp_bytes, mask_bytes = _prepare_expand_to_ratio(img_bytes, target_ratio)
            ew, eh = _PILImage.open(_io.BytesIO(exp_bytes)).size
            sw, sh = _snap_size_to_supported(model_id, ew, eh)
            if (sw, sh) != (ew, eh):
                exp_img = _PILImage.open(_io.BytesIO(exp_bytes)).resize((sw, sh), _PILImage.LANCZOS)
                buf = _io.BytesIO(); exp_img.save(buf, format='PNG')
                exp_bytes = buf.getvalue()
            img_file = _io.BytesIO(exp_bytes)
            img_file.name = 'source.png'
            if model_id not in _MODEL_SUPPORTED_SIZES:
                if (sw, sh) != (ew, eh):
                    mask_img = _PILImage.open(_io.BytesIO(mask_bytes)).resize((sw, sh), _PILImage.NEAREST)
                    buf_m = _io.BytesIO(); mask_img.save(buf_m, format='PNG')
                    mask_bytes = buf_m.getvalue()
                mask_file = _io.BytesIO(mask_bytes)
                mask_file.name = 'mask.png'
            size_override = f'{sw}x{sh}'
            logger.info(f'[expand-to-ratio] target={target_ratio} canvas={ew}x{eh} → {size_override}')
        except Exception as e:
            logger.warning(f'[expand-to-ratio] failed ({e}); продолжаем без расширения')
    if outpaint_direction:
        try:
            from PIL import Image as _PILImage
            exp_bytes, mask_bytes = _prepare_outpaint_canvas(img_bytes, outpaint_direction)
            ew, eh = _PILImage.open(_io.BytesIO(exp_bytes)).size
            # Приводим к поддерживаемому размеру (GPT Image 1, dall-e-3 и т.д.
            # не принимают произвольные размеры вроде 1024×1280)
            sw, sh = _snap_size_to_supported(model_id, ew, eh)
            if (sw, sh) != (ew, eh):
                exp_img = _PILImage.open(_io.BytesIO(exp_bytes)).resize((sw, sh), _PILImage.LANCZOS)
                buf = _io.BytesIO()
                exp_img.save(buf, format="PNG")
                exp_bytes = buf.getvalue()
            img_file = _io.BytesIO(exp_bytes)
            img_file.name = 'source.png'
            # OpenAI (GPT Image 1, dall-e-*) используют alpha-канал RGBA-изображения
            # как маску (alpha=0 = рисовать здесь). Отдельная маска не нужна —
            # и именно её нестандартный размер вызывал 400 "mask size does not match".
            # Для Flux и др. (не в словаре фиксированных размеров) — отправляем маску явно.
            if model_id not in _MODEL_SUPPORTED_SIZES:
                if (sw, sh) != (ew, eh):
                    mask_img = _PILImage.open(_io.BytesIO(mask_bytes)).resize((sw, sh), _PILImage.NEAREST)
                    buf_m = _io.BytesIO()
                    mask_img.save(buf_m, format="PNG")
                    mask_bytes = buf_m.getvalue()
                mask_file = _io.BytesIO(mask_bytes)
                mask_file.name = 'mask.png'
            # else: mask_file остаётся None — API читает alpha-канал img_file
            size_override = f"{sw}x{sh}"
            mask_mode = 'alpha-channel' if model_id in _MODEL_SUPPORTED_SIZES else 'explicit-mask'
            logger.info(f"[outpaint] direction={outpaint_direction} canvas={ew}x{eh} → size={size_override} mask={mask_mode}")
        except Exception as e:
            logger.warning(f"[outpaint] canvas build failed ({e}); продолжаем без outpaint")
    elif mask_url:
        try:
            from PIL import Image as _PILImage
            mresp = _req.get(_make_absolute(mask_url), timeout=30)
            mresp.raise_for_status()
            if model_id in _MODEL_SUPPORTED_SIZES:
                # OpenAI-семейство: зеркалим подход outpaint (commit 12bf4e6).
                # Пробиваем alpha=0 прямо в RGBA-исходнике там, где белые пиксели маски.
                # Отдельный mask-файл НЕ нужен — API читает alpha-канал изображения.
                src_img = _PILImage.open(_io.BytesIO(img_bytes)).convert("RGBA")
                mask_img = _PILImage.open(_io.BytesIO(mresp.content)).convert("L")
                if mask_img.size != src_img.size:
                    mask_img = mask_img.resize(src_img.size, _PILImage.NEAREST)
                sw, sh = _snap_size_to_supported(model_id, src_img.width, src_img.height)
                if (sw, sh) != src_img.size:
                    src_img = src_img.resize((sw, sh), _PILImage.LANCZOS)
                    mask_img = mask_img.resize((sw, sh), _PILImage.NEAREST)
                # MaskEditor: белый (>128) = рисовать → alpha=0; чёрный = сохранить → alpha=255
                new_alpha = mask_img.point(lambda x: 0 if x > 128 else 255)
                src_img.putalpha(new_alpha)
                buf = _io.BytesIO()
                src_img.save(buf, format="PNG")
                img_file = _io.BytesIO(buf.getvalue())
                img_file.name = 'source.png'
                size_override = f"{sw}x{sh}"
                # mask_file остаётся None
                logger.info(f"[inpaint] model={model_id} alpha-channel approach size={size_override}")
            else:
                # Flux и др.: отправляем маску явно (провайдер понимает grayscale)
                mask_file = _io.BytesIO(mresp.content)
                mask_file.name = 'mask.png'
                logger.info(f"[inpaint] model={model_id} explicit mask sent")
        except Exception as e:
            logger.warning(f"[mask] download failed ({e}); продолжаем без маски")

    # Для outpaint размер задаётся расширенным холстом, иначе берём из настроек
    size_val = size_override or final_args.get('size') or final_args.get('image_size', '1024x1024')
    if isinstance(size_val, dict):
        size_val = f"{size_val.get('width', 1024)}x{size_val.get('height', 1024)}"

    effective_model_id = _FLUX_EDIT_REDIRECT.get(model_id, model_id)
    if effective_model_id != model_id:
        logger.info(f"[img2img] {model_id} не сохраняет лицо при редактировании — используем {effective_model_id}")

    params = {'model': effective_model_id, 'prompt': prompt, 'n': 1, 'size': str(size_val)}
    # Нестандартные параметры (seed, negative_prompt, style refs) НЕ принимаются
    # openai SDK как прямые kwargs — поднимают TypeError. Передаём через extra_body,
    # который SDK сливает в JSON-тело; laozhang-прокси форвардит провайдеру.
    extra_body = {}
    if 'negative_prompt' in final_args and final_args['negative_prompt']:
        extra_body['negative_prompt'] = final_args['negative_prompt']
    if 'seed' in final_args and final_args['seed'] is not None:
        try:
            extra_body['seed'] = int(final_args['seed'])
        except (ValueError, TypeError):
            pass
    if style_image_url:
        extra_body.update({
            'style_image_url': style_image_url,
            'style_reference': style_image_url,
            'image_url_2': style_image_url,
        })
        logger.info("[style-ref] применён референс стиля для edit")
    if extra_body:
        params['extra_body'] = extra_body

    try:
        # OpenAI-клиент images.edit() — laozhang поддерживает для flux-kontext-pro и др.
        edit_kwargs = dict(params)
        if mask_file is not None:
            edit_kwargs['mask'] = mask_file
        result = client.images.edit(image=img_file, **edit_kwargs)
        img_url = result.data[0].url if result.data else None
        b64_data = result.data[0].b64_json if result.data else None
        logger.info(f"[img2img] edit response: data_len={len(result.data) if result.data else 0} url={bool(img_url)} b64={bool(b64_data)}")
    except Exception as edit_err:
        logger.warning(f"[img2img] images.edit failed ({edit_err}), falling back to generate+image_url")
        # Фолбэк: image_url передаём через extra_body (прямой kwarg → TypeError в SDK).
        # ВНИМАНИЕ: фолбэк не поддерживает маску/outpaint — они здесь теряются.
        fb_extra = dict(params.get('extra_body') or {})
        fb_extra['image_url'] = image_url
        gen_params = {k: v for k, v in params.items() if k != 'extra_body'}
        gen_params['extra_body'] = fb_extra
        result = client.images.generate(**gen_params)
        img_url = result.data[0].url if result.data else None
        b64_data = result.data[0].b64_json if result.data else None

    # laozhang.ai может вернуть b64_json вместо url — сохраняем напрямую
    if not img_url and b64_data:
        import base64 as _b64
        raw = _b64.b64decode(b64_data)
        from django.core.files.base import ContentFile
        from aitext.models import GeneratedImage as _GenImage
        import uuid
        fname = f"generated_images/{uuid.uuid4().hex}.png"
        gen = _GenImage(
            message=message,
            prompt=prompt,
            model_name=effective_model_id,
            provider='laozhang',
            media_type='image',
            source='chat',
        )
        gen.image.save(fname, ContentFile(raw), save=True)
        if user_settings and user_settings.get('parent_id'):
            try:
                gen.parent_id = int(user_settings['parent_id'])
                gen.save(update_fields=['parent_id'])
            except (ValueError, TypeError):
                pass
        logger.info(f"[img2img] сохранено из b64_json: {fname}")
        saved_media = [gen]
        model_name = config.get('name', network.name)
        text_parts = [f"Изображение отредактировано моделью \"{model_name}\"."]
        if effective_model_id != model_id:
            text_parts.append(_FLUX_EDIT_REDIRECT_NOTE)
        text_parts.append(
            f"<img src='{gen.image.url}' alt='Отредактированное изображение' style='max-width:100%; border-radius:12px;'>"
        )
        return "\n\n".join(text_parts), saved_media, total_cost

    if not img_url:
        raise Exception("Провайдер не вернул изображение")

    seed_used = getattr(result.data[0], 'seed', final_args.get('seed'))

    # Сохраняем результат
    gen = save_media_from_url(img_url, message, prompt)
    if gen:
        gen.params = params
        try:
            gen.seed = int(seed_used) if seed_used is not None else None
        except (ValueError, TypeError):
            gen.seed = None
        gen.model_name = effective_model_id
        gen.provider = 'laozhang'
        gen.source = 'chat'
        if user_settings and user_settings.get('parent_id'):
            try:
                gen.parent_id = int(user_settings['parent_id'])
            except (ValueError, TypeError):
                pass
        gen.save(update_fields=['params', 'seed', 'model_name', 'provider', 'source', 'parent_id'])

    model_name = config.get('name', network.name)
    saved_media = [gen] if gen else []
    if saved_media:
        text_parts = [f"Изображение отредактировано моделью \"{model_name}\"."]
        if effective_model_id != model_id:
            text_parts.append(_FLUX_EDIT_REDIRECT_NOTE)
        for media in saved_media:
            text_parts.append(
                f"<img src='{media.image.url}' alt='Отредактированное изображение' style='max-width:100%; border-radius:12px;'>"
            )
        final_text = "\n\n".join(text_parts)
    else:
        final_text = f"Модель \"{model_name}\" не вернула изображение. Попробуйте изменить промт."

    return final_text, saved_media, total_cost


# Апскейл-модели laozhang (img2img). Проверено 2026-06-28: провайдер не публикует
# отдельных upscale-моделей. flux-kontext-pro используется как fallback через
# images.edit() с enhance-промтом — не истинный upscaler, но даёт визуальное улучшение.
UPSCALE_MODELS = ['clarity-upscaler', 'aura-sr', 'flux-kontext-pro']
UPSCALE_FALLBACK_PROMPTS = {
    'flux-kontext-pro': 'enhance image quality, increase sharpness and detail, high resolution',
}


def generate_upscale(generation_id, user_id=None, factor=2, image_url=None, placeholder_id=None):
    """Sprint 6: апскейл GeneratedImage в factor раз через upscale-модель провайдера.

    image_url — абсолютный URL исходника (вычисляется во view).
    placeholder_id — если передан view создал placeholder заранее; иначе создаём здесь.
    """
    from .models import GeneratedImage
    original = GeneratedImage.objects.get(id=generation_id)

    # Резолвим URL исходника (приоритет — переданный из view абсолютный URL)
    if not image_url:
        image_url = original.image.url if original.image else ''
        if image_url and not image_url.startswith('http'):
            site = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
            if site:
                image_url = site + image_url
    if not image_url:
        raise Exception("Не удалось определить URL исходного изображения для апскейла")

    try:
        factor = int(factor)
    except (ValueError, TypeError):
        factor = 2
    if factor not in (2, 4):
        factor = 2

    if placeholder_id:
        placeholder = GeneratedImage.objects.get(id=placeholder_id)
    else:
        placeholder = GeneratedImage.objects.create(
            message=original.message,
            image='',
            prompt=original.prompt or '',
            media_type='image',
            model_name=UPSCALE_MODELS[0],
            provider='laozhang',
            source=original.source or 'chat',
            parent_id=original.id,
            params={'op': 'upscale', 'factor': factor, 'source_id': original.id},
            status='running',
            progress=10,
        )

    client = get_laozhang_image_client()

    # Скачиваем исходник server-side (проверенный путь generate_image_edit,
    # не требует от провайдера доступа к публичному URL)
    import io as _io
    import requests as _req
    img_bytes = None
    try:
        resp = _req.get(image_url, timeout=30)
        resp.raise_for_status()
        img_bytes = resp.content
    except Exception as e:
        logger.warning(f"[upscale] не удалось скачать исходник ({e}); пробуем URL-in-body путь")

    img_url = None
    last_err = None
    used_model = UPSCALE_MODELS[0]
    for model_id in UPSCALE_MODELS:
        try:
            upscale_prompt = UPSCALE_FALLBACK_PROMPTS.get(model_id, '')
            extra_body = {'scale': factor, 'upscale_factor': factor}
            if img_bytes is not None:
                img_file = _io.BytesIO(img_bytes)
                img_file.name = 'source.png'
                result = client.images.edit(
                    image=img_file, model=model_id, prompt=upscale_prompt, n=1, extra_body=extra_body,
                )
            else:
                extra_body['image_url'] = image_url
                result = client.images.generate(
                    model=model_id, prompt=upscale_prompt, n=1, extra_body=extra_body,
                )
            img_url = result.data[0].url if result.data else None
            if img_url:
                used_model = model_id
                break
        except Exception as e:
            last_err = e
            logger.warning(f"[upscale] модель {model_id} не сработала: {e}")
            continue

    if not img_url:
        _fail_video_gen(placeholder)
        raise Exception(f"Upscale-провайдер не вернул изображение: {last_err}")

    gen = save_media_from_url(img_url, original.message, original.prompt or '', gen=placeholder)
    if not gen:
        _fail_video_gen(placeholder)
        raise Exception("Не удалось сохранить результат апскейла")
    gen.params = {'op': 'upscale', 'factor': factor, 'source_id': original.id}
    gen.model_name = used_model
    gen.provider = 'laozhang'
    gen.parent_id = original.id
    gen.source = original.source or 'chat'
    gen.status = 'done'
    gen.progress = 100
    gen.save(update_fields=[
        'params', 'model_name', 'provider', 'parent_id', 'source', 'status', 'progress',
    ])
    return gen


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


def _save_video_binary(content, message, prompt, gen=None):
    """Сохраняет бинарные данные как mp4, возвращает GeneratedImage.

    Если передан ``gen`` — дозаполняет placeholder-строку вместо создания новой.
    """
    path = f"generated_videos/generated_{uuid.uuid4()}.mp4"
    default_storage.save(path, ContentFile(content))
    from .models import GeneratedImage
    if gen is not None:
        gen.image = path
        gen.media_type = 'video'
        gen.save(update_fields=['image', 'media_type'])
        return gen
    return GeneratedImage.objects.create(message=message, image=path, prompt=prompt, media_type='video')


def _create_video_placeholder(message, prompt, model_id, provider):
    """Создаёт placeholder-строку GeneratedImage для видео ДО начала polling.

    Нужно, чтобы SSE-эндпоинт прогресса (в web-процессе) мог читать прогресс,
    обновляемый Celery-воркером во время генерации. image='' до завершения —
    UserFilesView отфильтровывает такие строки.
    """
    from .models import GeneratedImage
    try:
        # Переиспользуем пустой placeholder, если он уже есть (apimart resume после
        # рестарта воркера) — чтобы не плодить дубли.
        existing = GeneratedImage.objects.filter(
            message=message, media_type='video', image=''
        ).order_by('-created_at').first()
        if existing is not None:
            existing.status = 'running'
            existing.save(update_fields=['status'])
            return existing
        return GeneratedImage.objects.create(
            message=message, image='', prompt=prompt, media_type='video',
            model_name=model_id or '', provider=provider, source='chat',
            status='running', progress=0,
        )
    except Exception as e:
        logger.warning(f"Не удалось создать placeholder видео: {e}")
        return None


def _bump_video_progress(gen, provider_progress, attempt, total_attempts):
    """Обновляет прогресс placeholder-строки.

    Провайдеры почти не отдают честный progress, поэтому синтезируем его по
    счётчику poll-итераций (потолок 90%), а если провайдер дал больше — берём его.
    """
    if gen is None:
        return
    try:
        prov = int(provider_progress or 0)
    except (ValueError, TypeError):
        prov = 0
    synthetic = int((attempt + 1) / max(1, total_attempts) * 90)
    gen.progress = max(0, min(99, max(prov, synthetic)))
    try:
        gen.save(update_fields=['progress'])
    except Exception:
        pass


def _finalize_video_gen(gen):
    """Помечает placeholder как готовый (после записи файла)."""
    if gen is None or not gen.image:
        return False
    gen.status = 'done'
    gen.progress = 100
    try:
        gen.save(update_fields=['status', 'progress'])
    except Exception:
        pass
    return True


def _fail_video_gen(gen):
    """Помечает placeholder как ошибочный."""
    if gen is None:
        return
    gen.status = 'error'
    try:
        gen.save(update_fields=['status'])
    except Exception:
        pass


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
    # img2video: image_url приходит только через user_settings (нет в ui_settings.sections)
    image_url = final_args.get('image_url') or (user_settings or {}).get('image_url', '')

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
    if image_url:
        fields['image_url'] = image_url

    # Placeholder для трекинга прогресса (SSE) — создаём ДО polling
    gen_ph = _create_video_placeholder(message, prompt, model_id, 'laozhang')

    saved_media_direct = []
    video_urls = []
    try:
        logger.info(f"Video POST /v1/videos model={model_id} size={size} seconds={seconds} img2video={bool(image_url)}")
        resp = requests.post(
            f"{base_url}/videos",
            headers=auth_headers,
            files={k: (None, v) for k, v in fields.items()},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Video creation response: {str(data)[:400]}")

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
                MAX_ATTEMPTS = 120
                for attempt in range(MAX_ATTEMPTS):
                    # Первые 20 итераций — каждые 3 сек (первая минута),
                    # затем каждые 8 сек (до 15 мин суммарно)
                    time.sleep(3 if attempt < 20 else 8)
                    poll = requests.get(f"{base_url}/videos/{job_id}", headers=auth_headers, timeout=30)
                    poll.raise_for_status()
                    pd = poll.json()
                    status = (pd.get('status') or '').lower()
                    logger.info(f"Video poll {attempt + 1}/{MAX_ATTEMPTS}: status={status} progress={pd.get('progress', '?')}")
                    _bump_video_progress(gen_ph, pd.get('progress'), attempt, MAX_ATTEMPTS)

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
                                gen = _save_video_binary(cr.content, message, prompt, gen=gen_ph)
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
    except Exception:
        _fail_video_gen(gen_ph)
        raise

    model_name = config.get('name', network.name)
    saved_media = list(saved_media_direct)
    # placeholder ещё пуст (видео пришло по URL) — дозаполняем его первым URL
    for url in video_urls:
        target = gen_ph if (gen_ph is not None and not gen_ph.image) else None
        gen = save_media_from_url(url, message, prompt, media_type='video', gen=target)
        if gen:
            saved_media.append(gen)

    if _finalize_video_gen(gen_ph):
        if gen_ph not in saved_media:
            saved_media.append(gen_ph)
    else:
        # видео так и не получили — помечаем пустой placeholder как error
        # (image='' отфильтровывается из галереи UserFilesView)
        _fail_video_gen(gen_ph)

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

    # img2video: image_url приходит только через user_settings
    image_url = final_args.get('image_url') or (user_settings or {}).get('image_url', '')
    content = [{"type": "text", "text": prompt}]
    if image_url:
        # Seedance принимает кадр-источник как image_url-элемент content-массива.
        # ВНИМАНИЕ: точная форма провайдер-зависима (OpenAI-vision-подобная); если
        # seedance img2video не сработает — здесь может потребоваться плоский ключ.
        content.append({"type": "image_url", "image_url": {"url": image_url}})

    body = {
        "model": model_id,
        "content": content,
        "ratio": str(final_args.get('ratio', '16:9')),
        "duration": int(final_args.get('duration', 5)),
        "resolution": str(final_args.get('resolution', '720p')),
    }

    gen_ph = _create_video_placeholder(message, prompt, model_id, 'seedance')

    saved_media_direct = []
    video_urls = []
    try:
        logger.info(f"Seedance POST {seedance_base}/contents/generations/tasks model={model_id} img2video={bool(image_url)}")
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

        logger.info(f"Seedance polling tasks/{job_id}")
        MAX_ATTEMPTS = 120
        for attempt in range(MAX_ATTEMPTS):
            time.sleep(3 if attempt < 20 else 8)
            poll = requests.get(
                f"{seedance_base}/contents/generations/tasks/{job_id}",
                headers=auth_headers,
                timeout=30,
            )
            poll.raise_for_status()
            pd = poll.json()
            status = (pd.get('status') or '').lower()
            logger.info(f"Seedance poll {attempt + 1}/{MAX_ATTEMPTS}: status={status}")
            _bump_video_progress(gen_ph, pd.get('progress'), attempt, MAX_ATTEMPTS)

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
                            gen = _save_video_binary(cr.content, message, prompt, gen=gen_ph)
                            saved_media_direct.append(gen)
                        else:
                            logger.warning(f"Seedance fallback unexpected: {ct} size={len(cr.content)}")
                    except Exception as ce:
                        logger.error(f"Seedance fallback download failed: {ce}")
                break
            elif status in ('failed', 'error', 'expired'):
                raise Exception(f"Seedance генерация завершилась ошибкой: {pd.get('error', status)}")
    except Exception:
        _fail_video_gen(gen_ph)
        raise

    model_name = config.get('name', network.name)
    saved_media = list(saved_media_direct)
    for url in video_urls:
        target = gen_ph if (gen_ph is not None and not gen_ph.image) else None
        gen = save_media_from_url(url, message, prompt, media_type='video', gen=target)
        if gen:
            saved_media.append(gen)

    if _finalize_video_gen(gen_ph):
        if gen_ph not in saved_media:
            saved_media.append(gen_ph)
    else:
        _fail_video_gen(gen_ph)

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
                  'negative_prompt', 'generation_type', 'enable_gif', 'official_fallback',
                  'size', 'generate_audio', 'camerafixed', 'quality', 'template',
                  'shot_type', 'prompt_optimizer']:
        if param in final_args and final_args[param] is not None:
            body[param] = final_args[param]

    # Пустые строки и «нулевые» select-значения apimart не принимает — не шлём
    for param in ['negative_prompt', 'template']:
        if param in body and (not body[param] or body[param] == 'none'):
            del body[param]

    # duration должен быть integer (apimart ожидает число, select возвращает строку)
    if 'duration' in body:
        try:
            body['duration'] = int(body['duration'])
        except (ValueError, TypeError):
            pass

    model_lower = (model_id or '').lower()

    # Kling v2.6: аудио работает только в pro mode — принудительно переключаем.
    # Только для этой модели: у kling-v3 звук есть во всех режимах, а у
    # wan/vidu/pixverse параметра mode нет вовсе — лишний mode ломает запрос.
    if body.get('audio') and model_lower == 'kling-v2-6':
        body['mode'] = 'pro'

    # Hailuo: 1080p доступен только для роликов 6 сек — иначе провайдер отклонит
    if 'hailuo' in model_lower and body.get('resolution') == '1080p':
        if isinstance(body.get('duration'), int) and body['duration'] > 6:
            logger.info("APIMart Hailuo: 1080p поддерживает только 6 сек, duration понижен")
            body['duration'] = 6

    # img2video: image_url приходит только через user_settings.
    # Имя параметра у моделей разное: большинство ждёт МАССИВ image_urls,
    # Hailuo — строку first_frame_image. Берём из metadata.i2v_param
    # (add_video_models), фолбэк — по имени модели.
    image_url = final_args.get('image_url') or (user_settings or {}).get('image_url', '')
    if image_url:
        i2v_param = (config.get('metadata') or {}).get('i2v_param')
        if not i2v_param:
            i2v_param = 'first_frame_image' if 'hailuo' in model_lower else 'image_urls'
        if i2v_param == 'image_urls':
            body['image_urls'] = [image_url]
        else:
            body[i2v_param] = image_url
        # Формат кадра при оживлении фото определяется самим фото; часть
        # моделей (wan, pixverse, sora) отклоняет size/aspect_ratio вместе с
        # изображением — убираем, кроме adaptive-подобных дефолтов
        body.pop('aspect_ratio', None)
        if body.get('size') and body['size'] != 'adaptive':
            body.pop('size', None)
    else:
        # template у wan — эффект оживления фото, без фото не имеет смысла
        body.pop('template', None)

    # Placeholder для трекинга прогресса (SSE). При рестарте воркера переиспользуется
    # (reuse по image=''). Краевой случай: если воркер умер ПОСЛЕ записи видео, но ДО
    # сохранения final_text — reuse не найдёт заполненную строку и создаст второй
    # placeholder → возможно второе видео. Редко; осознанный компромисс.
    gen_ph = _create_video_placeholder(message, prompt, model_id, 'apimart')

    # Если задача была перезапущена (celery restart), берём сохранённый task_id.
    # ВНИМАНИЕ: message.content используется apimart как хранилище task_id до завершения.
    import json as _json
    task_id = None
    try:
        saved = _json.loads(message.content or '{}')
        task_id = saved.get('_apimart_task_id')
        if task_id:
            logger.info(f"APIMart resuming existing task_id={task_id} (task restarted)")
    except Exception:
        task_id = None

    video_urls = []
    try:
        if not task_id:
            logger.info(f"APIMart Video POST model={model_id} img2video={bool(image_url)} params={body}")
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

            # Сохраняем task_id в message до начала polling — при рестарте воркера не создаём новое видео
            try:
                message.content = _json.dumps({'_apimart_task_id': task_id})
                message.save(update_fields=['content'])
            except Exception as e:
                logger.warning(f"Не удалось сохранить apimart task_id: {e}")

        logger.info(f"APIMart task_id={task_id}, polling...")

        # Sprint 7 (reliability): дублируем task_id в params placeholder-строки —
        # на случай резюма после краша воркера (основной источник — message.content).
        if gen_ph is not None and task_id:
            try:
                gen_ph.params = {'_apimart_task_id': task_id, 'model': model_id}
                gen_ph.save(update_fields=['params'])
            except Exception:
                pass

        MAX_ATTEMPTS = 120
        for attempt in range(MAX_ATTEMPTS):
            time.sleep(3 if attempt < 20 else 8)
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
            logger.info(f"APIMart poll {attempt + 1}/{MAX_ATTEMPTS}: status={status} progress={progress}")
            _bump_video_progress(gen_ph, status_obj.get('progress'), attempt, MAX_ATTEMPTS)

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
    except Exception:
        _fail_video_gen(gen_ph)
        raise

    model_name = config.get('name', network.name)
    saved_media = []
    for url in video_urls:
        target = gen_ph if (gen_ph is not None and not gen_ph.image) else None
        # Sprint 7 (reliability): 3 попытки финальной загрузки с паузой 5с.
        # max_retries=1 у save_media_from_url, чтобы не вкладывать ретраи (3×1=3, а не 9).
        gen = None
        for dl_attempt in range(3):
            gen = save_media_from_url(
                url, message, prompt, media_type='video', gen=target, max_retries=1
            )
            if gen:
                break
            if dl_attempt < 2:
                logger.warning(
                    f"[apimart] финальная загрузка видео не удалась "
                    f"(попытка {dl_attempt + 1}/3), повтор через 5с"
                )
                time.sleep(5)
        if gen:
            saved_media.append(gen)

    if _finalize_video_gen(gen_ph):
        if gen_ph not in saved_media:
            saved_media.append(gen_ph)
    else:
        _fail_video_gen(gen_ph)

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
            # apimart — основной сервис для видео. При его недоступности пробуем
            # laozhang, но только если админ задал laozhang-эквивалент модели в
            # metadata.laozhang_fallback_model (имена моделей у сервисов разные).
            try:
                return generate_video_apimart(network, user_msg, message, user_settings)
            except Exception as e:
                fb_model = config.get('metadata', {}).get('laozhang_fallback_model')
                fallback_on = getattr(settings, 'AI_PROVIDER_FALLBACK', True)
                # Ошибки валидации настроек — не повод для фолбэка.
                is_settings_err = str(e).startswith('Ошибки в настройках')
                if fallback_on and fb_model and not is_settings_err:
                    logger.warning(
                        "APIMart видео недоступно (%s); фолбэк → laozhang model=%s", e, fb_model
                    )
                    orig_model = network.model_name
                    try:
                        network.model_name = fb_model
                        return generate_video_laozhang(network, user_msg, message, user_settings)
                    finally:
                        network.model_name = orig_model
                raise
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

    # Img2img: если передан image_url — роутим на редактирование изображения.
    # Если передан только style_image_url (референс стиля без исходника) — остаётся
    # обычная генерация, style_image_url форвардится через _build_image_params.
    if user_settings and user_settings.get('image_url'):
        return generate_image_edit(network, user_msg, message, user_settings)

    # Sprint 6: референс стиля приходит через user_settings (нет в ui_settings.sections),
    # поэтому validate_and_merge_settings его не выдаёт — прокидываем вручную в final_args.
    if user_settings and user_settings.get('style_image_url'):
        final_args['style_image_url'] = user_settings['style_image_url']

    # Некоторые модели (Seedream, Gemini image) не принимают size/n — используем minimal_params.
    if config.get('metadata', {}).get('minimal_params'):
        final_args['_minimal_params'] = True

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
            # Храним user-settings-форму (final_args), а не API-форму (image_params):
            # она ключуется именами ui_settings (size/seed/negative_prompt/num_images)
            # и точно воспроизводится эндпоинтом rerun.
            gen_img.params = final_args
            seed_used = getattr(img_data, 'seed', None)
            if seed_used is None:
                seed_used = (image_params.get('extra_body') or {}).get('seed')
            try:
                gen_img.seed = int(seed_used) if seed_used is not None else None
            except (ValueError, TypeError):
                gen_img.seed = None
            gen_img.model_name = model_id
            gen_img.provider = 'laozhang'
            gen_img.source = 'chat'
            gen_img.save(update_fields=['params', 'seed', 'model_name', 'provider', 'source'])
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
