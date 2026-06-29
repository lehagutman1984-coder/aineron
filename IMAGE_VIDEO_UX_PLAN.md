# IMAGE_VIDEO_UX_PLAN.md — Путь к лидерству в России и Европе

> Обновлено: 2026-06-29  
> Провайдеры: **laozhang.ai** (изображения + текст), **apimart.ai** (видео)

---

## СТАТУС РЕАЛИЗАЦИИ — ЧТО СДЕЛАНО

### Изображения — laozhang.ai

| Функция | Статус | Коммит / Заметка |
|---|---|---|
| Генерация DALL-E 3 / GPT Image 1/2 | ✅ РАБОТАЕТ | стабильно |
| Генерация Flux 2 Pro/Max/Flex, Kontext Pro/Max | ✅ РАБОТАЕТ | стабильно |
| **GPT Image 1.5** | ✅ ДОБАВЛЕНО 29.06 | новая модель |
| **Seedream 4.0 / 4.5 / 5.0** | ✅ ДОБАВЛЕНО 29.06 | ByteDance, minimal_params fix |
| **Gemini 3.1 Flash Image / 3 Pro Image / 2.5 Flash Image** | ✅ ДОБАВЛЕНО 29.06 | Google Imagen, minimal_params fix |
| img2img / Flux Kontext редактирование | ✅ РАБОТАЕТ | generate_image_edit |
| Outpaint (расширение холста по направлению) | ✅ РАБОТАЕТ | фикс 28.06 |
| **Generative Expand (расширение до соотношения)** | ✅ СДЕЛАНО 28.06 | _prepare_expand_to_ratio + UI в EditImageModal |
| **Fullscreen Lightbox (просмотр / zoom / скачать)** | ✅ СДЕЛАНО 28.06 | ZoomableImage + createPortal overlay |
| Upscale / Детализация | ✅ РАБОТАЕТ | через img2img |
| Style Reference (Flux Kontext) | ✅ РАБОТАЕТ | image_url как референс |
| Vary / Вариации | ✅ РАБОТАЕТ | повторный запрос |
| Before/After слайдер | ✅ РАБОТАЕТ | BeforeAfterSlider компонент |
| Batch генерация (×1/×2/×4) | ✅ РАБОТАЕТ | параллельные запросы |
| **Background Removal** | ✅ АКТИВНО 29.06 | rembg добавлен в requirements.txt, rebuild активирует |
| Inpaint (mask → GPT Image 1) | ✅ РАБОТАЕТ | подтверждено 29.06 |
| AI Auto-Select (SAM2) | ❌ НЕТ | laozhang.ai не поддерживает — нужен новый провайдер |

### Видео — apimart.ai

| Функция | Статус | Заметка |
|---|---|---|
| Text2Video: Sora 2 / Pro | ✅ РАБОТАЕТ | duration 4/5/10/20 сек, aspect ratio |
| Text2Video: Veo 3.1 Fast / Quality | ✅ РАБОТАЕТ | аудиодорожка, resolution |
| Text2Video: Kling v2.6 | ✅ РАБОТАЕТ | аудио (pro mode), camera_type |
| Text2Video: Seedance 1.5 Pro / 2.0 | ✅ РАБОТАЕТ | аудио, camerafixed, size |
| Img2Video (оживить изображение) | ✅ РАБОТАЕТ | image_url в теле запроса |
| Прогресс видеогенерации | ✅ РАБОТАЕТ | polling |
| **Extend Video** | ❌ НЕТ | apimart вернул `Invalid URL` — endpoint не существует |
| **Lip Sync** | ❌ НЕТ | apimart вернул `Invalid URL` — endpoint не существует |
| Motion Brush | ❌ НЕТ | требует Runway ML |
| Video Inpaint | ❌ НЕТ | требует Runway ML или Kling enterprise |
| PikaEffects (inflate/melt/explode) | ❌ НЕТ | требует Pika API |

### Новые текстовые модели — добавлено 29.06

| Группа | Добавленные модели |
|---|---|
| DeepSeek | V3.2, V4 Flash, V4 Pro |
| Gemini | 3.5 Flash, 3.1 Pro |
| GLM | 5, 4.6 |
| GPT-5 | Mini, Pro, 5.1 |
| Grok | 4.3 |
| Kimi | K2.5, K2.6 |
| Qwen | 3.5 Flash, 3.5 Plus |
| MiniMax | M2.5, M2.7 |

