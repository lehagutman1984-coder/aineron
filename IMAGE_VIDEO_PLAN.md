# План развития Image / Video Generation — aineron.ru

**Горизонт**: 7 спринтов × 1 неделя (≈2 месяца)
**Цель**: догнать и обойти Midjourney / Firefly / Runway / Pika / Kling по ключевым возможностям creative-генерации и стать №1 в РФ по медиа-генерации.
**Стек**: Django + DRF + Celery + Redis + PostgreSQL + Next.js (App Router).

---

## Что реализовано сегодня

### Модели и провайдеры

| Тип | Провайдер | Модели (примеры) |
|---|---|---|
| Изображения (9) | laozhang.ai (OpenAI-совместимый) | DALL-E 3, GPT Image 1, Flux Schnell, Flux Dev, Flux Pro, Flux Kontext, Ideogram v2, Stable Image Ultra, Recraft v3 |
| Видео (7) | apimart.ai + laozhang.ai + Seedance | Sora, Veo 2, Kling 2.1, Hailuo, Wan 2.1, CogVideoX, Seedance-1 |

### Архитектура генерации
- **Чат**: `send_message` → Celery → `generate_ai_response` → `generate_with_falai()` → `client.images.generate()` или `generate_video_*()` → polling → `GeneratedImage.create()` → WebSocket → рендер в чат
- **Polling**: 800 мс для изображений, 15 мин (до 1080 итераций) для видео — слепое, без прогресса пользователю
- **Хранение**: `GeneratedImage` model (src/aitext/models.py:741) — поля `image` (FileField), `prompt`, `media_type` (image/video), `message` (FK, обязательный)
- **Галерея**: `/account/files/` — 3 таба (Все/Изображения/Видео), infinite scroll, preview modal (frontend/app/account/files/page.tsx)
- **UI настроек**: `MediaSettingsPanel` — динамическая форма из `ui_settings.sections` в config-JSON модели
- **Валидация параметров**: `validate_and_merge_settings()` (fal_utils.py:28) — уже парсит `seed`, `negative_prompt`, `image_size`, `image_url`, `num_images`

### Критические пробелы в текущей реализации
1. **`_build_image_params` (fal_utils.py:411)** форвардит только `model/prompt/size/quality/style/n` — `seed`, `negative_prompt`, `image_url` уходят в `validate_and_merge_settings` но **не достигают API-провайдера**
2. **Img2img и img2video** — только в Telegram; в веб-чате недоступны
3. **Параметры генерации не сохраняются** в БД → нет воспроизводимости, нет «повторить», нет истории с рецептом
4. **Видео без прогресса** — пользователь видит спиннер 15 минут

---

## Анализ: что реально нужно пользователю в 2025–2026

Лидеры рынка отличаются не количеством моделей (у нас их уже 9 + 7), а **рабочим процессом вокруг генерации**:

| Возможность | Кто задаёт стандарт | У нас |
|---|---|---|
| Редактирование изображения (img2img, inpaint, outpaint) | Firefly, Midjourney Editor, Flux Kontext | ❌ (только в Telegram) |
| Оживление фото (image-to-video) | Runway, Pika, Kling, Veo | ❌ (только в Telegram) |
| Воспроизводимость (seed) + история с параметрами | Midjourney, все pro-сервисы | ❌ |
| Прогресс-бар долгой генерации видео | Runway, Kling | ❌ (слепой polling 15 мин) |
| Апскейл / варианты / референс-стиль | Midjourney (U/V/cref), Magnific | ❌ |
| Улучшение промта AI | Firefly, Leonardo | ❌ |
| Сравнение моделей на одном промте | арены, FAL | частично (`/compare`, Arena — только текст) |
| Публичная галерея / шеринг | Midjourney, Leonardo | ❌ |

### Главный архитектурный долг (блокирует половину списка)

