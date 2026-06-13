import json
import os
import logging
import uuid
import time
import requests
import urllib.request
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
import fal_client

logger = logging.getLogger(__name__)


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
            # Ищем выбранную опцию и её extra_cost
            for opt in field.get('options', []):
                if opt.get('value') == value:
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

            # 2. Select
            elif field_type == 'select':
                allowed = [opt['value'] for opt in field.get('options', [])]
                if user_value in allowed:
                    set_value(name, user_value)
                    add_extra_cost(field, user_value)
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


def get_fal_client():
    """Возвращает настроенный fal_client"""
    os.environ['FAL_KEY'] = settings.FAL_KEY
    return fal_client

def save_media_from_url(url, message, prompt, media_type='image', max_retries=3, timeout=60):
    """
    Скачивает медиа по URL с повторными попытками и сохраняет в GeneratedImage.
    Поддерживает видео (mp4, webm, avi, mov, mkv) и изображения (png, jpg, jpeg, webp, gif, bmp, tiff).
    """
    for attempt in range(max_retries):
        try:
            logger.info(f"📥 Скачивание медиа из {url}, попытка {attempt + 1}/{max_retries}")
            response = requests.get(url, timeout=timeout, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()

            content_type = response.headers.get('content-type', '').lower()
            file_data = response.content
            logger.info(f"✅ Медиа скачано, размер: {len(file_data)} байт, тип: {content_type}")

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
            logger.error(f"❌ Ошибка скачивания (попытка {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                logger.error(f"Не удалось скачать {url} после {max_retries} попыток")
                return None
            time.sleep(3)
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при скачивании {url}: {e}")
            return None

    return None


def generate_with_falai(network, user_msg, message, user_settings=None):
    """
    Генерирует контент через fal.ai.
    network: объект NeuralNetwork
    user_msg: сообщение пользователя (Message)
    message: сообщение ассистента (pending)
    user_settings: настройки от пользователя (словарь)
    Возвращает (final_text, saved_media, total_cost)
    """
    config = network.config_json
    if not config:
        raise Exception("Отсутствует конфигурация для fal.ai модели")

    model_id = network.model_name
    if not model_id:
        raise Exception("Не указан model_name для fal.ai")

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

    # Извлекаем промпт
    prompt = user_msg.content if user_msg else ""
    final_args['prompt'] = prompt

    # Вызываем fal.ai
    logger.info(f"Запуск fal.ai модели {model_id} с аргументами: {final_args}")
    client = get_fal_client()
    try:
        result = client.run(model_id, arguments=final_args)
    except Exception as e:
        logger.error(f"Ошибка вызова fal.ai: {e}")
        raise

    # Обрабатываем результат
    media_urls = []
    possible_keys = ['image', 'images', 'video', 'videos', 'url', 'output']
    for key in possible_keys:
        if key in result:
            value = result[key]
            if isinstance(value, dict) and 'url' in value:
                media_urls.append(value['url'])
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and 'url' in item:
                        media_urls.append(item['url'])
                    elif isinstance(item, str) and item.startswith('http'):
                        media_urls.append(item)
            elif isinstance(value, str) and value.startswith('http'):
                media_urls.append(value)

    # Сохраняем медиа
    saved_media = []
    failed_urls = []
    for url in media_urls:
        gen_img = save_media_from_url(url, message, prompt)
        if gen_img:
            saved_media.append(gen_img)
        else:
            failed_urls.append(url)

    # Формируем текст ответа
    model_name = config.get('name', network.name)
    media_count = len(saved_media)
    if media_count > 0:
        first_media = saved_media[0]
        if first_media.media_type == 'video':
            type_word = 'видео'
            tag = 'video'
            attrs = 'controls width="100%" style="max-width:100%; border-radius:12px;"'
        else:
            type_word = 'изображений'
            tag = 'img'
            attrs = 'alt="Сгенерированное изображение" style="max-width:100%; border-radius:12px;"'

        text_parts = [f"✅ Сгенерировано {media_count} {type_word} моделью \"{model_name}\"."]
        for media in saved_media:
            if media.media_type == 'video':
                text_parts.append(f"<{tag} src='{media.image.url}' {attrs}></{tag}>")
            else:
                text_parts.append(f"<{tag} src='{media.image.url}' {attrs}>")
        final_text = "\n\n".join(text_parts)
    else:
        # Если медиа не сохранены, но есть URL в ответе
        if media_urls:
            # Формируем ссылки для скачивания
            download_links = []
            for url in media_urls:
                download_links.append(f'<a href="{url}" target="_blank" class="fal-download-link" download>скачать</a>')
            links_text = ", ".join(download_links)
            final_text = f"✅ Модель \"{model_name}\" обработала запрос: \"{prompt[:100]}\".\n\n⚠️ Извините, мы не смогли сохранить медиа на наши сервера, но вы можете {links_text} самостоятельно."
        else:
            final_text = f"✅ Модель \"{model_name}\" обработала запрос: \"{prompt[:100]}\". (Нет медиа в ответе)"

    return final_text, saved_media, total_cost