---

## ЧТО ТРЕБУЕТ НОВОГО ПРОВАЙДЕРА — ФИНАЛЬНЫЙ ВЕРДИКТ

> Проверено 29.06 прямыми API-запросами на apimart.ai и laozhang.ai.

| Фича | Что проверили | Результат | Нужен провайдер |
|---|---|---|---|
| **Extend Video** | `POST apimart.ai/v1/videos/extend` | `Invalid URL` — endpoint не существует | Kling official API или Runway ML |
| **Lip Sync** | `POST apimart.ai/v1/videos/lip-sync` | `Invalid URL` — endpoint не существует | Kling official API (есть `/v1/videos/lip-sync`) или SyncLabs |
| **AI Auto-Select** | laozhang.ai models list | `sam2`, `segment-anything` — отсутствуют | fal.ai (`fal-ai/sam2`) |
| **Motion Brush** | — | нет у apimart, laozhang | Runway ML API |
| **PikaEffects** (inflate/explode/melt) | — | нет у apimart, laozhang | Pika API |
| **Inpaint в видео** | — | нет у apimart, laozhang | Runway ML или Kling enterprise |
| **Ideogram** (текст в изображении) | laozhang.ai models list | отсутствует в каталоге | ideogram.ai API |

---

## ОСТАВШИЕСЯ ЗАДАЧИ (в рамках текущих провайдеров)

### Приоритет 1 — MaskEditor UX

Текущий редактор маски неудобен (чёрный холст, непонятно что закрашиваешь).

Нужно:
- Фоновое изображение с opacity 0.5 под маской
- Ластик (режим erase)
- Размер кисти S/M/L
- Подсказка: "Закрасьте область для редактирования"

### Приоритет 2 — Тестирование Gemini Image моделей

Gemini image модели добавлены с `minimal_params: true` (как Seedream).
Нужно проверить что они реально работают через аналогичный тест:

```bash
docker-compose exec web python3 -c "import os,django; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; django.setup(); from django.conf import settings; import requests; r=requests.post(settings.LAOZHANG_API_URL+'/images/generations',headers={'Authorization':'Bearer '+settings.LAOZHANG_API_KEY},json={'model':'gemini-3.1-flash-image','prompt':'a cat'},timeout=30); print(r.status_code,r.text[:400])"
```

---

## НОВЫЕ ПРОВАЙДЕРЫ — КОГДА ДОБАВЛЯТЬ

| Фича | Провайдер | Приоритет | Трудоёмкость |
|---|---|---|---|
| **Extend Video + Lip Sync** | Kling официальный API (`klingai.com/developer`) | Высокий — закрывает 2 фичи | ~4 часа |
| **AI Auto-Select** | fal.ai SDK (`fal-ai/sam2`) | Средний — уникальная фича | ~3 часа |
| **Ideogram** (профессиональный текст) | ideogram.ai API | Средний — нет конкурентов в RU | ~2 часа |
| **PikaEffects** | Pika API | Низкий — вирусная, но нишевая | ~4 часа |
| **Motion Brush + Video Inpaint** | Runway ML API | Низкий — дорого ($0.05-0.10/сек) | ~6 часов |

---

## ОПРЕДЕЛЕНИЕ "ГОТОВО"

Фича считается готовой когда:
1. Живой API-запрос вернул корректный результат (не только TypeScript без ошибок)
2. Ошибки провайдера показываются пользователю по-русски
3. Если новый endpoint — сначала подтверждён прямым curl/python тестом

---

## ТЕХНИЧЕСКИЕ ЗАМЕТКИ

### minimal_params для Seedream / Gemini image

Эти модели не принимают `size` и `n` параметры — возвращают `400 InvalidParameter`.
Фикс: `config_json.metadata.minimal_params: true` → `_build_image_params` отправляет только `{model, prompt}`.

Тест подтверждён 29.06: `POST /v1/images/generations {"model": "seedream-5-0-260128", "prompt": "a cat"}` → `200 OK` с URL изображения.

### Команды обновления моделей

```bash
# Добавить все новые модели (изображения + текст)
docker-compose exec web python manage.py add_new_models

# Скачать аватары для новых моделей
docker-compose exec web python manage.py download_avatars

# Добавить видео-модели apimart
docker-compose exec web python manage.py add_video_models
```