`GeneratedImage` (src/aitext/models.py:741) — это **узкое место всей фичи**:
- жёстко привязан к `Message` (FK обязателен) → нельзя сохранить генерацию из API или из отдельной «Студии»;
- **не хранит параметры генерации** — ни seed, ни модель, ни настройки, ни негативный промт → невозможны воспроизводимость, история, «повторить», варианты;
- нет связи «родитель → потомок» → невозможны lineage редактирования (img2img/варианты/апскейл);
- называется `GeneratedImage`, но хранит и видео (флаг пользователя).

**Вывод**: рефакторинг модели — фундамент. Но мы не делаем его «скучным Sprint 0»: он въезжает в Sprint 1 на спине WOW-фичи (img2img-редактор), которая физически требует lineage и params.

### Что уже частично есть (но не до конца)

`validate_and_merge_settings` (src/aitext/fal_utils.py:28) **уже парсит** `seed`, `negative_prompt`, `image_url` — они попадают в `final_args`. Но `_build_image_params` (fal_utils.py:411) **эти ключи не читает** и до API они не доходят. Sprint 1 добавляет `image_url`/edit-пайплайн, Sprint 4 добирает `seed`/`negative_prompt`/`num_images` — это не «с нуля», но и не «бесплатно»: нужно дописать форвардинг в `_build_image_params` и добавить поля в config JSON моделей.

### Что уже есть как плумбинг (переиспользуем)

Telegram уже умеет img2img и img2video (src/telegram_bot/handlers/img2img_cmd.py, img2video_cmd.py). Паттерн: фото → storage → `image_url` кладётся в `Message.settings['image_url']` → `generate_ai_response.delay()` → `user_settings = user_msg.settings` (src/aitext/tasks.py:680) → `generate_with_falai(..., user_settings)`.

**НО**: `_build_image_params` (fal_utils.py:411) форвардит только `model/prompt/size/quality/style/n` и зовёт `client.images.generate()`. Он **не передаёт `image_url`** и не использует `client.images.edit()`. Значит для веба нужно: (1) UI загрузки исходника, (2) проброс `image_url` в провайдера через корректный edit-эндпоинт. Это ограниченная, понятная задача — не «с нуля».

---

## Sprint 1 — Медиа-движок 2.0 + Image-to-Image
**Цель**: дать пользователю редактировать изображения по референсу (как Flux Kontext / Firefly) и одновременно перестроить хранилище под все будущие фичи.

### Backend
- **Рефакторинг модели**: `GeneratedImage` → `MediaAsset` в `src/aitext/models.py`. Добавить поля: `params` (JSONField — финальные args генерации), `seed` (BigInteger, null), `model_name` (Char), `provider` (Char), `media_kind` (image/video), `parent = FK('self', null)` (lineage редактирования), `message` сделать **nullable** (FK SET_NULL), `source` (chat/api/studio). Сохранить `related_name='generated_images'` алиасом или обновить все обращения. Data-миграция переносит существующие строки.
- **Edit-пайплайн**: новая `generate_image_edit(network, user_msg, message, user_settings)` в `src/aitext/fal_utils.py` — читает `image_url` из `user_settings`, скачивает исходник, вызывает `client.images.edit()` (или provider-специфичный edit-эндпоинт для Flux Kontext / GPT Image). Роутинг в `generate_with_falai`: если в `user_settings`/config есть `image_url` → ветка edit, иначе текущая `generate`.
- **Lineage**: при сохранении edit-результата проставлять `parent` = исходный `MediaAsset` (если редактируем существующую генерацию) и записывать `params`/`seed`/`model_name`.

### Frontend
- В чат-композере (`frontend/app/chat/[chatId]/page.tsx` + `frontend/components/chat/AttachmentPreview.tsx`): для image-моделей разрешить прикрепить исходное изображение → положить его URL в `settings.image_url` отправляемого сообщения.
- Кнопка **«Редактировать»** на любом сгенерированном изображении в чате и в `/account/files/` → открывает редактор с предзаполненным `image_url` исходника.

