import uuid
import os
import base64
import logging
import datetime
from celery import shared_task
from openai import OpenAI
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from .models import Message, NeuralNetwork, GeneratedImage, Project
from .file_utils import prepare_media_for_ai
from .fal_utils import generate_with_falai, validate_and_merge_settings
from users.models import UserSpending
from .code_formatter import CodeFormatter

logger = logging.getLogger(__name__)

_client = None


def get_laozhang_client():
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=settings.LAOZHANG_API_URL,
            api_key=settings.LAOZHANG_API_KEY,
        )
    return _client


def translate_to_english(text, network_name):
    """Переводит текст на английский через DeepSeek (laozhang.ai)"""
    if not text or not text.strip():
        return text

    try:
        client = get_laozhang_client()
        completion = client.chat.completions.create(
            model="deepseek-v3",
            messages=[
                {"role": "system",
                 "content": "You are a translator. Translate the user's message into English. Preserve the meaning and tone. Output only the translated text. If the text is already in English, return the text unchanged."},
                {"role": "user", "content": text}
            ],
            temperature=0.3,
            max_tokens=500,
        )
        translated = completion.choices[0].message.content.strip()
        logger.info(f"Переведён промт для {network_name}: '{text[:50]}...'")
        return translated
    except Exception as e:
        logger.error(f"Ошибка перевода промта: {e}")
        return text


def generate_images_html(files):
    """Генерирует HTML для отображения сгенерированных медиа-файлов"""
    html_parts = []
    for file in files:
        file_url = file.image.url if hasattr(file, 'image') else ''
        if not file_url:
            continue
        model_name = "fal.ai"
        if hasattr(file, 'media_type') and file.media_type == 'video':
            html_parts.append(f'''
            <div class="generated-media generated-video">
                <div class="media-header">
                    <span class="media-model">Сгенерировано видео: {model_name}</span>
                    <div class="media-actions">
                        <button class="media-action-btn download-media" data-url="{file_url}">
                            <i class="fas fa-download"></i> Скачать
                        </button>
                    </div>
                </div>
                <div class="media-content">
                    <video controls src="{file_url}" style="max-width:100%; border-radius:12px;"></video>
                </div>
            </div>
            ''')
        else:
            html_parts.append(f'''
            <div class="generated-media generated-image">
                <div class="media-header">
                    <span class="media-model">Сгенерировано изображение: {model_name}</span>
                    <div class="media-actions">
                        <button class="media-action-btn download-media" data-url="{file_url}">
                            <i class="fas fa-download"></i> Скачать
                        </button>
                    </div>
                </div>
                <div class="media-content">
                    <img src="{file_url}" alt="Сгенерированное изображение" style="max-width:100%; border-radius:12px;">
                </div>
            </div>
            ''')
    return '\n'.join(html_parts)


def truncate_text(text, max_length):
    """Обрезает текст до указанной длины, добавляя '...' в конце"""
    if max_length > 0 and text and len(text) > max_length:
        return text[:max_length] + "..."
    return text


WEB_SEARCH_MODEL = "grok-3-deepsearch"  # Grok 3 DeepSearch — встроенный веб-поиск на laozhang.ai
_WEB_SEARCH_FALLBACK = "grok-3-search"  # резерв, если deepsearch недоступен


def build_web_search_message(search_results: str, user_query: str) -> dict:
    """Формирует system-сообщение с результатами поиска — как у Perplexity/ChatGPT."""
    now = datetime.datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC")
    query_preview = user_query[:200].strip()
    content = (
        f"[Результаты веб-поиска — {now}]\n"
        f"Запрос: {query_preview}\n\n"
        f"{search_results[:4500]}\n\n"
        "[Инструкция к использованию результатов]\n"
        "• Факты выше актуальны и получены из интернета только что — давай им приоритет над тренировочными данными\n"
        "• При ссылке на конкретный факт из поиска укажи его номер в скобках, например [1], [2]\n"
        "• Если источник неизвестен или факт общеизвестен — не придумывай ссылку\n"
        "• Отвечай на языке пользователя\n"
        "[Конец результатов поиска]"
    )
    return {"role": "system", "content": content}