### Результат для пользователя
Можно загрузить своё фото (или взять уже сгенерированное) и сказать «сделай в стиле акварели / поменяй фон / добавь объект» — получить отредактированный вариант. История знает, из чего что сделано.

### Архитектурные изменения
`GeneratedImage → MediaAsset` (rename + params/seed/model/parent/nullable message). **Риск 1**: data-миграция продакшн-таблицы — пишем reversible-миграцию, прогон на копии БД, бэкап перед `deploy.sh`.

**Риск 2 (внешний, требует проверки до старта)**: edit-пайплайн предполагает, что laozhang.ai / apimart.ai поддерживают `client.images.edit()` и `image_url` passthrough для Flux Kontext / GPT Image 1. OpenAI-совместимый интерфейс исторически поддерживает `/images/edits` только для части моделей. Необходимо протестировать до написания кода: `curl -X POST .../v1/images/edits -F image=... -F prompt=...` по обоим провайдерам. Если edit не поддерживается — использовать provider-специфичный REST-эндпоинт (Flux Kontext имеет свой `/kontext/edit`).

---

## Sprint 2 — Inpaint / Outpaint (редактор с маской)
**Цель**: убийца Adobe Firefly — точечное редактирование области изображения и расширение холста.

### Backend
- Поддержка маски в `generate_image_edit`: принимать `mask_url` из `user_settings`, передавать в `client.images.edit(image=..., mask=...)`. Для outpaint — генерировать расширенный холст + прозрачную маску по краям на стороне сервера (PIL уже в зависимостях, см. models.py:728).
- Расширить `validate_and_merge_settings` веткой `mask_url` (по аналогии с существующей `image_url`).
- Endpoint загрузки маски (переиспользовать существующий upload-флоу attachments).

### Frontend
- Новый компонент `frontend/components/chat/MaskEditor.tsx` — canvas поверх изображения: кисть для закраски области (inpaint) + ручки расширения холста (outpaint). Экспорт маски в PNG → upload → `settings.mask_url`.
- Пресеты соотношений для outpaint (16:9, 1:1, 9:16).

### Результат для пользователя
Закрасил кистью лишний объект и написал «убрать» — объект исчез. Или расширил фото в широкоформатное, AI дорисовал края. Полноценный редактор уровня Firefly.

### Архитектурные изменения
Нет (едет на модели и edit-пайплайне Sprint 1).

---

## Sprint 3 — Image-to-Video (веб) + реальный прогресс
**Цель**: оживление фото в видео (Runway/Kling/Pika-класс) и устранение «слепого» 15-минутного ожидания.

### Backend
- Веб img2video поверх готового плумбинга: видео-модели уже читают `image_url` из `user_settings` через `generate_with_falai` → `generate_video_apimart`/`_laozhang`/`_seedance`. Дописать проброс `image_url` в `body` этих функций (fal_utils.py:742, 623, 500) — сейчас он не добавляется в payload видео-провайдеров.
- **Статус-строка прогресса**: добавить в `MediaAsset` (или отдельную `GenerationJob`) поля `status` (pending/running/done/error) и `progress` (0–100). Polling-циклы в `generate_video_*` обновляют `progress` из ответа провайдера (поле `progress` уже приходит, логируется в fal_utils.py:543, 820).
- **SSE-стрим прогресса**: переиспользовать SSE-инфраструктуру из Studio (log-stream) → endpoint `GET /api/v1/generations/<id>/stream`.

### Frontend
- Кнопка **«Оживить»** на изображениях (в чате и `/account/files/`) → выбор видео-модели + промт движения камеры.
- Компонент `GenerationProgress.tsx` — настоящий прогресс-бар, подписан на SSE; заменяет polling 800 мс для видео.

### Результат для пользователя
Из любой картинки — видео с движением. Видно реальный прогресс (47%… 80%…), а не «крутилку» на 15 минут.

### Архитектурные изменения
Введение `status`/`progress` + SSE-канал прогресса. Снимает главную хрупкость: блокирующий Celery-поллинг (60×15с) перестаёт быть «чёрным ящиком».

---

## Sprint 4 — Creative Controls + настоящая История/Галерея
**Цель**: pro-контроль над генерацией и галерея, в которой видно ВСЕ параметры (как у Midjourney).

### Backend
- **Дописать форвардинг в `_build_image_params` (fal_utils.py:411)**: добавить ключи `seed`, `negative_prompt`, `num_images` из `final_args` в итоговый `params` — то же, что делаем для `image_url` в Sprint 1. Без этого параметры парсятся, но до API-провайдера не доходят.
- Добавить поля `seed`, `negative_prompt`, `num_images`, `aspect_ratio` в `ui_settings` существующих image-моделей — через команду `src/aitext/management/commands/add_laozhang_models.py`.
- `UserFilesView` (src/api/views/files.py:13) — отдавать `params`, `seed`, `model_name`, `parent_id` в ответе; фильтры по модели и дате; группировка lineage.
- Эндпоинт **«Повторить»**: `POST /api/v1/generations/<id>/rerun` — создаёт новую генерацию с теми же `params`/`seed` (или новым seed для вариации).

### Frontend
- `MediaSettingsPanel.tsx` — секции seed (с кнопкой 🎲 random / 🔒 lock), negative prompt, batch (1–4), пресеты соотношений сторон.
- Переписать `frontend/app/account/files/page.tsx`: карточка генерации показывает промт, модель, seed, параметры; кнопки **«Повторить»**, **«Вариации»**, **«Скопировать seed»**, **«Редактировать»**; визуализация дерева lineage.
- Batch-генерация: сетка 2×2 результатов в одном сообщении.

### Результат для пользователя
Зафиксировал seed → воспроизводимый результат. Сгенерировал 4 варианта разом. В галерее видно «рецепт» каждой картинки и можно повторить в один клик.

### Архитектурные изменения
Нет — всё едет на `params`/`seed`/`parent` из Sprint 1 (поэтому эти поля заложены сразу).

---

## Sprint 5 — AI Prompt Enhancer + Multi-Model Compare
**Цель**: снизить порог входа (хорошие картинки без навыка промптинга) и показать силу мульти-модельности.

### Backend
- `enhance_image_prompt(prompt, model_name)` в `src/aitext/fal_utils.py` (или `prompt_utils.py`) — берёт короткий промт, через текстовую модель (DeepSeek/Claude, переиспользуем `translate_to_english`-паттерн, fal_utils видит LAOZHANG) возвращает обогащённый англоязычный промт со стилем/освещением/деталями. Endpoint `POST /api/v1/images/enhance-prompt`.
- **Compare для медиа**: расширить существующий `/compare` (frontend/app/compare/page.tsx) на image-модели — один промт уходит в N image-моделей параллельно (Celery group), результаты в сетку. Привязать к Elo Arena (ModelMatch, models.py:1095) для image-моделей.

### Frontend
- Кнопка **«✨ Улучшить промт»** рядом с полем ввода для image/video-моделей: показывает diff (было/стало), можно принять/откатить.
- Страница `frontend/app/compare/page.tsx`: режим изображений — сравнение 2–4 моделей бок о бок, голосование (кормит Arena).

### Результат для пользователя
Пишешь «кот в космосе» → AI разворачивает в детальный промт → отличная картинка. Видишь, как один промт выглядит у DALL-E 3 vs Flux vs GPT Image, и голосуешь.

### Архитектурные изменения
Нет (Celery group + существующая Arena).

---

## Sprint 6 — Upscale + Variations + Style Reference
**Цель**: финишная обработка и консистентность — то, за что платят в Midjourney/Magnific.