def call_web_search(user_query: str, log_prefix: str = "") -> str:
    """Вызывает Grok DeepSearch (с fallback на grok-3-search), возвращает текст или ''."""
    client = get_laozhang_client()
    grok_message = [{
        "role": "user",
        "content": (
            f"{user_query[:1800]}\n\n"
            "Search the web and return findings as numbered facts:\n"
            "[1] key fact (date if applicable, source if available)\n"
            "[2] ...\n"
            "Be concise and factual. Match the language of the query."
        ),
    }]
    for model in (WEB_SEARCH_MODEL, _WEB_SEARCH_FALLBACK):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=grok_message,
                max_tokens=2000,
            )
            result = resp.choices[0].message.content.strip()
            logger.info(f"{log_prefix}Web search OK ({model}): {len(result)} chars")
            return result
        except Exception as e:
            logger.warning(f"{log_prefix}Web search FAILED ({model}): {e}")
    logger.error(f"{log_prefix}All web search models unavailable")
    return ""


@shared_task(bind=True, max_retries=3)
def generate_ai_response(self, message_id, web_search=False):
    try:
        message = Message.objects.get(id=message_id)
        if message.role != 'assistant':
            logger.warning(f"Сообщение {message_id} не является сообщением ассистента, пропуск")
            return

        chat = message.chat
        network = chat.network
        user = chat.user
        user_msg = chat.messages.filter(role='user', created_at__lt=message.created_at).order_by('-created_at').first()
        if not user_msg:
            user_msg = chat.messages.filter(role='user').order_by('-created_at').first()

        # ========== fal.ai провайдер ==========
        if network.provider == 'fal-ai':
            if not network.model_name:
                message.status = Message.Status.FAILED
                message.error_message = "У нейросети не указан model_name для fal.ai"
                message.save()
                return

            logger.info(f"=== Генерация через fal.ai для сообщения {message_id}, нейросеть: {network.name} ===")
            stars_deducted = False
            total_cost = 0
            try:
                user_settings = user_msg.settings if user_msg else {}

                config = network.config_json
                if not config:
                    raise Exception("Отсутствует конфигурация для fal.ai модели")

                base_cost = network.cost_per_message
                if user_settings:
                    _, errors, extra_cost = validate_and_merge_settings(config, user_settings)
                    if errors:
                        raise Exception("Ошибки в настройках: " + "; ".join(errors))
                else:
                    extra_cost = 0

                total_cost = base_cost + extra_cost

                if user.pages_count < total_cost:
                    raise Exception(f"Недостаточно звёзд. Нужно {total_cost} зв., у вас {user.pages_count} зв.")

                user.spend_pages(total_cost)
                stars_deducted = True
                UserSpending.objects.create(
                    user=user,
                    amount=total_cost,
                    description=f"Сообщение в чате с {network.name} (включая настройки)"
                )
                logger.info(f"Списано {total_cost} зв. у пользователя {user.email}")

                original_prompt = user_msg.content if user_msg else ""
                if network.translate_to_english and original_prompt:
                    logger.info(f"Переводим промт для {network.name}...")
                    translated_prompt = translate_to_english(original_prompt, network.name)
                    original_content = user_msg.content
                    user_msg.content = translated_prompt
                    try:
                        final_text, saved_images, _ = generate_with_falai(network, user_msg, message,
                                                                          user_settings=user_settings)
                    finally:
                        user_msg.content = original_content
                else:
                    final_text, saved_images, _ = generate_with_falai(network, user_msg, message,
                                                                      user_settings=user_settings)

                message.content = final_text
                message.plain_text = final_text
                message.status = Message.Status.COMPLETED
                message.save()
                logger.info(
                    f"fal.ai ответ сгенерирован для сообщения {message_id}, сохранено изображений: {len(saved_images)}")
                return

            except Exception as e:
                error_str = str(e)
                logger.error(f"Ошибка генерации изображения для сообщения {message_id}: {e}")
                if stars_deducted:
                    user.add_pages(total_cost)
                    logger.info(f"Возвращено {total_cost} зв. пользователю {user.email} из-за ошибки генерации")
                message.status = Message.Status.FAILED
                if 'billing' in error_str.lower() or 'balance' in error_str.lower() or 'quota' in error_str.lower():
                    message.error_message = "Проблема с провайдером, обратитесь к администратору сервиса для решения проблем."
                else:
                    message.error_message = "Произошла ошибка генерации, звезды возвращены на ваш баланс, пожалуйста выберите другую нейросеть из каталога, пока мы будем устранять проблему."
                message.save()
                return

        # ========== laozhang.ai текст провайдер ==========
        if not network.model_name:
            message.status = Message.Status.FAILED
            message.error_message = "У нейросети не указана модель"
            message.save()
            return

        logger.info(f"=== Генерация ответа для сообщения {message_id}, нейросеть: {network.name} ===")

        max_input_tokens = network.max_input_tokens

        # Получаем последние 20 сообщений из истории
        history_qs = chat.messages.filter(status=Message.Status.COMPLETED).order_by('-created_at')[:20]
        history = list(reversed(history_qs))

        messages_for_api = []

        if chat.project_id:
            try:
                proj = Project.objects.get(id=chat.project_id)
                if proj.system_prompt:
                    messages_for_api.append({"role": "system", "content": proj.system_prompt})
            except Exception:
                pass

        if network.has_prompt and network.prompt:
            messages_for_api.append({"role": "system", "content": network.prompt})

        # Добавляем сообщения из истории
        for msg in history:
            if msg.id == message.id:
                continue
            if user_msg and msg.id == user_msg.id:
                continue

            if msg.role == 'user':
                content_text = msg.content
                extracted = msg.extracted_content
                if max_input_tokens > 0:
                    content_text = truncate_text(content_text, max_input_tokens)
                    extracted = truncate_text(extracted, max_input_tokens) if extracted else ''
                if extracted:
                    combined = f"{content_text}\n\n{extracted}" if content_text else extracted
                    messages_for_api.append({"role": "user", "content": combined})
                elif content_text:
                    messages_for_api.append({"role": "user", "content": content_text})
            elif msg.role == 'assistant':
                assistant_text = msg.plain_text or msg.content
                if max_input_tokens > 0:
                    assistant_text = truncate_text(assistant_text, max_input_tokens)
                if assistant_text:
                    messages_for_api.append({"role": "assistant", "content": assistant_text})

        # Добавляем текущее сообщение пользователя
        if user_msg:
            user_content = user_msg.content or ""
            user_extracted = user_msg.extracted_content or ""
            attachments = user_msg.attachments.all()
            content_array = []
            if user_extracted:
                if max_input_tokens > 0:
                    user_extracted = truncate_text(user_extracted, max_input_tokens)
                content_array.append({"type": "text", "text": user_extracted})
            if user_content:
                if max_input_tokens > 0:
                    user_content = truncate_text(user_content, max_input_tokens)
                content_array.append({"type": "text", "text": user_content})
            for att in attachments:
                if not att.extracted_text:
                    prepared = prepare_media_for_ai(att)
                    if prepared:
                        content_array.append(prepared)
            if content_array:
                messages_for_api.append({"role": "user", "content": content_array})

        if not messages_for_api:
            messages_for_api.append({"role": "user", "content": "Привет"})

        # ── Двухэтапный веб-поиск ──────────────────────────────────────────────
        if web_search:
            user_query = ""
            for m in reversed(messages_for_api):
                if m.get("role") == "user":
                    c = m.get("content", "")
                    user_query = c if isinstance(c, str) else " ".join(
                        p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"
                    )
                    break
            if not user_query:
                user_query = "информация"

            search_results = call_web_search(user_query, log_prefix=f"[msg {message_id}] ")

            if search_results:
                message.search_context = search_results
                message.save(update_fields=['search_context'])
                # Вставляем прямо перед последним user-сообщением — как делает Perplexity
                insert_pos = max(len(messages_for_api) - 1, 0)
                messages_for_api.insert(insert_pos, build_web_search_message(search_results, user_query))

        effective_model = network.model_name  # всегда используем выбранную пользователем модель
        client = get_laozhang_client()
        completion_kwargs = {
            "model": effective_model,
            "messages": messages_for_api,
            "temperature": 0.7,
        }
        if network.max_tokens > 0:
            completion_kwargs["max_tokens"] = network.max_tokens

        # Обёртка для обработки ошибки deprecated модели
        try:
            completion = client.chat.completions.create(**completion_kwargs)
        except Exception as api_error:
            error_str = str(api_error)
            # Проверяем статус-код (если есть) или наличие ключевых слов
            status_code = getattr(api_error, 'status_code', None)
            if status_code == 404 or 'deprecated' in error_str.lower() or 'free model' in error_str.lower():
                logger.error(f"Ошибка при вызове модели {network.model_name}: {error_str}")
                message.status = Message.Status.FAILED
                message.error_message = "Пожалуйста выберите другую бесплатную нейросеть. Эта нейросеть более не предоставляется бесплатно, и скоро пропадет из каталога."
                message.save()
                return
            else:
                # Другие ошибки — пробуем retry
                raise

        response = completion.choices[0].message

        # Извлечение plain_text
        plain_text = ""
        if response.content:
            if isinstance(response.content, str):
                plain_text = response.content
            elif isinstance(response.content, list):
                text_parts = []
                for item in response.content:
                    if item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
                plain_text = "\n".join(text_parts)

        formatted_html = CodeFormatter.format_ai_response(plain_text)

        # Обработка изображений (если есть)
        saved_images = []
        image_urls = []

        content = response.content
        if isinstance(content, str) and content.startswith('data:image'):
            image_urls.append(content)
        elif isinstance(content, list):
            for item in content:
                if item.get('type') == 'image_url':
                    img_url = item.get('image_url', {}).get('url')
                    if img_url and img_url.startswith('data:image'):
                        image_urls.append(img_url)
        if hasattr(response, 'images') and response.images:
            for img_obj in response.images:
                img_url = img_obj.get('image_url', {}).get('url')
                if img_url and img_url.startswith('data:image'):
                    image_urls.append(img_url)

        unique_image_urls = list(dict.fromkeys(image_urls))

        def save_image(base64_data, prompt):
            try:
                header, data = base64_data.split(',', 1)
                ext = 'png'
                if 'image/png' in header:
                    ext = 'png'
                elif 'image/jpeg' in header:
                    ext = 'jpg'
                elif 'image/webp' in header:
                    ext = 'webp'
                img_data = base64.b64decode(data)
                filename = f"generated_{uuid.uuid4()}.{ext}"
                path = f"generated_images/{filename}"
                default_storage.save(path, ContentFile(img_data))
                gen_img = GeneratedImage.objects.create(
                    message=message,
                    image=path,
                    prompt=prompt
                )
                return gen_img
            except Exception as e:
                logger.error(f"Ошибка сохранения изображения: {e}")
                return None

        for img_url in unique_image_urls:
            gen_img = save_image(img_url, user_msg.content if user_msg else '')
            if gen_img:
                saved_images.append(gen_img)

        if saved_images:
            images_html = generate_images_html(saved_images)
            formatted_html = images_html + formatted_html

        message.content = formatted_html
        message.plain_text = plain_text
        message.status = Message.Status.COMPLETED
        message.save()

        logger.info(f"AI ответ сгенерирован для сообщения {message_id}, сохранено изображений: {len(saved_images)}")

    except Exception as e:
        logger.error(f"Ошибка генерации AI ответа для сообщения {message_id}: {e}")
        try:
            message = Message.objects.get(id=message_id)
            message.status = Message.Status.FAILED
            message.error_message = str(e)
            message.save()
        except Message.DoesNotExist:
            pass
        raise self.retry(exc=e, countdown=60)