### Backend
- **Upscale**: `generate_upscale(asset, factor)` в fal_utils — апскейл-модель/эндпоинт провайдера (2x/4x). Результат — новый `MediaAsset` c `parent` = оригинал, `params={'op':'upscale','factor':4}`.
- **Variations**: повтор генерации с тем же seed + лёгкая вариация (или Midjourney-style V1–V4 из batch).
- **Style / Character reference**: проброс `style_image_url` (референс стиля) и для img2img — сохранение «персонажа» между генерациями. Ветка в `validate_and_merge_settings` + `generate_image_edit`.

### Frontend
- На карточке результата: кнопки **«Upscale 2x/4x»**, **«Варианты»**.
- В композере: слот «Референс стиля» (отдельно от исходника для edit).

### Результат для пользователя
Понравившуюся картинку — в 4K одним кликом. Генерация серии в едином стиле/с одним персонажем. Полный цикл: задумка → генерация → редактирование → апскейл.

### Архитектурные изменения
Нет (lineage `parent` уже есть).

---

## Sprint 7 — Публичная галерея, шеринг, API-в-галерею, надёжность
**Цель**: рост (виральность + SEO) и продакшн-устойчивость долгих генераций.

### Backend
- **API сохраняет в галерею**: `POST /api/v1/images/generations` (dev-API) создаёт `MediaAsset` с `source='api'`, `message=null` (теперь возможно благодаря nullable FK) → юзер видит API-генерации в `/account/files/`. Закрывает явный пробел из ТЗ.
- **Публичная галерея/шеринг**: поля `is_public`, `share_slug` в `MediaAsset` (паттерн `Project.public_slug`, models.py:238). Публичная страница, лента «Discover», модерация (ModerationLog, models.py:1133 — уже есть).
- **Надёжность видео**: webhooks провайдеров вместо/в дополнение к 15-мин поллингу; идемпотентность по `task_id` (уже частично, fal_utils.py:798); ретраи скачивания; авто-восстановление job при рестарте Celery.

### Frontend
- `frontend/app/account/files/page.tsx`: переключатель Public/Private, кнопка «Поделиться» (ссылка + OG-превью).
- Публичные страницы: `frontend/app/gallery/[slug]/page.tsx` (одна генерация, SEO/OG) и `frontend/app/discover/page.tsx` (лента).

### Результат для пользователя
Генерации из API видны в кабинете. Любую работу можно опубликовать ссылкой с красивым превью. Публичная лента вдохновляет и приводит SEO-трафик. Долгие видео не теряются при сбоях.

### Архитектурные изменения
`is_public`/`share_slug` + webhook-приём результатов видео + идемпотентность/восстановление job. Снимает остаток хрупкости долгого медиа-пайплайна.

---

## Сводная таблица приоритетов

| Sprint | Фича | WOW | Конкур. разрыв закрывает | Стоимость | Статус |
|---|---|---|---|---|---|
| 1 | Img2Img + MediaAsset | 🔥🔥🔥 | Firefly / Flux Kontext | High (миграция) | ✅ Выполнено |
| 2 | Inpaint / Outpaint | 🔥🔥🔥 | Firefly | Medium | ✅ Выполнено |
| 3 | Img2Video + прогресс | 🔥🔥🔥 | Runway / Kling / Pika | Medium | ✅ Выполнено |
| 4 | Controls + История | 🔥🔥 | Midjourney | Low-Medium (форвардинг + config) | ✅ Выполнено |
| 5 | Enhancer + Compare | 🔥🔥 | Firefly / Leonardo | Low | ✅ Выполнено |
| 6 | Upscale + Variations + Ref | 🔥🔥 | Midjourney / Magnific | Medium | ✅ Выполнено (см. примечание) |
| 7 | Галерея + API + надёжность | 🔥 | рост / SEO / SLA | Medium | ✅ Выполнено |

**Принцип очередности**: сначала закрываем самые заметные разрывы против лидеров (редактирование и видео из фото), причём первый же WOW-спринт «затаскивает» неизбежный рефакторинг модели — поэтому дешёвые фичи (controls, история, варианты) в спринтах 4 и 6 почти не требуют нового бэкенда.

---

## Статус выполнения: ВСЕ 7 СПРИНТОВ ЗАВЕРШЕНЫ

Реализация завершена 2026-06-28. Ниже — исправления багов, найденных после деплоя в ходе аудита.

### Исправления после деплоя (commit 3f03a67, 2026-06-28)

1. **img2img не работал** — OpenAI SDK поднимал `TypeError`, потому что параметры `seed`, `negative_prompt`, `image_url` передавались как прямые аргументы функции, хотя SDK их не принимает. Все нестандартные параметры перенесены в `extra_body`. Подтверждено живыми API-тестами.
2. **Upscale-модели `clarity-upscaler` и `aura-sr` не найдены** — эти имена взяты с fal.ai (предыдущий провайдер). В laozhang.ai и apimart.ai их нет. Добавлен fallback на `flux-kontext-pro` (подробнее ниже).
3. **API-генерации не отображались в кабинете** — фильтр в `/account/files/` не находил генерации, созданные через API, у которых `message=null`. Добавлена FK-связь `user` на `GeneratedImage` (миграция 0042), фильтр обновлён.

---

## Что теперь умеет пользователь — простым языком

### Редактирование изображений (img2img)
Загрузил своё фото или взял готовую генерацию — и попросил «поменяй фон на закат» или «перекрась куртку в синий». Модель Flux Kontext понимает правку на русском языке и меняет именно то, что указано, сохраняя остальное нетронутым. Работает прямо в чате.

### Закраска области (inpaint) и расширение фото (outpaint)
Кистью закрасил лишний объект на фото — AI убрал его и дорисовал фон. Или расширил портрет до широкоформатного — AI достроил края. Инструмент уровня Adobe Firefly, без Photoshop.

### Оживление фото в видео (img2video)
Любую картинку можно «оживить» — загрузил фото, написал «камера медленно приближается» и через несколько минут получил видео. Работает с Kling, Kling 3.0, Seedance, Wan и другими видео-моделями. Виден реальный прогресс (47%… 80%), а не просто крутилка.

### Контроль генерации: seed, негативный промт, количество
Зафиксировал seed — получил воспроизводимый результат, который можно повторить в любой момент. Негативный промт убирает то, что не нужно в кадре. Сразу 2–4 варианта в одном запросе.

### Улучшение промта
Написал короткую идею — нажал «Улучшить» и AI превратил её в детальный профессиональный промт. Видно что изменилось, можно принять или откатить.

### Сравнение моделей
Один промт — несколько моделей параллельно. Видно как один и тот же запрос выглядит у Flux, DALL-E 3, GPT Image 2 и других. Помогает выбрать лучшую модель под конкретную задачу.

### Улучшение качества изображения (enhance)
Кнопка «Улучшить 2x/4x» на любой готовой генерации. **Честное примечание**: настоящих upscale-моделей (Real-ESRGAN, clarity-upscaler) у текущих провайдеров нет — функция работает через Flux Kontext с задачей «улучши детализацию и чёткость». Это визуальное улучшение и переработка деталей, но не математическое масштабирование в 4x пикселей как у Magnific. Результат хороший, но честнее называть это «enhance», а не «upscale».

### Вариации
На любой готовой картинке — кнопка «Варианты». AI создаёт 2–4 похожие генерации с теми же настройками, но разными деталями. Удобно когда «почти то, но хочется немного по-другому».

### Публичная галерея и шеринг
Любую генерацию можно опубликовать по ссылке с красивым превью (OG-карточка в соцсетях). Публичная лента /gallery показывает работы всех пользователей. Генерации через API тоже видны в личном кабинете.

### История с параметрами
В /account/files/ каждая генерация хранит полный «рецепт»: модель, промт, seed, все настройки. Одна кнопка — повторить ту же генерацию или запустить с чистым seed для свежего варианта.
