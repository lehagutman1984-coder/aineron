# PROJECT SPACES — План реализации

Апгрейд фичи **«Проекты»** до полноценных **«Project Spaces»** по аналогии с
Claude.ai Projects, Perplexity Spaces и ChatGPT Projects.

Цель: проект становится не просто папкой для чатов, а рабочим пространством со
своей **базой знаний** (файлы), **инструкциями** (system prompt) и
**подключённым git-репозиторием** (GitHub / Gitea), который AI читает и в который
предлагает коммиты.

---

## СТАТУС РЕАЛИЗАЦИИ (2026-06-23)

| Этап | Статус | Коммиты |
|------|--------|---------|
| Спринт 1 — База знаний (ProjectFile + Celery + инжект в контекст) | **ЗАВЕРШЁН** | `bf16907`, `fix(projects)` |
| Спринт 2 — UX Инструкций (вкладка + счётчик + превью + бейдж в чате) | **ЗАВЕРШЁН** | (`studio-v3`) |
| Спринт 3 — Git-коннектор (GitHub/Gitea PAT + браузер файлов + коммиты) | **ЗАВЕРШЁН** | `b9f8296` |
| **Bug-fix пост-аудит** (6 критических исправлений) | **ЗАВЕРШЁН** | `b9f8296` |
| **Sprint 4.5** — Публичные Spaces (is_public + slug + /s/[slug]/) | **ЗАВЕРШЁН** | `9bc8a51` |
| **Sprint 4.3** — AI-коммиты из чата (FILE-блоки → ProjectCommit) | **ЗАВЕРШЁН** | `9bc8a51` |
| **Sprint 4.1** — Векторный RAG (pgvector + chunks + embeddings) | **ЗАВЕРШЁН** | `6af2601` |
| **Sprint 4.4** — Project Spaces в Telegram-боте | **ЗАВЕРШЁН** | `860fcd8` |
| **Sprint 4.2** — Inbound sync (repo → knowledge base, webhook+manual) | **ЗАВЕРШЁН** | `927db84` |
| **Bug-fix RAG-аудит** (3 исправления, текущая сессия) | **ЗАВЕРШЁН** | (текущая сессия, без хэша) |
| **B4 hotfix** — Rate limit публичных Spaces (Redis throttle 60/min + кэш 60s) | **ЗАВЕРШЁН** | `33046bc` |
| **Sprint 5.7** — RAG Quality (лимиты + надёжность эмбеддингов + умный чанкинг) | **ЗАВЕРШЁН** | `33046bc` |
| **Sprint 5.3** — Knowledge intelligence (FTS поиск + кэш эмбеддингов + метрики) | **ЗАВЕРШЁН** | — |
| **Sprint 5.4** — Sync hardening (версии файлов + polling + auto_sync toggle + sync badge) | **ЗАВЕРШЁН** | — |
| **Sprint 5.1** — Collaborative Spaces (ProjectCollaborator + viewer/editor roles + UI) | **ЗАВЕРШЁН** | `f2f6339` |
| **Sprint 5.2** — Codebase Intelligence (@codebase + PR proposals) | **ЗАВЕРШЁН** | `3c2d091` |
| **Sprint 5.5** — Observability (audit log + public Spaces hardening) | **ЗАВЕРШЁН** | `72e6ab3` |
| **Sprint 5.6** — Telegram upload (файлы в базу знаний из бота) | **ЗАВЕРШЁН** | `f9a5338` |
| **Bug-fix RAG-инъекция** (двойная инъекция + sync error-статус + polling-кнопка + бейдж) | **ЗАВЕРШЁН** | (сессия 2026-06-22) |
| **Phase 6 — RAG Supremacy** (hybrid+rerank+query-expansion+@file/@web+two-level) | **ЗАВЕРШЁН** | `c680c8a`, `1955105` |
| **Phase 7 — Code Workspace** (встроенный редактор CodeMirror + deploy-хук) | **ЗАВЕРШЁН** | `c680c8a`, `1955105` |
| **Post-launch fixes** (chunk_index bug, auto-push bug, rate-limit, lang extensions) | **ЗАВЕРШЁН** | `1955105`, `0620d0c` |
| **Large-file commit fixes** (KB tail-stitch, codebase.py bug, truncation warning) | **ЗАВЕРШЁН** | `d3ecd65`, `643d182`, `43afd10`, `f28fca2` |
| **Phase 8 — EDIT Blocks** (патч-коммиты для файлов >30K символов) | **ЗАПЛАНИРОВАНО** | — |

**ВСЕ ФАЗЫ ЗАВЕРШЕНЫ. Project Spaces реализован полностью.**

### Post-launch fixes (сессия 2026-06-22)

| # | Проблема | Исправление |
|---|----------|-------------|
| 1 | `chunk_index = PositiveIntegerField()` — Postgres CHECK не пропускал `-1`, summary-эмбеддинги Sprint 6.5 падали при INSERT | Изменено на `IntegerField`, миграция `0025` |
| 2 | `embed_chunks` удалял все чанки файла включая `chunk_index=-1` при ресинке | `DELETE WHERE chunk_index >= 0` — summary-строка сохраняется |
| 3 | `time.monotonic()` в rate-limit deploy.py — не работает cross-worker в gunicorn | Заменено на `time.time()` |
| 4 | `CodeEditor` передавал `extensions=[]` — синтаксическая подсветка не работала | Подключены `@codemirror/lang-javascript/html/css` через `getLanguageExtensions()` |
| 5 | CodeEditor авто-пушил коммит сразу после создания, минуя кнопку «Запушить» | Убран `confirmCommit()` из `onCommit` callback — коммит уходит в «Ожидает» |

### Bug-fix RAG-аудит (текущая сессия)

При аудите контекстного пайплайна Project Spaces выявлены и исправлены **3 ошибки**:

| # | Проблема | Исправление |
|---|----------|-------------|
| 1 | `GET /api/v1/projects/` отдавал 500 из-за обращения к несуществующему related_name | `fix(projects): use correct related_name 'knowledge_files'` — приведено к фактическому `related_name='knowledge_files'` (см. `aitext/models.py:271`) |
| 2 | Файлы, синхронизированные из GitHub-репо (`source='repo'`), не попадали в контекст, если их эмбеддинг ещё не завершён (`embed_status != 'done'`) | `fix(projects): include non-embedded repo files in knowledge context` — лексический fallback в `build_project_knowledge_context` теперь подхватывает repo-файлы с `embed_status != 'done'` (`tasks.py:74-76`) |
| 3 | Repo-синхронизированные файлы дублировались: показывались и во вкладке «Файлы», и считались в Git-разделе | `fix(projects): hide repo-synced files from Files tab` — вкладка «Файлы» фильтрует `source='upload'`, repo-файлы видны только в Git-секции |

---

## Что реализовано (подробно)

### Спринт 1 — База знаний проекта

**Backend:**
- `ProjectFile` модель в `src/aitext/models.py` — filename, file\_path, file\_size,
  mime\_type, extracted\_text, char\_count, inject\_mode, enabled, status
- Миграция `src/aitext/migrations/0012_projectfile.py` (аддитивная, не трогает существующих)
- `build_project_knowledge_context(proj, user_msg)` в `src/aitext/tasks.py`:
  - `FULL_INJECT_LIMIT = 50_000` — файлы до 50 КБ инжектятся целиком
  - `AGGREGATE_INJECT_LIMIT = 200_000` — суммарный cap всего знания в контексте
  - Для крупных файлов — лексический отбор по релевантным фрагментам (BM25-подобный)
- `process_project_file` Celery-задача — асинхронное извлечение текста
- **Инжект в оба пути** (исправлено): Celery (`generate_ai_response`) + SSE streaming
  (`StreamMessageView` в `src/api/views/chats.py`)
- Эндпоинты: `v1/projects/<pk>/files/` (GET, POST), `v1/projects/<pk>/files/<id>/` (DELETE, PATCH)

**Frontend:**
- Вкладка «Файлы» в `frontend/app/projects/[id]/page.tsx`
- Drag&drop загрузка, список файлов со статусами (processing/ready/error), тумблер enabled,
  удаление, polling статуса
- Бейдж «База знаний: N файлов» в чате

### Спринт 2 — UX Инструкций

**Frontend (бэкенд уже работал):**
- Отдельная вкладка «Инструкции» с полноразмерным textarea
- Счётчик символов с предупреждением при > 4000
- Markdown-превью инструкции через `react-markdown`
- Индикатор «Инструкции активны» в заголовке чата

### Спринт 3 — Git-коннектор

**Backend:**
- `ProjectConnector` — FK к Project, connector\_type (github/gitea), repo\_url, owner, repo,
  branch, access\_token\_enc (Fernet), unique\_together `(project, owner, repo)`
- `ProjectCommit` — предложенные коммиты с JSON-полем files `[{path, content}]`, статусы
  pending/pushed/rejected/failed
- Миграция `src/aitext/migrations/0013_project_connector_commit.py`
- `src/aitext/crypto.py` — Fernet-шифрование PAT: `encrypt_token`, `decrypt_token`
- `src/config/settings.py` — `PROJECT_CONNECTOR_FERNET_KEY` из env
- `src/aitext/github_client.py` — полный клиент GitHub REST API:
  - `list_tree` — Trees API с `recursive=1`
  - `get_file_content` — Contents API с base64-decode
  - `push_files` — **атомарный** Git Data API (blob→tree→commit→update-ref)
- `src/studio/gitea_client.py` — дополнен для внешних репо:
  - `list_tree`, `get_file_content_ext`, `push_files_ext` — параметр `base_url`
- `src/api/views/connectors.py` — 6 view-классов:
  - `ConnectorListCreateView`, `ConnectorDetailView`
  - `ConnectorReadFilesView`, `ConnectorFileContentView`
  - `CommitListCreateView`, `CommitConfirmView`
- `push_project_commit` Celery-задача — маршрутизация по `connector_type`
- 8 URL-маршрутов в `src/api/urls.py`

**Frontend:**
- Вкладка «Git» (`ConnectorsTab`) в `frontend/app/projects/[id]/page.tsx`
- Форма подключения репо (GitHub/Gitea, URL, PAT)
- Браузер файлов репозитория с TreeNode-компонентом, просмотр содержимого
- Список коммитов с pending-статусом, кнопки «Подтвердить» / «Отклонить»
- Модальное окно создания нового коммита

**Типы в `frontend/lib/api/types.ts`:**
`ProjectConnector`, `RepoTreeItem`, `CommitFile`, `ProjectCommit`

**Методы в `frontend/lib/api/client.ts`:**
`listConnectors`, `createConnector`, `deleteConnector`, `listRepoFiles`,
`getRepoFileContent`, `listCommits`, `createCommit`, `confirmCommit`

---

## Bug-fix пост-аудит (коммит b9f8296)

После имплементации Sprint 3 выявлены и исправлены **6 ошибок**:

| # | Проблема | Исправление |
|---|----------|-------------|
| 1 | `StreamMessageView` не инжектил знания проекта (только Celery-путь) | `build_project_knowledge_context` добавлен в SSE-путь с `message_text` |
| 2 | `build_project_knowledge_context` использовал `message.plain_text` от пустого assistant-сообщения | Переключено на `last_user_msg = chat.messages.filter(role='user').order_by('-created_at').first()` |
| 3 | `gitea_client.py` всегда роутил на внутренний `STUDIO_GITEA_URL` | Добавлен параметр `base_url`; `connectors.py` извлекает его из `connector.repo_url` |
| 4 | `github_client.py push_files` делал N отдельных коммитов (один на файл) | Заменено на атомарный Git Data API: blob→tree→commit→ref |
| 5 | `push_project_commit` помечал commit как `failed` до исчерпания retry | Статус `failed` выставляется только при `self.request.retries >= self.max_retries` |
| 6 | `TreeNode` и `CommitStatusBadge` объявлены внутри `ConnectorsTab` — React ремаунтил дерево на каждый рендер | Вынесены в module-scope компоненты с явными props |

Дополнительно: убран двойной QuerySet в `build_project_knowledge_context` (`.exists()` + цикл заменено на `list(qs)`), добавлены warnings при `truncated` дереве (GitHub ≥100K файлов, Gitea).

---

## Переменные окружения (.env)

```
# Шифрование PAT-токенов коннекторов
PROJECT_CONNECTOR_FERNET_KEY=<сгенерировать: from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())>
```

---

## ЧТО ДАЛЬШЕ: Project Spaces Phase 4

*Разработан с Opus 4.8. Цель: конкурировать с Claude.ai Projects, Cursor, Perplexity Spaces.*

Полный план — раздел `## Phase 4` ниже.

---

## 0. Что уже работает (не переписываем)

*(Исходный раздел оставлен для справки)*

### 0.1. System prompt проекта УЖЕ инжектится в каждый чат

`src/aitext/tasks.py`, строки 297–304 — при генерации ответа system prompt
проекта добавляется первым системным сообщением:

```python
# 1. Project system prompt (если есть)
if chat.project_id:
    try:
        proj = Project.objects.get(id=chat.project_id)
        if proj.system_prompt:
            messages_for_api.append({"role": "system", "content": proj.system_prompt})
    except Exception:
        pass
```

**Вывод:** Фаза «Инструкции» — это на 95% задача UX, а не бэкенда. Бэкенд работает.

### 0.2. Gitea-клиент УЖЕ полностью реализован

`src/studio/gitea_client.py` содержит готовые функции REST API Gitea:

| Функция | Назначение |
|---------|-----------|
| `create_user(username, email, password)` | создать пользователя |
| `create_repo(username, repo, private=True)` | создать репозиторий |
| `put_file(owner, repo, path, content, message, branch='main')` | записать/обновить файл (1 коммит) |
| `put_files_batch(owner, repo, files: dict, message, branch='main')` | пакетный коммит нескольких файлов |
| `get_commits(owner, repo, limit=20)` | список коммитов |
| `get_file_content(owner, repo, path, ref='main')` | прочитать содержимое файла |

### 0.3. Инфраструктура извлечения текста из файлов УЖЕ есть

`src/aitext/file_utils.py` → `extract_text_from_file(file_path, original_filename, file_data=None)`
плюс специализированные парсеры: PDF, DOCX, TXT, Excel, PPTX, архивы.

### 0.4. Persistent Memory работает

В `tasks.py` уже собирается `memory_ctx` (`build_memory_context`), история сжимается
(`get_history_with_compression`, `should_compress`). Контекст проекта (файлы) встаёт
в ту же сборку `messages_for_api` — между system prompt и историей.

---

## Phase 4

*Эволюционный этап: Project Spaces → конкурентоспособный продукт мирового класса.*
*Архитектор: Opus 4.8. Дата плана: 2026-06-21. Ветка: `studio-v3`.*

### Принципы Phase 4 (что НЕ переписываем)

Phase 4 строится строго поверх готового кода Спринтов 1–3. Никакого бэкпортирования.
Точки переиспользования зафиксированы заранее:

| Что переиспользуем | Откуда берём | Где применяем в Phase 4 |
|--------------------|--------------|--------------------------|
| `parse_file_blocks(text)` → `{path: content}` + `incomplete[]` | `src/studio/agents/blocks.py` | Sprint 3: AI предлагает коммиты — парсим FILE-блоки из ответа |
| `ProjectCommit(status='pending')` + `CommitConfirmView` + `push_project_commit` | `aitext/models.py`, `api/views/connectors.py`, `aitext/tasks.py` | Sprint 3: AI-коммит впадает в УЖЕ существующий flow approve→push |
| `build_project_knowledge_context` + `_retrieve_relevant_chunks` (лексика) | `src/aitext/tasks.py` | Sprint 1: векторный RAG встаёт как альтернативный путь за флагом, лексика — fallback |
| `github_client.list_tree / get_file_content / push_files` | `src/aitext/github_client.py` | Sprint 2: inbound-синк читает дерево репо |
| `gitea_client.*_ext(base_url=...)` | `src/studio/gitea_client.py` | Sprint 2: inbound-синк для Gitea |
| `extract_text_from_file(...)` | `src/aitext/file_utils.py` | Sprint 2: текст из файлов репо |
| `ProjectFile` модель (статусы, enabled, extracted_text) | `src/aitext/models.py` | Sprint 1 + 2: файлы репо ложатся в ту же модель через `source`-дискриминатор |
| `EmbeddingsView` + `get_laozhang_client()` | `src/api/views/embeddings.py`, `tasks.py` | Sprint 1: эмбеддинги через тот же laozhang-клиент |
| Конвенция флагов `STUDIO_V4_*` (по умолчанию `0`) | `settings.py` | весь Phase 4: новые фичи под флагами `PROJECT_*` |

**Терминология «двусторонней синхронизации»:** outbound (проект → репо: propose→approve→push)
УЖЕ реализован в Sprint 3. Phase 4 добавляет **inbound** (репо → база знаний проекта).
Вместе они дают двустороннюю синхронизацию.

---

### Дорожная карта Phase 4 (порядок = зависимости)

| Sprint | Тема | Сложность | Срок | Зависит от |
|--------|------|-----------|------|-----------|
| **4.1** | Векторный RAG (pgvector + чанки + эмбеддинги) | **L** | ~1.5–2 нед | — (фундамент) |
| **4.2** | Inbound-синхронизация репо → база знаний | **M** | ~1 нед | 4.1 (чтобы файлы репо сразу эмбеддились) |
| **4.3** | AI предлагает коммиты из чата (FILE-блоки → ProjectCommit) | **M** | ~1 нед | Sprint 3 (готовый push-flow) |
| **4.4** | Project Spaces в Telegram-боте | **M** | ~1 нед | 4.1 (RAG-инжект общий) |
| **4.5** | Публичные Spaces и шаринг (read-only) | **S** | ~3–5 дней | — |

**Честная оценка реализуемости:**
- За **1–2 недели** реально закрыть один из: 4.2, 4.3, 4.4 **или** 4.5 (S/M-спринты — аддитивны, риск низкий).
- **4.1 — на грани месяца** в одиночку: pgvector в проде (привилегии, бэкфилл всех существующих `ProjectFile`), чанкинг, ребиллинг звёзд за эмбеддинги, тесты на пустую/деградировавшую выдачу. Это фундамент — спешка здесь дорого обходится.
- Весь Phase 4 целиком (4.1–4.5) — **реалистично ~5–6 недель** при одном разработчике. 4.1 — половина бюджета.

---

### Sprint 4.1 — Векторный RAG (L)

**Цель:** опциональный семантический поиск по базе знаний вместо/вместе с лексическим.
Включается флагом `PROJECT_VECTOR_RAG=1`. При `=0` — текущая лексика (Sprint 1) без изменений.

#### Ключевое архитектурное решение №1: размерность эмбеддингов и индекс

text-embedding-3-large = **3072 измерения**. Критичное ограничение pgvector:
тип `vector` хранит до 16 000 dim, **но ANN-индексы (hnsw / ivfflat) работают только до 2000 dim**.

**Решение:** НЕ строим ANN-индекс. Каждый запрос RAG всегда фильтруется по `WHERE project_id = X`
(чанков на проект — десятки–сотни, редко тысячи). Точный seq-scan по косинусу внутри одного
проекта дешевле, чем поддержка ANN-индекса, и снимает лимит 2000 dim. Если в будущем понадобится
глобальный поиск — перейдём на `dimensions=1536` (через параметр API) + hnsw.

**Дефолтная модель:** `text-embedding-3-small` (1536 dim) — подтверждённо доступна через laozhang
(`EmbeddingsView` уже её дефолтит). `text-embedding-3-large` — за флагом
`PROJECT_EMBED_MODEL`, как апгрейд (требует проверки прохождения `dimensions` через прокси).
Это снимает риск «модель недоступна через laozhang».

#### Ключевое архитектурное решение №2: где живут чанки

Новая модель `ProjectChunk`, а НЕ поле в `ProjectFile` (файл = много чанков, 1:N).
`ProjectFile` обогащаем дискриминатором источника (нужно и для Sprint 4.2):

```python
# aitext/models.py — добавить в ProjectFile
source = models.CharField(max_length=10, default='upload',
    choices=[('upload', 'Загружен'), ('repo', 'Из репозитория')])
connector = models.ForeignKey(ProjectConnector, null=True, blank=True,
    on_delete=models.SET_NULL, related_name='synced_files')
repo_path = models.CharField(max_length=500, blank=True)  # путь в репо для repo-файлов
embed_status = models.CharField(max_length=12, default='none',
    choices=[('none','Нет'),('pending','В очереди'),('done','Готово'),('error','Ошибка')])

# Новая модель
class ProjectChunk(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='chunks')
    file = models.ForeignKey(ProjectFile, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()
    embedding = VectorField(dimensions=1536)  # pgvector, без ANN-индекса
    token_count = models.PositiveIntegerField(default=0)
    # индекс только по project (B-tree), вектор — exact scan в пределах проекта
```

#### Файлы

| Файл | Действие |
|------|----------|
| `src/requirements.txt` | + `pgvector` (Python-биндинг для Django) |
| `src/aitext/migrations/0014_pgvector_chunks.py` | **новая**: `CREATE EXTENSION IF NOT EXISTS vector` (RunSQL), `ProjectChunk`, новые поля `ProjectFile` |
| `src/aitext/models.py` | `ProjectChunk`, поля `source/connector/repo_path/embed_status` в `ProjectFile` |
| `src/aitext/embeddings.py` | **новый**: `chunk_text(text)` (~500 ток/чанк, overlap 50), `embed_chunks(file)` (батч в laozhang), `vector_search(project, query, top_k)` (косинус, exact) |
| `src/aitext/tasks.py` | `embed_project_file(file_id)` Celery-задача; в `build_project_knowledge_context` — ветка `if settings.PROJECT_VECTOR_RAG` → `vector_search`, иначе лексика; `process_project_file` в конце ставит `embed_project_file.delay()` если флаг |
| `src/aitext/management/commands/backfill_embeddings.py` | **новый**: ребиллинг эмбеддингов всех `ProjectFile(status='ready')` |
| `src/config/settings.py` | `PROJECT_VECTOR_RAG`, `PROJECT_EMBED_MODEL`, `PROJECT_EMBED_DIMS` |

#### Решение №3: миграция расширения и бэкфилл (честно про прод)

- `CREATE EXTENSION vector` требует **superuser** в Postgres. В docker-compose `db` стартует под
  `POSTGRES_USER=neiro_user` — он владелец БД, но не superuser. Нужно либо разово выполнить
  `CREATE EXTENSION` под суперпользователем (init-скрипт контейнера / ручной `psql`), либо
  выдать `neiro_user` право. **В плане: добавить шаг в `deploy.sh` / отдельный init-SQL.** Миграция
  делает `CREATE EXTENSION IF NOT EXISTS` — она пройдёт, если расширение уже создано суперъюзером.
- **Бэкфилл стоит звёзд/токенов.** Включение векторов = переэмбеддить ВСЕ существующие файлы
  (`backfill_embeddings`). На больших аккаунтах это заметный расход → команда логирует прогресс и
  суммарные токены, биллинг — за счёт системы (не пользователя) при бэкфилле. Это часть «месячной»
  оценки 4.1.

#### Биллинг

Эмбеддинги тарифицируются как и любой laozhang-вызов через `charge_for_tokens` (см. `EmbeddingsView`).
При загрузке файла — звёзды пользователя; при ручном бэкфилле — системно. Дешёвая модель
(`-3-small`) выбрана в т.ч. ради стоимости.

#### Компромиссы

- **Без ANN-индекса** — осознанно (лимит 2000 dim + per-project фильтр делает exact-scan достаточным). Минус: на проекте с десятками тысяч чанков латентность вырастет — тогда включаем `dimensions=1536`+hnsw как отдельную доработку.
- **Чанк-overlap 50 токенов** — баланс «не терять контекст на границах» vs дубли.
- Лексика остаётся как fallback при `embed_status != 'done'` или пустой векторной выдаче — деградация плавная, а не обрыв.

---

### Sprint 4.2 — Inbound-синхронизация репо → база знаний (M)

**Цель:** новый коммит в подключённом репо → Project Space автоматически переэмбеддит изменённые
файлы. Завершает «двустороннюю» синхронизацию.

#### Ключевое решение: webhook-primary, polling-fallback

- **Primary — webhook.** При создании коннектора регистрируем webhook в репо через сохранённый PAT
  (`POST /repos/{owner}/{repo}/hooks` у GitHub; аналог у Gitea). Входящий хук **HMAC-верифицируется**
  секретом, который мы генерируем на коннектор (это *inbound* HMAC — отдельная сущность от уже
  существующей *outbound* webhook-инфраструктуры в `api/`, не путать).
- **Fallback — polling.** Celery-beat раз в N минут сверяет `last_synced_sha` коннектора с головой
  ветки (для приватных репо без публичного webhook-эндпоинта, или если регистрация хука не удалась).

Почему так: webhook даёт мгновенность и «как у взрослых» (Cursor/Copilot), polling гарантирует
работу там, где webhook недоступен (self-hosted Gitea за NAT, ограничения PAT).

#### Ключевое решение: защита от петли синхронизации

AI-коммит (Sprint 4.3) → push → webhook от репо → переэмбеддинг → НЕ должен заново что-то триггерить.
Гард: `ProjectConnector.last_synced_sha`. Входящий sync **пропускает коммиты, чей SHA = last_synced_sha**,
и коммиты, авторские для платформы (по committer email/имени бота). Проектируем сразу — ретрофит больнее.

#### Файлы

| Файл | Действие |
|------|----------|
| `src/aitext/migrations/0015_connector_sync.py` | **новая**: `last_synced_sha`, `webhook_secret`, `webhook_id`, `sync_enabled`, `auto_sync` на `ProjectConnector` |
| `src/aitext/models.py` | поля синка на `ProjectConnector` |
| `src/aitext/sync.py` | **новый**: `sync_connector(connector)` — diff дерева по SHA, скачивание изменённых текстовых файлов, upsert в `ProjectFile(source='repo', repo_path=...)`, удаление пропавших, постановка `embed_project_file` |
| `src/aitext/tasks.py` | `sync_connector_task(connector_id)` Celery; `poll_connectors()` beat-задача |
| `src/config/celery.py` | расписание `poll_connectors` (напр. каждые 10 мин, только `auto_sync=True`) |
| `src/api/views/connectors.py` | `ConnectorSyncNowView` (ручной триггер), регистрация webhook в `ConnectorListCreateView.create` |
| `src/api/views/webhooks_inbound.py` | **новый**: `RepoWebhookView` (publicly routed, HMAC-verify, → `sync_connector_task.delay`) |
| `src/api/urls.py` | `+ projects/<pk>/connectors/<cid>/sync/`, `+ /webhooks/repo/<cid>/` |
| `src/aitext/github_client.py` / `gitea_client.py` | `create_webhook`, `compare_commits` (или diff через два `list_tree`) |
| `frontend/app/projects/[id]/page.tsx` | в `ConnectorsTab`: тумблер «Авто-синхронизация», бейдж «Синхронизировано: <sha>», кнопка «Синхронизировать сейчас» |
| `frontend/lib/api/client.ts` + `types.ts` | `syncConnector()`, поля синка в `ProjectConnector` |

#### Фильтрация файлов

Синкаем только текст/код по расширению и размеру (cap, напр. 256 КБ/файл), бинарь/`node_modules`/`.git`
игнорируем (re-use логики игнора при необходимости). Извлечение — `extract_text_from_file`.

#### Компромиссы

- **Diff по дереву, не git-clone.** Полный clone репо в песочницу — тяжело и дублирует Studio. Берём дерево через API и тянем только изменённые blob'ы — дёшево, без локального git.
- **Webhook регистрируем best-effort.** Если PAT без прав на хуки — молча падаем на polling, UI показывает «режим: опрос».

---

### Sprint 4.3 — AI предлагает коммиты из чата (M)

**Цель:** в чате проекта с подключённым репо пользователь просит («добавь README», «отрефактори utils»),
AI отвечает текстом + FILE-блоками, система детектит блоки и создаёт `ProjectCommit(status='pending')`.
Дальше — УЖЕ существующий approve→push (Sprint 3). Никакого нового push-кода.

#### Ключевое решение: переиспользуем parser и commit-flow

- Парсинг — `parse_file_blocks` из `studio/agents/blocks.py` (детерминированный, без JSON-escaping).
- Когда у чата `chat.project_id` и у проекта есть коннектор, в системный промпт добавляется инструкция:
  «если просят изменить код — выводи файлы в формате `=== FILE: path ===` … `=== END FILE ===`».
- После генерации ответа (в обоих путях: Celery `generate_ai_response` и SSE `StreamMessageView`)
  пост-обработчик `extract_commit_from_response()` парсит блоки; если есть — создаёт `ProjectCommit`
  с `connector` = дефолтный коннектор проекта, `commit_message` из первой строки/эвристики.
- Фронт показывает «AI предложил коммит (N файлов)» с теми же кнопками Подтвердить/Отклонить.

#### Файлы

| Файл | Действие |
|------|----------|
| `src/aitext/commit_extract.py` | **новый**: `extract_commit_from_response(project, assistant_text)` → создаёт `ProjectCommit` или `None`; импортирует `parse_file_blocks` |
| `src/aitext/tasks.py` | в конце `generate_ai_response`: если `project + connector + флаг` → `extract_commit_from_response`; инжект инструкции о FILE-формате в системный промпт |
| `src/api/views/chats.py` | то же в SSE-пути (`StreamMessageView`) после завершения стрима |
| `src/config/settings.py` | `PROJECT_AI_COMMITS=0` (флаг) |
| `frontend/app/chat/[networkSlug]/...` | карточка «AI предложил коммит» под сообщением ассистента (рендер pending-коммита, привязанного к проекту) |
| `frontend/lib/api/client.ts` | переиспользует `confirmCommit` (готово) |

#### Решение: «понимание структуры репо»

AI отвечает по коду за счёт RAG (Sprint 4.1) над файлами `source='repo'` (Sprint 4.2). Отдельно
в системный промпт добавляем **карту дерева репо** (paths-only, из `list_tree`, обрезанную до ~3 КБ) —
чтобы модель знала, какие файлы существуют, и не плодила дубли. Это дёшево и резко повышает качество
предложений рефакторинга.

#### Компромиссы

- **Только дефолтный коннектор.** Если у проекта несколько репо — берём первый/помеченный. Мульти-репо выбор в чате — позже, не в MVP.
- **Коммит всегда pending.** AI НЕ пушит сам — пользователь подтверждает. Безопасность и контроль важнее автономности (в отличие от Studio-песочницы, тут чужой прод-репозиторий).
- Старый ручной путь создания коммита (модалка Sprint 3) остаётся — это просто второй источник `ProjectCommit`.

---

### Sprint 4.4 — Project Spaces в Telegram-боте (M)

**Цель:** выбор активного Project Space в боте; вопросы AI учитывают знания и инструкции проекта.

#### Ключевое решение: общий RAG-инжект, не дублировать логику

Инжект знаний проекта — это `build_project_knowledge_context` (общая функция). Бот лишь должен
проставить «активный проект» в чат, который он использует, — и инжект отработает сам (RAG из 4.1
тоже общий). Минимум нового кода на стороне бота.

#### Файлы

| Файл | Действие |
|------|----------|
| `src/telegram_bot/migrations/00XX_active_project.py` | **новая**: `active_project` FK на `aitext.Project` в `TelegramUser` |
| `src/telegram_bot/models.py` | `active_project = ForeignKey('aitext.Project', null=True, SET_NULL)` |
| `src/telegram_bot/handlers/projects_cmd.py` | **новый**: `/projects` — список Spaces пользователя (inline-кнопки), выбор активного, «Сбросить»; карточка с числом файлов и активностью инструкций |
| `src/telegram_bot/handlers/chat.py` | при создании/получении рабочего `Chat` — если `tg_user.active_project` → проставить `chat.project = active_project` (тогда системный промпт + знания инжектятся существующим пайплайном) |
| `src/telegram_bot/handlers/menu.py` | пункт меню «Проекты»; индикатор активного Space в шапке/статусе |
| `src/telegram_bot/bot.py` | регистрация роутера `projects_cmd` |
| `frontend/app/tg/...` (Mini App) | опц.: селектор проекта в Mini App (если есть бюджет) |

#### Компромиссы

- **Read+chat в боте, управление файлами — в вебе.** Загрузка PDF и Git-настройка остаются в веб-UI; бот — это «спросить у своего Space». Это сознательное сужение: TG-загрузка файлов в проект — отдельная задача, не блокирует ценность.
- **Активный проект — на `TelegramUser`, не на каждый чат.** Проще ментальная модель: «я сейчас работаю в Space X». Переключение — через `/projects`.

---

### Sprint 4.5 — Публичные Spaces и шаринг (S)

**Цель:** сделать Space публичным read-only и поделиться ссылкой (аналог Perplexity Spaces share).

#### Ключевое решение: токен-ссылка + read-only снапшот

Публичность = поле на `Project` + случайный `public_slug`. Публичная страница отдаёт **read-only**:
название, инструкции (system_prompt), список файлов базы знаний (без скачивания приватных по умолчанию),
и — опционально — публичные чаты. НЕ отдаём токены коннекторов, не даём писать, не запускаем генерацию
от имени владельца.

```python
# aitext/models.py — Project
is_public = models.BooleanField(default=False)
public_slug = models.CharField(max_length=22, blank=True, db_index=True)  # secrets.token_urlsafe
public_show_files = models.BooleanField(default=True)
public_show_chats = models.BooleanField(default=False)
```

#### Файлы

| Файл | Действие |
|------|----------|
| `src/aitext/migrations/00XX_public_space.py` | **новая**: `is_public`, `public_slug`, флаги видимости |
| `src/aitext/models.py` | поля выше + генерация `public_slug` |
| `src/api/views/projects.py` | `ProjectPublicView` (AllowAny, по `public_slug`, только read-only сериализация); экшен «опубликовать/снять» в `ProjectDetailView` |
| `src/api/urls.py` | `+ public/spaces/<slug>/` (без auth) |
| `frontend/app/s/[slug]/page.tsx` | **новая** публичная SSR-страница Space (SEO: title/description из проекта, OG-теги) |
| `frontend/app/projects/[id]/page.tsx` | секция «Доступ»: тумблер «Публичный», копирование ссылки `/s/<slug>`, тумблеры видимости файлов/чатов |
| `frontend/lib/api/client.ts` + `types.ts` | `publishProject`, `getPublicSpace`, поля публичности |

#### Компромиссы

- **Slug, а не sequential id** — нельзя перебрать чужие Spaces.
- **Снятие публичности инвалидирует ссылку** (меняем slug или `is_public=False` → 404). Версионирование снапшотов — избыточно для MVP.
- **По умолчанию файлы — только список, без контента** приватных загрузок (защита от утечки PDF). `public_show_files` управляет показом списка; полная отдача контента — отдельный явный опт-ин позже.

---

### Сводка новых флагов окружения (Phase 4)

```
# Векторный RAG (Sprint 4.1) — по умолчанию выключен, лексика остаётся
PROJECT_VECTOR_RAG=0
PROJECT_EMBED_MODEL=text-embedding-3-small   # large=3072 как апгрейд (no ANN index)
PROJECT_EMBED_DIMS=1536

# AI-коммиты из чата (Sprint 4.3)
PROJECT_AI_COMMITS=0
```

### Порядок выкатки и риски

1. **4.1 первым** — фундамент знаний (и upload, и repo идут через один RAG). Главный технический риск — pgvector в проде (привилегии + бэкфилл). Закладываем на это половину бюджета Phase 4.
2. **4.2** сразу за 4.1 — repo-файлы должны эмбеддиться тем же путём.
3. **4.3 и 4.4 параллелизуемы** — независимы, оба опираются на готовый RAG/commit-flow.
4. **4.5** — самостоятельный S, можно вставить в любой момент как «быстрая победа» для маркетинга.

**Главные грабли, заложенные в дизайн заранее:** лимит 2000 dim у ANN-индексов pgvector (решено exact-scan per-project), привилегии `CREATE EXTENSION` (решено deploy-шагом), петля синхронизации AI-коммит↔webhook (решено `last_synced_sha` + фильтр по автору), путаница inbound/outbound HMAC (решено отдельной сущностью `webhook_secret` на коннекторе).

---

# Phase 5 — «Intelligent Workspaces»

*Архитектор: Opus 4.8. Дата плана: 2026-06-22. Цель: вывести Project Spaces из паритета*
*с Claude.ai Projects / ChatGPT Projects / Perplexity Spaces в режим **превосходства** на двух осях,*
*где у нас уже есть структурное преимущество: **командная работа** (паритет) и **git/codebase-*
*интеллект** (моат — ни один потребительский конкурент не пишет в чужой git-репозиторий).*

## Тезис фазы

Phase 4 сделала Space «умной папкой со знаниями». Phase 5 делает её **рабочим пространством команды
с агентным интеллектом над знаниями и кодом**. Две трети спринтов закрывают 10 ограничений аудита
(это honesty-долг и прямой сигнал ценности), одна треть — настоящая «интеллектуальность», которую
обещает название фазы и которой у конкурентов на российском рынке нет.

### Карта: спринт → ограничение аудита

| Ограничение аудита | Закрывается в |
|--------------------|---------------|
| #1 Нет совместного доступа (`ProjectCollaborator` не реализован) | **Sprint 5.1** (флагман) |
| #2 Нет поиска по файлам базы знаний | **Sprint 5.3** |
| #4 Нет кэша эмбеддингов (каждый запрос = новый embedding-call) | **Sprint 5.3** |
| #8 Нет метрик использования базы знаний | **Sprint 5.3** + #7 |
| #3 Нет версионирования файлов (overwrites) | **Sprint 5.4** |
| #5 Нет уведомлений о результатах sync | **Sprint 5.4** |
| #6 Нет polling-fallback для синка (был «спроектирован», но НЕ выкачен) | **Sprint 5.4** |
| #7 Нет audit log per-project | **Sprint 5.5** |
| #10 Публичные Spaces: нет кэша, rate-limit, аналитики посещений | **Sprint 5.5** |
| #9 Telegram: нет загрузки файлов в проект из бота | **Sprint 5.6** |
| — (новая ценность, не из аудита) Агентный research + `@codebase` | **Sprint 5.2** (моат) |

> **Замечание о ground truth.** В тексте Phase 4 утверждалось, что polling-fallback для синка был
> «заложен в дизайн». Аудит (#6) показывает, что он **не выкачен**. Здесь, как и с `ProjectCollaborator`
> (упомянут, но не реализован), приоритет у факта аудита, а не у аспирационной прозы плана.

---

## Принципы Phase 5 (что НЕ трогаем)

| НЕ трогаем | Почему |
|------------|--------|
| Сигнатура `build_project_knowledge_context(proj, user_msg)` | Это единая точка инжекта для веба, SSE и бота. Меняем только её *внутренности* (кэш, метрики), не контракт. |
| Flow `ProjectCommit`: propose → `CommitConfirmView` → `push_project_commit` | Sprint 5.2 (PR-предложения) встаёт поверх, не переписывает push. |
| `embeddings.py`: `vector_search` / `embed_chunks` / `chunk_text` | Кэш и `@codebase` — обёртки, не замена. Exact-scan per-project остаётся (см. баг B3). **Исключение:** Sprint 5.7 осознанно ревизует `chunk_text` (умный чанкинг по структуре кода) — это явно объявленное изменение внутренностей, контракт `embed_chunks`/`vector_search` сохраняется. |
| `ProjectChunk` как raw-SQL вектор без ANN-индекса | Осознанный компромисс Phase 4. Phase 5 его НЕ форсирует на hnsw (см. баг B3 — оставляем как явный долг, не как скрытую бомбу). |
| Модель валюты «звёзды» / `charge_for_tokens` | Все новые AI-вызовы (research, кэш-промахи) тарифицируются существующим путём. |
| Флаги `PROJECT_*` = `0/1`, дефолт `0` | Каждая фича Phase 5 — за флагом, прод не ломается. |

## Переиспользование (по образцу таблицы Phase 4)

| Что переиспользуем | Откуда | Где в Phase 5 |
|--------------------|--------|---------------|
| `Webhook` модель + HMAC-подпись (`api/models.py:205`, `:243`) | `src/api/models.py` | Sprint 5.1: уведомления соавторам и о sync — через готовую исходящую webhook-инфру, не новую |
| `crypto.py` Fernet (`encrypt_token`/`decrypt_token`) | `src/aitext/crypto.py` | Sprint 5.1: share-токены приглашений |
| `vector_search(project, query, top_k)` | `src/aitext/embeddings.py:128` | Sprint 5.2 `@codebase`, Sprint 5.3 поиск по файлам |
| `parse_file_blocks` + `extract_commit_from_response` + `ProjectCommit` | `studio/agents/blocks.py`, `aitext/commit_extract.py` | Sprint 5.2: PR-уровневые предложения над тем же commit-flow |
| `github_client.push_files` (атомарный Git Data API) | `src/aitext/github_client.py` | Sprint 5.2: PR = ветка + push + `create_pull` (новый метод поверх готового push) |
| `sync_connector` + `repo_sha` инкрементальность | `src/aitext/sync.py` | Sprint 5.4: polling-fallback переиспользует ту же diff-логику |
| `build_project_knowledge_context` | `src/aitext/tasks.py` | Sprint 5.3: кэш и метрики встраиваются внутрь, контракт не меняется |
| `active_project` FK + `/projects` хендлер | `src/telegram_bot/models.py:40`, `handlers/projects_cmd.py` | Sprint 5.6: загрузка файлов в активный проект из бота |
| SSE-инфра событий (`commit_proposed`, polling статуса) | `src/api/views/chats.py` | Sprint 5.1/5.2: live-присутствие соавторов, события research |
| Конвенция management-команд (`backfill_embeddings`) | `aitext/management/commands/` | Sprint 5.3: `backfill_kb_index` (FTS), Sprint 5.5: ретеншн audit-лога |

---

## Баги/долги для исправления ПЕРЕД Phase 5

Найдены при чтении кода (не выдуманы — со ссылками на строки):

| # | Долг | Где | Действие |
|---|------|-----|----------|
| **B1** | `ProjectCollaborator` упомянут в плане и в `frontend/lib/api/client.ts`, но модели нет. Фронт может слать запросы в несуществующий эндпоинт. | `client.ts`, `aitext/models.py` | Либо реализовать (Sprint 5.1), либо явно загейтить клиентский код за `PROJECT_COLLAB`. Не оставлять «висящий» вызов. |
| **B2** *(minor)* | `Project.save()` не обнуляет `public_slug` при `is_public=False`, поэтому при повторной публикации slug переиспользуется. **Утечки НЕТ**: `ProjectPublicView` фильтрует `is_public=True` (`api/views/projects.py:90`), т.е. снятая с публикации ссылка уже отдаёт 404. Косметика: ротировать slug при каждой публикации, чтобы старая расшаренная ссылка не «оживала» при повторном опубликовании. | `aitext/models.py:234-238` | Низкий приоритет, опционально в Sprint 5.5. НЕ блокирует. |
| **B3** | `ProjectChunk.embedding` — raw-SQL, без Django-поля и без ANN-индекса. Exact cosine seq-scan per-project. На Space с десятками тысяч чанков (repo-sync крупного монорепо) — линейная деградация. | `aitext/models.py:368`, `embeddings.py:128` | НЕ чинить в Phase 5 форсированно — оставить как **явный документированный долг** с порогом-алертом (Sprint 5.5 метрики ловят рост латентности). Решение `dimensions=1536`+hnsw — отдельная задача, когда метрики покажут необходимость. |
| **B4** | Публичный эндпоинт Space (`is_public`) уже в проде **без rate-limit и без кэша** (#10). Любой может перебирать/долбить `/s/<slug>`. | `api/views/projects.py` (`ProjectPublicView`), `frontend/app/s/[slug]/` | Закрыть в Sprint 5.5 (throttle + кэш) — это **живая экспозиция**, а не будущая фича. Поднять приоритет внутри 5.5. |
| **B5** | Эмбеддинг запроса (`vector_search`) считается на **каждый** RAG-вызов — даже на одинаковые вопросы (#4). Лишние токены/звёзды и латентность. | `embeddings.py:128-160` | Кэш query-эмбеддингов (Sprint 5.3). Полу-баг, полу-фича. |

B4 — обязателен до пиара Phase 5 (живая экспозиция публичного эндпоинта без throttle/кэша). B1 решается выбором: реализовать (Sprint 5.1) или загейтить клиентский код. B2 — косметика, низкий приоритет.

---

## Дорожная карта Phase 5 (порядок = ценность × зависимости)

| Sprint | Тема | Сложность | Срок (1 разработчик) | Зависит от | Тип |
|--------|------|-----------|----------------------|-----------|-----|
| **5.1** | Совместные Spaces (`ProjectCollaborator` + роли + presence) | **L** | ~2–2.5 нед | B1, B2 | Паритет |
| **5.2** | Codebase-интеллект: `@codebase` + PR-уровневые предложения | **L** | ~2 нед | Phase 4 RAG + commit-flow | **Моат** |
| **5.3** | Knowledge intelligence: поиск + кэш эмбеддингов + метрики KB | **M** | ~1–1.5 нед | B5 | Хардненинг+ценность |
| **5.4** | Sync hardening: версии файлов + polling-fallback + уведомления | **M** | ~1 нед | #6 (не выкачен) | Хардненинг |
| **5.5** | Observability: per-project audit log + защита публичных Spaces | **M** | ~1 нед | B3, B4 | Хардненинг+безопасность |
| **5.6** | Telegram: загрузка файлов в Space из бота | **S** | ~2–3 дня | `active_project` | Ценность |
| **5.7** | RAG Quality: лимиты + надёжность эмбеддингов + умный чанкинг | **S→M** | ~3–4 дня | Phase 4 RAG | Хардненинг+качество |

**Честная оценка целиком:** ~8–9.5 недель в одиночку. 5.1 и 5.2 — две трети бюджета (это «intelligence» и «collaboration», ради которых фаза существует). 5.3–5.7 — аддитивные, низкорисковые, параллелизуемы между собой. **Sprint 5.7 — самая высокая отдача на единицу времени во всей Phase 5** (Улучшение 1 — 30 минут, ×3–4 видимого контекста), его разумно сделать одним из первых.

---

### Sprint 5.1 — Совместные Spaces (L)

**Что это даёт пользователю:** пригласить коллегу в Space — общая база знаний, инструкции, чаты и git-коннектор; роли viewer/editor; видно, кто онлайн.

**Конкурентный паритет/превосходство:** vs. **Claude Projects** и **Perplexity Spaces** (у обоих коллаборация — наш главный *named* пробел, аудит #1). vs. **ChatGPT Projects** (исторически слабее в шаринге). Превосходство: соавтор получает не только знания, но и **общий git-write-back** (предложить коммит в общий репо проекта) — этого нет ни у кого из потребительских.

**Реализация (файлы):**

| Файл | Действие |
|------|----------|
| `src/aitext/models.py` | **новая** `ProjectCollaborator(project, user, role[viewer/editor], invited_by, accepted_at)`; **новая** `ProjectInvite(project, email, token[Fernet], role, expires_at)` |
| `src/aitext/migrations/00XX_collaborators.py` | новая (аддитивная) |
| `src/aitext/permissions.py` | **новый**: `project_role(user, project)` → `owner/editor/viewer/None`; хелпер `require_project_access(level)` |
| `src/api/views/projects.py` | во ВСЕХ project-вью заменить `project.user == request.user` на `project_role(...)`; экшены `invite`, `accept_invite`, `list_collaborators`, `remove_collaborator`, `change_role` |
| `src/api/views/project_files.py`, `connectors.py`, `chats.py` | проверка доступа через `project_role` (viewer — read-only, editor — пишет файлы/коммиты, только owner — git-PAT и удаление Space) |
| `src/api/urls.py` | `+ projects/<pk>/collaborators/`, `+ projects/invite/accept/<token>/` |
| `src/users/tasks.py` | `send_project_invite_email(invite_id)` (переиспользует email-инфру) |
| `frontend/app/projects/[id]/page.tsx` | вкладка «Команда»: список соавторов, инвайт по email, смена роли, presence-индикатор |
| `frontend/lib/api/client.ts` + `types.ts` | привести в соответствие с реальными эндпоинтами (закрывает B1) |

**Ключевые решения:**
1. **Роль вычисляется, не денормализуется.** `project_role()` — единая функция, owner = `project.user`, остальные из `ProjectCollaborator`. Меняем точки авторизации, а не каждую вью копипастом.
2. **Presence — поверх SSE, без нового веб-сокета.** Лёгкий heartbeat (Redis TTL-ключ `presence:project:<id>:<uid>`), читается тем же SSE-каналом проекта. Не тащим WebSocket-стек.
3. **Инвайт = Fernet-токен в email**, переиспользуем `crypto.py`. Принятие — по ссылке, привязка к `request.user`.

**Компромиссы:**
- **Делаем:** viewer/editor, инвайт по email, presence-индикатор, разделение прав на git-PAT (только owner).
- **НЕ делаем:** real-time co-editing инструкций (как Google Docs) — это OT/CRDT, отдельный месяц. Соавторы редактируют последовательно с optimistic-lock по `updated_at`. Комментарии/треды — отложены.
- **Биллинг звёзд** — на владельце Space (запросы соавторов тратят звёзды owner'а; флаг на будущее: «соавтор платит сам»).

**Флаги:** `PROJECT_COLLAB=0/1`. При `=0` вкладка «Команда» скрыта, авторизация = только владелец (текущее поведение).

---

### Sprint 5.2 — Codebase-интеллект: `@codebase` + PR-предложения (L) — МОАТ

**Что это даёт пользователю:** в чате проекта спросить «как работает auth?» — AI ищет семантически по **всему подключённому репо** и отвечает с цитатами файлов; на «отрефактори X» — предлагает не просто коммит, а **Pull Request** (ветка + diff + описание) в реальный GitHub/Gitea.

**Конкурентный паритет/превосходство:** vs. **Cursor** (`@codebase`, composer) — мы догоняем семантику по репо, но Cursor — это IDE; мы даём то же из **чата, Telegram и веба без установки**. vs. **Claude/ChatGPT/Perplexity/Yandex 300** — **полное превосходство**: ни один не делает write-back в чужой git, тем более PR-уровневый. Это наш единственный по-настоящему защищённый дифференциатор.

**Реализация (файлы):**

| Файл | Действие |
|------|----------|
| `src/aitext/codebase.py` | **новый**: `codebase_search(project, query, top_k)` — `vector_search` с фильтром `file.source='repo'`; `repo_tree_map(project)` (paths-only, ≤3 КБ) для инжекта структуры |
| `src/aitext/tasks.py` | при `@codebase` в сообщении (или авто, если у проекта есть коннектор) — подмешать `codebase_search` + tree-map в системный контекст через `build_project_knowledge_context` |
| `src/aitext/github_client.py` | **+** `create_branch`, `create_pull` (поверх готового атомарного `push_files`) |
| `src/studio/gitea_client.py` | **+** `create_pull_ext(base_url=...)` |
| `src/aitext/models.py` | `ProjectCommit.kind` choice `commit/pull_request`; `pr_url`, `pr_branch` |
| `src/aitext/tasks.py` (`push_project_commit`) | ветвление: `kind='pull_request'` → branch + push + create_pull; `commit` → текущий путь |
| `src/api/views/connectors.py` | в `CommitConfirmView` — выбор «коммит в ветку» vs «открыть PR» |
| `frontend/app/chat/...` | карточка «AI предложил PR (N файлов)» со ссылкой на открытый PR после подтверждения |
| `frontend/app/projects/[id]/page.tsx` | мульти-репо: селектор активного коннектора для предложений |

**Ключевые решения:**
1. **`@codebase` = тот же `vector_search`, фильтр по `source='repo'`.** Никакого нового индекса — Phase 4 уже эмбеддит repo-файлы. Tree-map даёт модели «карту», семантика — содержимое.
2. **PR — это «коммит в новую ветку + create_pull».** Переиспользуем атомарный `push_files`; PR — тонкая обёртка. Безопасность: AI **никогда не мержит**, только открывает PR — человек ревьюит в GitHub/Gitea.
3. **Мульти-репо.** Снимаем компромисс Phase 4.3 «только дефолтный коннектор» — в предложении указывается целевой коннектор.

**Компромиссы:**
- **Делаем:** семантический поиск по репо, tree-map, PR-предложения, мульти-репо выбор.
- **НЕ делаем:** граф зависимостей кода / AST-aware чанкинг (как у Cursor) — чанкинг остаётся текстовым (`chunk_text`). Это «достаточно хорошо» для ответов и рефакторинга; AST — отдельная R&D-задача.
- **НЕ делаем:** автоисполнение/тесты PR в песочнице (это Studio-территория, не смешиваем продукты).

**Флаги:** `PROJECT_CODEBASE=0/1` (семантика по репо), `PROJECT_PR_PROPOSALS=0/1` (PR-режим; при `=0` остаётся прямой commit из Phase 4.3).

---

### Sprint 5.3 — Knowledge intelligence: поиск, кэш, метрики (M)

**Что это даёт пользователю:** мгновенный поиск по файлам базы знаний из UI; быстрее и дешевле повторные вопросы; владелец видит, какие файлы реально используются.

**Конкурентный паритет/превосходство:** vs. **ChatGPT/Claude Projects** — поиск по файлам и прозрачность «что использовал AI» закрывают аудит #2/#8. Превосходство: явные **метрики цитирования** (какой файл сколько раз попал в контекст) — продуктовая прозрачность, которой у конкурентов нет.

**Реализация (файлы):**

| Файл | Действие |
|------|----------|
| `src/aitext/embeddings.py` | кэш query-эмбеддингов в Redis (ключ = sha256(model+text), TTL 24ч) — закрывает B5/#4 |
| `src/aitext/search.py` | **новый**: `search_knowledge(project, query)` — гибрид: Postgres FTS (`SearchVector` по `extracted_text`) + `vector_search`, дедуп по файлу |
| `src/aitext/models.py` | `ProjectFile` — `tsv` (`SearchVectorField`) + GIN-индекс; **новая** `KBUsageStat(file, hits, last_used_at)` (счётчик цитирований) |
| `src/aitext/tasks.py` | в `build_project_knowledge_context` — инкремент `KBUsageStat` по файлам, попавшим в контекст (метрики #8); чтение query-кэша |
| `src/api/views/project_files.py` | `ProjectFileSearchView` (GET `?q=`); поле `usage` в сериализаторе файла |
| `src/aitext/management/commands/backfill_kb_index.py` | **новый**: пересчёт `tsv` для существующих файлов |
| `frontend/app/projects/[id]/page.tsx` | строка поиска во вкладке «Файлы»; бейдж «использован N раз» у файла |

**Ключевые решения:**
1. **Гибридный поиск (FTS + вектор), не «или».** FTS — мгновенный, точный по ключевым словам, работает БЕЗ pgvector; вектор — семантика. Дедуп по файлу. FTS-путь работает даже при `PROJECT_VECTOR_RAG=0`.
2. **Кэш query-эмбеддингов в Redis** (уже в стеке) — не новая инфра. Снимает B5.
3. **Метрики — инкремент в той же транзакции инжекта**, источник правды один (`build_project_knowledge_context`).

**Компромиссы:**
- **Делаем:** гибридный поиск, кэш, счётчик цитирований per-file.
- **НЕ делаем:** полнотекстовый поиск по чанкам с подсветкой (highlight по позиции) — отдаём файл целиком как результат. Подсветка — позже.
- **НЕ делаем:** дашборд аналитики KB — пока только бейдж «использован N раз». Полноценная аналитика — в Sprint 5.5 (audit).

**Флаги:** `PROJECT_FILE_SEARCH=0/1`, `PROJECT_EMBED_CACHE=0/1`, `PROJECT_KB_METRICS=0/1`.

---

### Sprint 5.4 — Sync hardening: версии, polling-fallback, уведомления (M)

**Что это даёт пользователю:** история версий файла (откат), синк работает даже без webhook, уведомление «синхронизировано N файлов / ошибка».

**Конкурентный паритет/превосходство:** vs. **Cursor/Copilot** — надёжность синка как у инженерных инструментов. Закрывает аудит #3/#5/#6. Превосходство для потребительского сегмента: версионирование загруженных знаний — редкость у чат-конкурентов.

**Реализация (файлы):**

| Файл | Действие |
|------|----------|
| `src/aitext/models.py` | **новая** `ProjectFileVersion(file, content_snapshot, repo_sha, created_at)`; на `ProjectConnector` — `auto_sync`, `sync_status`, `last_sync_report` |
| `src/aitext/sync.py` | при upsert (`source='repo'`) — снапшот старого содержимого в `ProjectFileVersion`; формировать `last_sync_report` (added/updated/removed/errors) |
| `src/aitext/tasks.py` | **`poll_connectors()`** beat-задача (закрывает #6 — реально выкатываем): по `auto_sync=True` сверять голову ветки с `last_synced_at`/`repo_sha`, при расхождении `sync_connector_task.delay`; по завершении — уведомление |
| `src/config/celery.py` | расписание `poll_connectors` каждые 10 мин |
| `src/api/views/project_files.py` | `FileVersionListView`, `FileRestoreView` (откат к версии) |
| `frontend/app/projects/[id]/page.tsx` | «История версий» у файла; тост/бейдж результата синка; тумблер «Авто-синхронизация» |
| Уведомления | через готовую `Webhook`-инфру + in-app тост по SSE — не новая система |

**Ключевые решения:**
1. **Polling — это `sync_connector` по расписанию.** Вся diff-логика (`repo_sha`-инкремент) уже есть. Beat лишь сверяет голову ветки и дёргает существующую задачу. Webhook остаётся primary, polling — гарантия для self-hosted Gitea за NAT.
2. **Версии — снапшот контента, не полный git.** `ProjectFileVersion` хранит предыдущий `extracted_text`/`content`. Ретеншн: N последних версий на файл (cap, напр. 10).
3. **Уведомления через существующий `Webhook`**, не новый канал.

**Компромиссы:**
- **Делаем:** версии загруженных и repo-файлов, polling-fallback, отчёт+уведомление о синке.
- **НЕ делаем:** diff-вьювер версий в UI — пока список + «откатить». Визуальный diff — позже.
- **НЕ делаем:** версионирование эмбеддингов (при откате просто переэмбеддиваем) — проще и дешевле.

**Флаги:** `PROJECT_FILE_VERSIONS=0/1`, `PROJECT_SYNC_POLLING=0/1`.

---

### Sprint 5.5 — Observability: per-project audit + защита публичных Spaces (M)

**Что это даёт пользователю (владельцу/команде):** журнал «кто, когда, что спросил, какие файлы использованы»; публичные Spaces защищены от перебора и нагрузки, видна посещаемость.

**Конкурентный паритет/превосходство:** vs. все — **audit log per-project** (особенно с коллаборацией из 5.1) — это enterprise/B2B-функция, которой нет у потребительских конкурентов; усиливает нашу `teams`-историю. Закрывает #7/#10 и **критическую экспозицию B4**.

**Реализация (файлы):**

| Файл | Действие |
|------|----------|
| `src/aitext/models.py` | **новая** `ProjectAuditEntry(project, actor, action, target, files_used[JSON], created_at)`; на `Project` — `public_views` счётчик |
| `src/aitext/tasks.py` | писать audit-запись при генерации ответа в проекте (actor, использованные файлы из `KBUsageStat`-инжекта) |
| `src/api/views/projects.py` | `ProjectAuditView` (owner/editor); **`ProjectPublicView`** — добавить throttle-класс + кэш ответа (закрывает B4); инкремент `public_views` |
| `src/api/throttling.py` | `PublicSpaceThrottle` (по IP, напр. 60/мин) |
| `src/aitext/models.py` (`Project.save`) | **косметика B2** (опц.): ротировать `public_slug` при публикации (не блокирует — утечки нет) |
| `src/aitext/management/commands/prune_audit.py` | **новый**: ретеншн audit-лога (напр. 90 дней) |
| `frontend/app/projects/[id]/page.tsx` | вкладка «Журнал» (audit); счётчик просмотров публичного Space |
| `nginx.conf` / кэш | кэш-заголовки для `/s/<slug>` (CDN-friendly) |

**Ключевые решения:**
1. **Audit пишется в той же точке, что метрики (5.3)** — `build_project_knowledge_context` уже знает использованные файлы. Один источник правды.
2. **Защита публичных Spaces — приоритет внутри спринта** (B4 — живая экспозиция): сначала throttle+кэш, потом аналитика. (B2 — косметика slug, опционально.)
3. **Кэш публичной страницы** — на уровне DRF-ответа + nginx-заголовки; SSR-страница `/s/<slug>` становится дёшево-отдаваемой.

**Компромиссы:**
- **Делаем:** audit per-project, throttle+кэш публичных Spaces (фикс B4), счётчик просмотров; опц. ротация slug (B2).
- **НЕ делаем:** экспорт audit в SIEM / CSV — пока только UI-журнал.
- **НЕ делаем:** гео-аналитику посещений — только агрегат `public_views`.

**Флаги:** `PROJECT_AUDIT_LOG=0/1`, `PROJECT_PUBLIC_HARDENING=1` (включить по умолчанию — это безопасность, а не эксперимент).

---

### Sprint 5.6 — Telegram: загрузка файлов в Space из бота (S)

**Что это даёт пользователю:** переслать боту PDF/документ → он попадает в базу знаний активного Project Space.

**Конкурентный паритет/превосходство:** vs. **Claude/ChatGPT mobile** — у нас Space живёт в мессенджере, который у россиян всегда под рукой; добавить знание «на ходу» — превосходство по доступности. Закрывает #9.

**Реализация (файлы):**

| Файл | Действие |
|------|----------|
| `src/telegram_bot/handlers/files.py` | если `tg_user.active_project` и пришёл документ — спросить «В чат или в базу знаний проекта?»; при выборе — создать `ProjectFile(source='upload')` + `process_project_file.delay` |
| `src/telegram_bot/handlers/projects_cmd.py` | в карточке активного Space — кнопка «Загрузить файл» (инструкция переслать документ) |
| Переиспользование | `extract_text_from_file`, `process_project_file`, `embed_project_file` — всё готово; бот только создаёт запись |

**Ключевые решения:**
1. **Ноль нового backend-кода для обработки** — бот создаёт `ProjectFile`, дальше работает существующий Celery-пайплайн (извлечение + эмбеддинг).
2. **Уважаем лимиты** (20 файлов/проект, размер) — те же проверки, что в вебе.

**Компромиссы:**
- **Делаем:** загрузка документов в активный Space из бота.
- **НЕ делаем:** управление файлами (удаление/переименование) из бота — это веб. Бот = «добавить и спросить».

**Флаги:** `PROJECT_TG_UPLOAD=0/1`.

---

### Sprint 5.7 — RAG Quality: умный чанкинг + надёжность эмбеддингов + расширенные лимиты (S→M)

**Что это даёт пользователю:** AI «видит» в 3–4 раза больше кода и документов проекта без изменения
архитектуры; файлы перестают «молча» выпадать из векторного поиска при сбое эмбеддинга; результаты
поиска по коду становятся осмысленными (функции/классы целиком, а не обрезки посередине строки).

**Конкурентный паритет/превосходство:** vs. **Cursor `@codebase`** — структурный чанкинг по границам
функций/классов приближает качество ретривала к IDE-инструментам, оставаясь в чате/боте/вебе без
установки. vs. **Claude/ChatGPT Projects** — расширенные лимиты + надёжность эмбеддингов закрывают
типовую жалобу «AI не нашёл нужный файл». Это хардненинг существующего RAG, а не новая ось ценности —
но с наивысшей отдачей на единицу времени во всей Phase 5.

> **Замечание о ground truth (важно для Улучшения 2).** Текущий код **не** «падает без retry», как
> можно подумать: задача `embed_project_file` уже объявлена с `max_retries=2, default_retry_delay=60`
> и вызывает `self.retry(countdown=60)` (`tasks.py:1071,1090`). Реальные дефекты другие:
> (а) retry слабый — фиксированные 60 сек × 2 попытки, без exponential backoff;
> (б) `embed_status='error'` выставляется при **первой же** ошибке (`tasks.py:1087-1088`), ещё до
> исчерпания retry, — то есть файл помечается «ошибкой» преждевременно (та же проблема, что закрывал
> bug-fix #5 пост-аудита Sprint 3 — там решено условием `self.request.retries >= self.max_retries`);
> (в) причина ошибки логируется обобщённо. При окончательном провале файл остаётся с `embed_status='error'`
> (не `'none'`) и выпадает из векторного поиска — работает только лексика.

---

#### Улучшение 1 — Расширенные лимиты (30 минут работы, ~80% видимого результата)

Чистая правка констант, без изменения архитектуры. Немедленно даёт в 3–4 раза больше кода/документов
в контексте.

**Важно: в коде ДВА разных места чанкинга с разными единицами измерения — не путать.**

| Что | Файл:строка | Единица | Было | Стало |
|-----|-------------|---------|------|-------|
| `SYNC_MAX_FILES` (лимит repo-файлов на коннектор) | `aitext/sync.py:29` | файлы | `50` | `300` |
| `AGGREGATE_INJECT_LIMIT` (суммарный cap знания в контексте) | `aitext/tasks.py:32` | символы | `200_000` | `400_000` |
| `_retrieve_relevant_chunks(chunk_size=…)` (**лексический** fallback) | `aitext/tasks.py:35,39` | **символы** | `500` | `1500` |
| `_retrieve_relevant_chunks(top_k=…)` (лексика) | `aitext/tasks.py:35,47` | чанки | `6` | `12` |
| `vector_search(top_k=…)` (векторный путь) | `aitext/embeddings.py:128,160` | чанки | `6` | `12` |
| `embeddings.CHUNK_SIZE` (векторный `chunk_text`) | `aitext/embeddings.py:27` | **токены** | `500` | см. ниже |

> **Тонкость про «чанк 500 → 1500 символов».** В ТЗ единица не уточнена, но в коде это два разных
> числа: лексический `_retrieve_relevant_chunks` режет по **символам** (500 → меняем на 1500),
> а векторный `chunk_text` — по **токенам** (`CHUNK_SIZE=500` токенов ≈ ~2000 символов, т.е. он
> УЖЕ крупнее «1500 символов»). Поэтому:
> - **лексический** чанк: `500 → 1500` символов (Улучшение 1, тривиально);
> - **векторный** `CHUNK_SIZE`: НЕ трогаем простым ×3 — фиксированный размер всё равно
>   **отменяется Улучшением 3** (умный чанкинг по структуре). Улучшения 1 и 3 затрагивают один и
>   тот же путь (`embeddings.py:chunk_text`) — это **последовательность, а не независимые правки**:
>   сначала лимиты/top_k (1), затем замена самой стратегии нарезки (3). До выката (3) можно поднять
>   `CHUNK_SIZE` до `750` токенов как промежуточный шаг — но это опционально.

**Эффект:** мгновенно видно в 3–4 раза больше кода без изменения архитектуры. Риск — рост стоимости
инжекта (больше токенов в промте) и латентности exact-scan (больше чанков). Митигация: лимиты — это
**потолки**, реальный объём ограничивается релевантностью; следить за метриками (Sprint 5.3/5.5).

**Файлы Улучшения 1:**

| Файл | Действие |
|------|----------|
| `src/aitext/sync.py` | `SYNC_MAX_FILES = 50` → `300` (строка 29) |
| `src/aitext/tasks.py` | `AGGREGATE_INJECT_LIMIT = 200_000` → `400_000` (строка 32); дефолты `_retrieve_relevant_chunks(chunk_size=1500, top_k=12)` (строка 35) |
| `src/aitext/embeddings.py` | дефолт `vector_search(..., top_k=12)` (строка 128) и параметр top_k в raw-SQL (строка 160) |

---

#### Улучшение 2 — Надёжность эмбеддингов

Цель — чтобы файл не «выпадал» из векторного поиска навсегда из-за транзиентной ошибки laozhang
(rate-limit, таймаут прокси), и чтобы пользователь видел проблему и мог переэмбеддить вручную.

**Задачи (с учётом фактического состояния кода, см. «Замечание о ground truth» выше):**
1. **Exponential backoff.** Поднять `embed_project_file` до `max_retries=3` и считать задержку
   `60/120/300` сек (через `countdown` по `self.request.retries`, а не фиксированный
   `default_retry_delay`).
2. **`embed_status='error'` — только при исчерпании retry.** Сейчас статус ставится при первой
   ошибке. Переписать по образцу bug-fix #5 пост-аудита: `error` выставляется только когда
   `self.request.retries >= self.max_retries`; до этого статус остаётся `pending`.
3. **Точная причина ошибки.** Логировать тип/сообщение исключения (а при провале — сохранять короткую
   причину в новое поле `ProjectFile.embed_error` для показа в UI).
4. **Management-команда `retry_failed_embeddings`.** Переэмбеддит все `ProjectFile(embed_status='error')`.
   > **Переиспользование/перекрытие:** уже существующая `backfill_embeddings` (`management/commands/backfill_embeddings.py`)
   > исключает `embed_status='done'` и потому **уже** переэмбеддивает error-файлы. Чтобы не плодить
   > дубль — реализовать `retry_failed_embeddings` как тонкую обёртку или добавить
   > `backfill_embeddings --status=error` (фильтр только по `error`). Предпочтительно — флаг
   > `--status`, единая команда.
5. **UI статуса эмбеддинга по файлу.** Во вкладке «Файлы» — иконка статуса (Lucide: `Loader2` для
   pending, `AlertCircle` для error) и кнопка «Повторить» у файлов с `embed_status='error'`,
   дёргающая повторный эмбеддинг.

**Файлы Улучшения 2:**

| Файл | Действие |
|------|----------|
| `src/aitext/tasks.py` | `embed_project_file`: `max_retries=3`; backoff `60/120/300`; `embed_status='error'` только при `self.request.retries >= self.max_retries`; логирование причины (строки 1071-1090) |
| `src/aitext/models.py` | **+** поле `ProjectFile.embed_error = models.CharField(max_length=300, blank=True)` (короткая причина для UI) |
| `src/aitext/migrations/00XX_embed_error.py` | **новая** (аддитивная): поле `embed_error` |
| `src/aitext/management/commands/backfill_embeddings.py` | **+** аргумент `--status=error` (фильтр `embed_status='error'`); либо отдельная тонкая команда `retry_failed_embeddings.py` поверх неё |
| `src/api/views/project_files.py` | экшен `POST .../files/<id>/reembed/` — поставить `embed_project_file.delay(id)`; поля `embed_status`/`embed_error` в сериализаторе файла |
| `src/api/urls.py` | `+ projects/<pk>/files/<id>/reembed/` |
| `frontend/app/projects/[id]/page.tsx` | иконка статуса эмбеддинга + кнопка «Повторить» у файла (Lucide `Loader2`/`AlertCircle`) |
| `frontend/lib/api/client.ts` + `types.ts` | `reembedFile(id)`; поля `embed_status`/`embed_error` в типе `ProjectFile` |

---

#### Улучшение 3 — Умный чанкинг по структуре кода (2–3 дня)

**Проблема:** фиксированная нарезка (по токенам/символам) обрывает функции и классы посередине →
семантически бессмысленные чанки, ретривал тянет «огрызки».

**Решение — структурный чанкинг (`smart_chunk`):**
- Для `.py`, `.ts`, `.tsx`, `.js` — разбивать по **границам функций/классов** (regex + AST-lite:
  `def`/`class`, `function`/`const … =>`/`export …`), а не по фиксированному размеру.
- Файлы прочих типов — по **абзацам** (двойной перенос строки `\n\n`).
- **Максимальный размер чанка — 2000 символов.** Если одна функция крупнее — обрезать с overlap
  (сохранить overlap из текущего `CHUNK_OVERLAP`-подхода, чтобы не терять контекст границ).
- Язык определяется по расширению файла (`ProjectFile.filename` / `repo_path`).

**Связь с принципом «НЕ трогаем» (стр. 538):** `embeddings.py:chunk_text` помечен как неизменяемый.
Sprint 5.7 **осознанно ревизует** именно его — это явно объявленное изменение внутренностей.
Контракт `embed_chunks(file)` и `vector_search(project, query, top_k)` сохраняется; меняется только
стратегия нарезки. Чтобы откат был дёшев — ввести `smart_chunk(text, filename)` рядом с `chunk_text`
и переключать через флаг `PROJECT_SMART_CHUNK`; при `=0` остаётся текущий `chunk_text`.

**Результат:** AI получает осмысленные семантические единицы (функция/класс целиком), а не обрезанный
код посередине строки — заметный рост качества ответов по коду и предложений рефакторинга (синергия
со Sprint 5.2 `@codebase`).

**Файлы Улучшения 3:**

| Файл | Действие |
|------|----------|
| `src/aitext/embeddings.py` | **+** `smart_chunk(text, filename)` — диспатч по расширению (код → границы функций/классов; прочее → абзацы; cap 2000 символов + overlap); `embed_chunks` выбирает `smart_chunk` vs `chunk_text` по флагу `PROJECT_SMART_CHUNK` |
| `src/config/settings.py` | `PROJECT_SMART_CHUNK=0` |
| `src/aitext/management/commands/backfill_embeddings.py` | использовать `--force` для переэмбеддинга существующих после включения флага (новая стратегия = новые чанки) |
| (тесты) | юнит-тесты `smart_chunk` на `.py`/`.ts`/`.md`: функция не рвётся; крупная функция режется с overlap; не-код режется по абзацам |

---

#### Дополнительно: Two-level retrieval (будущий апгрейд, НЕ в MVP 5.7)

Опциональная эволюция качества ретривала к Cursor-уровню без Live GitHub API. **Обозначено как
будущее** — за рамками Sprint 5.7, кандидат в отдельный спринт после метрик 5.3/5.5.

- **Уровень 1 — Summary-индекс.** Для каждого файла хранить краткое описание (~200 слов,
  генерируется дешёвой моделью при эмбеддинге). Поиск сначала идёт по summaries → отбираются нужные
  **файлы**.
- **Уровень 2 — Chunk-индекс.** Только по найденным файлам ищутся релевантные чанки.

Это даёт Cursor-уровень качества поиска (сначала «какие файлы», потом «какие фрагменты») без
интеграции с Live GitHub API. Эскиз будущей реализации: поле `ProjectFile.summary` + первичный проход
`vector_search` по summary-эмбеддингам, затем `vector_search` по чанкам в пределах отобранных файлов.
**Не реализуем в 5.7** — сначала собираем метрики реального качества после Улучшений 1–3.

---

#### Ключевые решения Sprint 5.7

1. **Улучшения 1 и 3 — последовательность, не параллель.** Оба трогают `embeddings.py:chunk_text`.
   Сначала лимиты/top_k (1, тривиально, мгновенный эффект), затем замена стратегии нарезки (3). Не
   презентовать как независимые правки.
2. **Все три улучшения — за флагами / аддитивны.** Лимиты — простые константы (можно без флага, но
   легко откатить); `smart_chunk` — за `PROJECT_SMART_CHUNK`; надёжность эмбеддингов — чистое
   усиление без флага (поведение строго лучше).
3. **Честность про текущий код.** Retry уже есть — улучшаем его (backoff + корректный момент
   `error`), а не «добавляем с нуля». См. «Замечание о ground truth».
4. **`retry_failed_embeddings` не дублирует `backfill_embeddings`** — реализуется как `--status=error`
   поверх существующей команды.

#### Компромиссы Sprint 5.7

- **Делаем:** расширенные лимиты, exponential backoff + корректный момент `error` + UI статуса +
  команда повтора, структурный `smart_chunk` за флагом.
- **НЕ делаем (в 5.7):** полноценный AST-парсинг (tree-sitter) — берём «AST-lite» (regex по сигнатурам
  функций/классов), это «достаточно хорошо»; полноценный AST — R&D-задача (совпадает с компромиссом
  Sprint 5.2).
- **НЕ делаем (в 5.7):** Two-level retrieval (summary-индекс) — будущий апгрейд, после метрик.
- **Риск лимитов:** рост токенов промта и латентности exact-scan на крупных проектах — потолки, а не
  целевой объём; мониторим метриками 5.3/5.5 (баг B3 — порог-алерт по латентности).

**Флаги:** `PROJECT_SMART_CHUNK=0/1` (умный чанкинг). Лимиты (Улучшение 1) и надёжность эмбеддингов
(Улучшение 2) — без отдельных флагов (константы / строгое улучшение).

---

## Сводка новых флагов окружения (Phase 5)

```
# Sprint 5.1 — Совместные Spaces
PROJECT_COLLAB=0

# Sprint 5.2 — Codebase-интеллект (моат)
PROJECT_CODEBASE=0          # @codebase: семантика по repo-файлам
PROJECT_PR_PROPOSALS=0      # PR-режим вместо прямого коммита

# Sprint 5.3 — Knowledge intelligence
PROJECT_FILE_SEARCH=0       # гибридный FTS+вектор поиск по KB
PROJECT_EMBED_CACHE=0       # кэш query-эмбеддингов (Redis)
PROJECT_KB_METRICS=0        # счётчик цитирований файлов

# Sprint 5.4 — Sync hardening
PROJECT_FILE_VERSIONS=0     # версионирование файлов + откат
PROJECT_SYNC_POLLING=0      # polling-fallback синка (beat)

# Sprint 5.5 — Observability + безопасность публичных Spaces
PROJECT_AUDIT_LOG=0
PROJECT_PUBLIC_HARDENING=1  # throttle+кэш публичных Spaces — ВКЛ по умолчанию (безопасность)

# Sprint 5.6 — Telegram upload
PROJECT_TG_UPLOAD=0

# Sprint 5.7 — RAG Quality
PROJECT_SMART_CHUNK=0        # умный чанкинг по структуре кода (функции/классы)
# Улучшение 1 (лимиты) и Улучшение 2 (надёжность эмбеддингов) — без флагов:
# константы в sync.py/tasks.py/embeddings.py и строгое усиление retry
```

## Порядок выкатки и риски

1. **Сначала фикс B4 (защита публичных Spaces: throttle+кэш)** — выносим из 5.5 вперёд как hotfix, это живая экспозиция в текущем проде, не ждёт всей фазы. (B2 — косметика slug, не hotfix.)
2. **5.1 (коллаборация) и 5.2 (codebase/PR) — ядро фазы**, две трети бюджета. Параллельно не делаются (оба L, один разработчик) — 5.1 первым (закрывает B1, разблокирует «командные» сценарии для остальных спринтов: audit команды, presence).
3. **5.3 → 5.4 → 5.5** — аддитивная цепочка хардненинга, низкий риск, можно перемежать.
4. **5.6** — S, «быстрая победа», вставляется в любой слот.
5. **5.7 — кандидат на «первым делом» наравне с фиксом B4.** Улучшение 1 (лимиты) — 30 минут с
   эффектом ×3–4 видимого контекста, реальная немедленная ценность для пользователя при минимальном
   риске. Улучшение 2 (надёжность эмбеддингов) — чистое усиление, делается без флага. Улучшение 3
   (умный чанкинг) — 2–3 дня, за флагом, синергия с 5.2. Внутренний порядок: 1 → 2 → 3 (1 и 3 трогают
   один путь `chunk_text`, поэтому строго последовательны).

**Главные риски, заложенные в дизайн заранее:**
- **Авторизация-рефактор (5.1).** Переход `project.user == user` → `project_role()` затрагивает много вью. Митигация: единая `permissions.py`, покрыть тестами owner/editor/viewer/None ДО фронта.
- **PR против чужого прод-репо (5.2).** AI никогда не мержит — только открывает PR; человек ревьюит в GitHub/Gitea. Жёсткое разделение прав на PAT (только owner, из 5.1).
- **B3 (exact-scan вектора) — не чиним, мониторим.** 5.5-метрики ловят рост латентности; hnsw-апгрейд — по данным, а не превентивно.
- **Биллинг звёзд в командах (5.1).** По умолчанию платит owner — простая модель, явно задокументирована; «соавтор платит сам» — флаг на будущее.

---

## Bug-fix RAG-инъекция (сессия 2026-06-22)

После завершения Phase 5 при аудите контекстного пайплайна выявлены и исправлены **4 дефекта**:

| # | Проблема | Исправление |
|---|----------|-------------|
| 1 | `build_project_knowledge_context` инжектил один и тот же файл **дважды**: его подхватывал и лексический/не-эмбеддённый QuerySet (`no_embed_qs`), и общий проход (`all_qs`) | Дедуп по `file_id` между путями — файл попадает в контекст ровно один раз |
| 2 | `sync_connector`: ранние `return` (нет токена, 404 ветки, truncated-дерево) выходили **без** записи статуса — коннектор «молча» оставался в прежнем состоянии | Все ранние выходы теперь сохраняют `sync_status='error'` + `error_detail` с причиной |
| 3 | Кнопка «Синхронизировать» в `ConnectorsTab` запускала задачу, но не показывала результат | Polling 45 с до завершения `sync_connector_task`, затем рендер отчёта (added/updated/removed) |
| 4 | Бейдж коннектора не отражал исход синка | Бейдж: «синк OK · +47 файлов» при успехе / «синк ошибка: token_error» при провале |

---

# Phase 6 — RAG Supremacy

*Архитектор: Opus 4.8. Дата плана: 2026-06-22.*
*Цель: вывести **сам поиск** Project Spaces на уровень **превосходства над Perplexity и Cursor**,*
*а не только паритет по фичам. Phase 5 закрыла коллаборацию и codebase-интеллект; Phase 6 атакует*
*единственную ось, где мы пока **честно хуже** — качество ретривала.*

## Тезис фазы

На вопрос пользователя «наш поиск лучше, чем у Perplexity?» честный ответ — **пока хуже**. У нас один
канал ретривала (exact-scan вектор) + лексический fallback, склеенные «или». У нас **нет**:

- **hybrid search** (мы НЕ объединяем лексику и вектор скорингом — выбираем один путь);
- **reranking** (top-K из vector-search отдаётся как есть, без переоценки релевантности);
- **query expansion** (узкий запрос пользователя ищется буквально, recall на широких вопросах низкий);
- **conversation-aware search** (поиск игнорирует контекст диалога — «а покажи ещё» ищется как есть);
- **adaptive top_k** (для «посмотри биллинг» — 50 релевантных файлов, а `TOP_K=12` их физически не вмещает).

> **Ground truth — что у нас УЖЕ есть (не выдумываем с нуля).**
> - `vector_search(project, query, top_k)` (`embeddings.py:218`) делает exact cosine seq-scan per-project
>   и возвращает **склеенный текст** top_k чанков — НЕ список кандидатов со скором. Для reranking/RRF
>   функцию нужно научить отдавать **кандидатов с дистанцией** (внутреннее изменение, контракт-обёртка
>   `vector_search` для текущих вызовов сохраняется).
> - `search_knowledge(project, query, top_n)` (`search.py:21`) **уже** делает FTS + вектор с дедупом по
>   файлу — это заготовка hybrid, но дедуп там «или/конкатенация», а не RRF-скоринг. Phase 6 заменяет
>   склейку на **Reciprocal Rank Fusion**.
> - `_get_query_embedding(query, model, client)` (`embeddings.py:187`) уже кэширует эмбеддинг запроса в
>   Redis (24 ч, Sprint 5.3). Query expansion и conversation-aware переиспользуют **этот** путь —
>   несколько вариантов запроса = несколько кэшируемых эмбеддингов, не новая инфра.
> - `build_project_knowledge_context(project, user_message_text)` (`tasks.py:71`) — **единая точка
>   инжекта** для веба, SSE и Telegram. Весь Phase 6 меняет её *внутренности*, контракт не трогаем.

**Конкурентная рамка.** Perplexity силён именно retrieval-стеком (multi-query + rerank + свежий web).
Cursor силён two-level codebase-ретривалом. Phase 6 берёт **обе** техники и добавляет то, чего нет ни
у кого из них в одном продукте: **knowledge base + codebase + web в одном ответе** через `@web`.

## Принципы Phase 6 (что НЕ трогаем)

| НЕ трогаем | Почему |
|------------|--------|
| Контракт `build_project_knowledge_context(proj, user_msg)` | Единая точка инжекта (веб/SSE/бот). Меняем только внутренний пайплайн ретривала, не сигнатуру. |
| Exact-scan per-project без ANN (`ProjectChunk`, баг B3) | Phase 6 не форсирует hnsw. Кандидатов на reranking берём тем же seq-scan'ом (top-50 на проект — дёшево). |
| Модель валюты «звёзды» / `charge_for_tokens` | Query expansion (дешёвая LLM) и `@web` (Tavily) тарифицируются существующим путём. |
| Флаги `PROJECT_*` = `0/1`, дефолт `0` | Каждая техника Phase 6 — за отдельным флагом; при всех `=0` поведение = текущий Phase 5. |
| Текущая склейка результата (`'\n...\n'.join`) как формат инжекта | Меняем, ЧТО склеивается (переранжированный top), не сам способ передачи в промт. |

## Переиспользование (по образцу таблиц Phase 4/5)

| Что переиспользуем | Откуда | Где в Phase 6 |
|--------------------|--------|---------------|
| `_get_query_embedding` (+ Redis-кэш 24ч) | `embeddings.py:187` | 6.2 query expansion, 6.4 conversation-aware — каждый вариант запроса эмбеддится этим путём |
| `search_knowledge` (FTS + вектор + дедуп) | `search.py:21` | 6.1: заготовка hybrid; склейку заменяем на RRF |
| `vector_search` (exact cosine scan) | `embeddings.py:218` | 6.1/6.3: расширяем до возврата кандидатов со скором (top-50) |
| `get_laozhang_client()` | `aitext/tasks.py` | 6.2: дешёвая LLM для генерации вариантов запроса |
| `ProjectFile.extracted_text` + лимиты инжекта | `aitext/models.py`, `tasks.py:32` | 6.5 `@file`: подтянуть весь файл; 6.6 two-level: summary-эмбеддинги |
| `ProjectChunk` + `embed_chunks` | `aitext/models.py`, `embeddings.py:120` | 6.6: добавить summary-эмбеддинг файла рядом с чанками |
| Конвенция management-команд (`backfill_embeddings`) | `management/commands/` | 6.6: `backfill_summaries` (summary-индекс) |
| `charge_for_tokens` | `EmbeddingsView` / `tasks.py` | 6.2 (LLM-expansion), 6.7 (`@web` Tavily) — биллинг существующим путём |

---

## Дорожная карта Phase 6 (порядок = отдача × зависимости)

| Sprint | Тема | Сложность | Срок (1 разработчик) | Зависит от | Прирост качества |
|--------|------|-----------|----------------------|-----------|------------------|
| **6.1** | Hybrid Search (BM25/FTS + Vector + **RRF**) + Adaptive top_k + Conversation-aware | **M** | ~1–1.5 нед | Phase 4 RAG, `search_knowledge` | recall ↑, цена $0 |
| **6.2** | Query Expansion (LLM → 3 варианта запроса) | **S** | ~2–3 дня | 6.1 (RRF поверх вариантов) | +30–40% recall на широких вопросах |
| **6.3** | Reranking (Cross-Encoder, CPU, top-50 → top-15) | **M** | ~1 нед | 6.1 (источник кандидатов) | +20–25% precision |
| **6.4** | `@file` + `@web` явный контекст (Tavily) | **M** | ~1–1.5 нед | — / Tavily-ключ | уникальность: KB+code+web |
| **6.5** | Two-Level Retrieval (File → Chunk, summary-индекс) | **L** | ~1.5–2 нед | 6.1, метрики 5.3/5.5 | Cursor-уровень ретривала |

**Честная оценка целиком:** ~5–6.5 недель в одиночку. 6.1+6.2+6.3 — **ядро «обогнать Perplexity»**
(retrieval-стек), ~3 недели, отдача/время максимальна. 6.4 — наш дифференциатор (web в Space). 6.5 —
самый дорогой и самый «Cursor-подобный», делается **последним и по метрикам**, а не превентивно.

> **Важно про порядок 6.1 → 6.2 → 6.3.** Это **конвейер**, не независимые правки: 6.2 порождает N
> вариантов запроса → 6.1 (RRF) сливает их ранги → 6.3 переранжирует объединённый пул. Каждый
> следующий спринт встаёт поверх предыдущего как ещё одна ступень одного ретривал-пайплайна.

---

### Sprint 6.1 — Hybrid Search (RRF) + Adaptive top_k + Conversation-aware (M)

**Что это даёт пользователю:** поиск перестаёт быть «или вектор, или лексика» — оба сигнала
объединяются, точные ключевые слова (имя функции, путь файла) и семантика работают вместе; для широких
вопросов система автоматически расширяет выдачу; «а покажи ещё про это» понимается в контексте диалога.

**Конкурентный паритет/превосходство:** vs. **Perplexity** — RRF-слияние лексики и вектора — это база их
retrieval-качества; мы её получаем при стоимости **$0** (только CPU/БД). vs. **Cursor** — conversation-aware
ретривал в чате.

#### Ключевое решение №1: Reciprocal Rank Fusion, а не взвешенная сумма скоров

Вектор отдаёт косинус-дистанцию, FTS — `SearchRank` (несопоставимые шкалы). Нормировать их в общий
скор хрупко. **RRF** объединяет **ранги**, а не скоры: `score(d) = Σ 1/(k + rank_i(d))`, `k=60`
(каноническая константа). Лексический и векторный списки сливаются по `file_id`+`chunk_index`; шкалы
не важны — важен только порядок. Это и есть техника Perplexity/Elastic, и она тривиальна в коде.

#### Ключевое решение №2: vector_search учится отдавать кандидатов

Сейчас `vector_search` возвращает склеенный текст. Для RRF нужен **ранжированный список** `(file_id,
chunk_index, content, distance)`. Вводим `vector_search_candidates(project, query, top_n=50)` (внутренний),
а текущий `vector_search` становится тонкой обёрткой над ним (`'\n...\n'.join` от top_k) — **контракт
существующих вызовов сохраняется**.

#### Ключевое решение №3: Adaptive top_k — дешёвая эвристика, не LLM

Тип вопроса определяем **локальной эвристикой** (без вызова модели): короткий запрос / наличие
конкретного идентификатора-пути / вопросительное «как/где X» → `top_k=8`; широкие маркеры
(«посмотри/проанализируй/обзор/весь/all/biling» и длина запроса) → `top_k=20`. Дефолт — текущие 12.
Порог и словари — в `settings`. (LLM-классификатор типа вопроса — возможен в 6.2 заодно с expansion,
но MVP-эвристика бесплатна и мгновенна.)

#### Ключевое решение №4: Conversation-aware = конкатенация, не переписывание

Берём последние **3–5 сообщений** чата (только `role='user'` + при наличии — краткие assistant-реплики),
конкатенируем с текущим запросом как **поисковый контекст** (не как новый промт к модели). Эмбеддим
через тот же `_get_query_embedding` (кэш работает). Стоимость — $0 (один лишний эмбеддинг, кэшируемый).
Гард: ограничить суммарную длину контекста (напр. ≤1500 символов), чтобы не «размывать» запрос.

#### Файлы

| Файл | Действие |
|------|----------|
| `src/aitext/embeddings.py` | **+** `vector_search_candidates(project, query, top_n=50)` → `list[dict]` (file_id, chunk_index, content, distance); `vector_search` рефакторится в обёртку над ним |
| `src/aitext/search.py` | **+** `hybrid_search(project, query, top_k)` — RRF над `vector_search_candidates` + FTS-кандидатами (`search_knowledge` как FTS-источник ранга); дедуп и слияние по `file_id`+`chunk_index` |
| `src/aitext/retrieval.py` | **новый**: `adaptive_top_k(query)` (эвристика) + `build_search_query(chat, user_msg)` (conversation-aware конкатенация последних N сообщений) — единая точка «как формируется поисковый запрос и его ширина» |
| `src/aitext/tasks.py` | в `build_project_knowledge_context`: при `PROJECT_HYBRID_SEARCH` → `hybrid_search(... top_k=adaptive_top_k(q))`; запрос строится через `build_search_query` при `PROJECT_CONV_SEARCH` |
| `src/config/settings.py` | `PROJECT_HYBRID_SEARCH`, `PROJECT_RRF_K=60`, `PROJECT_ADAPTIVE_TOPK`, `PROJECT_CONV_SEARCH`, `PROJECT_CONV_WINDOW=4` |

#### Компромиссы

- **Делаем:** RRF-hybrid, adaptive top_k (эвристика), conversation-aware (конкатенация).
- **НЕ делаем:** обучаемые веса слияния / learning-to-rank — RRF без обучения «достаточно хорош» и не требует данных.
- **НЕ делаем:** ANN-индекс под кандидатов — top-50 exact-scan per-project дёшев (баг B3 — порог-алерт из 5.5 ловит деградацию на гигантских монорепо).
- **Риск:** conversation-aware может «утянуть» поиск в сторону на резкой смене темы. Митигация: окно ≤N сообщений + cap длины; флаг для отката.

**Флаги:** `PROJECT_HYBRID_SEARCH=0/1`, `PROJECT_ADAPTIVE_TOPK=0/1`, `PROJECT_CONV_SEARCH=0/1`.

---

### Sprint 6.2 — Query Expansion (S)

**Что это даёт пользователю:** на узкий вопрос («где лимиты?») система сама ищет по 3–4 переформулировкам
(«rate limit», «throttle», «ограничение запросов»), резко поднимая recall на широких/неточных вопросах.

**Конкурентный паритет/превосходство:** vs. **Perplexity** — multi-query expansion — их ключевой приём
recall; мы получаем его за **~$0.00003/сообщение** (дешёвая модель, ~30 токенов на выход).

#### Ключевое решение: дешёвая LLM генерирует варианты, RRF сливает их выдачи

- Перед поиском вызываем дешёвую модель (`gpt-4o-mini`/аналог через `get_laozhang_client`) с
  инструкцией «верни 3 альтернативных формулировки запроса, по одной на строку, без пояснений».
- Каждый вариант (+оригинал) прогоняется через `hybrid_search` (6.1); результаты сливаются **тем же
  RRF** — чанк, всплывший в нескольких вариантах, поднимается естественно.
- Кэш: эмбеддинги вариантов кэшируются через `_get_query_embedding`; саму генерацию вариантов кэшируем
  в Redis по `sha256(query)` (TTL 24ч) — повторный одинаковый вопрос не платит за expansion дважды.

#### Файлы

| Файл | Действие |
|------|----------|
| `src/aitext/retrieval.py` | **+** `expand_query(query) -> list[str]` (LLM → варианты, Redis-кэш по sha256); таймаут/исключение → fallback на `[query]` (деградация плавная) |
| `src/aitext/search.py` | `hybrid_search` принимает `list[str]` запросов (или вызывается по каждому, RRF-слияние пулов) |
| `src/aitext/tasks.py` | в `build_project_knowledge_context`: при `PROJECT_QUERY_EXPANSION` — `expand_query` перед поиском |
| `src/config/settings.py` | `PROJECT_QUERY_EXPANSION`, `PROJECT_EXPAND_MODEL=gpt-4o-mini`, `PROJECT_EXPAND_N=3` |

#### Компромиссы

- **Делаем:** LLM-expansion на 3 варианта + кэш + плавный fallback.
- **НЕ делаем:** HyDE (генерация гипотетического ответа для эмбеддинга) — мощнее, но дороже и медленнее; кандидат на эксперимент после метрик.
- **Риск:** лишняя латентность (один дешёвый LLM-вызов) + микро-стоимость. Митигация: дешёвая модель, кэш, флаг; expansion включается выборочно (хорошо комбинируется с adaptive — расширять только «широкие» запросы).

**Флаги:** `PROJECT_QUERY_EXPANSION=0/1`.

---

### Sprint 6.3 — Reranking (Cross-Encoder, CPU) (M)

**Что это даёт пользователю:** из «похожих» чанков наверх выходят действительно **отвечающие на вопрос**
— precision контекста заметно растёт, AI меньше «промахивается мимо файла».

**Конкурентный паритет/превосходство:** vs. **Perplexity/Cursor** — cross-encoder reranking — это то, что
отделяет «нашлось похожее» от «нашлось нужное». Модель `cross-encoder/ms-marco-MiniLM-L-6-v2` работает
на **CPU бесплатно** (без GPU, без внешнего API).

#### Ключевое решение: retrieve-wide, rerank-narrow

- 6.1 отдаёт **top-50** кандидатов (RRF над лексикой+вектором, по всем вариантам из 6.2).
- Cross-encoder скорит пары `(query, chunk)` и оставляет **top-15** для инжекта.
- Bi-encoder (наш вектор) грубо отбирает дёшево по всему проекту; cross-encoder точно ранжирует только
  50 кандидатов — классический двухступенчатый ретривал.

#### Ключевое решение №2: модель грузится один раз, на CPU, опционально

- `sentence-transformers` + модель кэшируется в памяти воркера (ленивая загрузка при первом запросе).
- Если пакет/модель недоступны (lean-деплой) — `PROJECT_RERANK=0`, пайплайн отдаёт RRF-порядок без
  reranking. Никакой жёсткой зависимости в проде.
- Латентность cross-encoder на 50 коротких чанках на CPU — десятки–сотни мс; приемлемо для чата
  (для стрима — реранкинг до начала генерации). При риске задержки — cap кандидатов (top-30).

#### Файлы

| Файл | Действие |
|------|----------|
| `src/requirements.txt` | **+** `sentence-transformers` (CPU; опц. — отдельный extras, чтобы не утяжелять базовый образ) |
| `src/aitext/rerank.py` | **новый**: ленивый синглтон модели; `rerank(query, candidates, top_k=15)` → переранжированный список; грациозный no-op если модель не загрузилась |
| `src/aitext/tasks.py` | в `build_project_knowledge_context`: при `PROJECT_RERANK` — `rerank(query, hybrid_candidates(top_n=50), top_k=15)` перед склейкой инжекта |
| `src/aitext/search.py` | `hybrid_search` умеет вернуть пул кандидатов (не только финальный top) для передачи в reranker |
| `src/config/settings.py` | `PROJECT_RERANK`, `PROJECT_RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2`, `PROJECT_RERANK_CANDIDATES=50`, `PROJECT_RERANK_TOPK=15` |

#### Компромиссы

- **Делаем:** CPU cross-encoder, retrieve-50/rerank-15, ленивая загрузка, грациозный no-op.
- **НЕ делаем:** API-reranker (Cohere Rerank) — деньги и внешняя зависимость; локальная MiniLM бесплатна и приватна.
- **Риск:** размер образа (модель ~80 МБ) + холодный старт воркера. Митигация: extras-зависимость, ленивая загрузка, флаг; первый запрос «прогревает» модель.

**Флаги:** `PROJECT_RERANK=0/1`.

---

### Sprint 6.4 — `@file` + `@web` явный контекст (M)

**Что это даёт пользователю:** `@file billing/models.py` — система кладёт в контекст **весь** файл
(не чанки); `@web` — добавляет к ответу свежий веб-поиск (Tavily). Ответ может опираться на **базу знаний
+ код проекта + web одновременно** — комбинация, которой нет ни у Perplexity, ни у Cursor, ни у Claude/ChatGPT Projects.

**Конкурентный паритет/превосходство:** `@file` = паритет с Cursor (явный pin контекста). `@web` в Space
= **уникальный дифференциатор** (web поверх приватной KB и git-репо в одном ответе).

#### Ключевое решение №1: `@file` — детерминированный парс + полный файл

- Перед поиском парсим из текста запроса токены `@file <path>` (regex). Для каждого — ищем `ProjectFile`
  по `filename`/`repo_path` (точное, затем suffix-совпадение) и кладём **весь** `extracted_text` в контекст
  (с пометкой пути), вычитая его длину из `AGGREGATE_INJECT_LIMIT`. Если файл крупнее остатка лимита —
  усечь с предупреждением (а не молча выкинуть).
- `@file` **обходит** ретривал для этого файла (он явно затребован) и дополняет, а не заменяет, обычный поиск.

#### Ключевое решение №2: `@web` — Tavily, тарифицируется как laozhang-вызов

- Токен `@web` → вызов Tavily Search API (готовый под RAG провайдер: возвращает чистые сниппеты), top-N
  результатов добавляются в контекст с источниками (URL). Биллинг — через `charge_for_tokens`/системный
  путь, как у прочих внешних вызовов.
- Ключ `TAVILY_API_KEY`; при отсутствии — `@web` молча игнорируется (флаг/ключ-гейт).

#### Файлы

| Файл | Действие |
|------|----------|
| `src/aitext/retrieval.py` | **+** `parse_context_directives(text)` → `{files:[...], web:bool, clean_query:str}` (вырезает `@file/@web` из запроса перед ретривалом) |
| `src/aitext/web_search.py` | **новый**: `web_search(query, max_results=5)` — Tavily-клиент, нормализованные сниппеты + источники; грациозный no-op без ключа |
| `src/aitext/tasks.py` | в `build_project_knowledge_context`: подмешать полные `@file`-файлы и `@web`-результаты к RAG-контексту; учитывать их в лимите инжекта |
| `src/config/settings.py` | `PROJECT_FILE_PIN`, `PROJECT_WEB_SEARCH`, `TAVILY_API_KEY` |
| `frontend/app/chat/...` | автодополнение `@file` (список файлов Space) и подсказка `@web`; рендер источников web под ответом |
| `frontend/lib/api/client.ts` + `types.ts` | (опц.) эндпоинт списка файлов для автокомплита `@file` |

#### Компромиссы

- **Делаем:** `@file` (полный файл по пути), `@web` (Tavily) с источниками, учёт в лимите инжекта.
- **НЕ делаем:** `@folder`/glob и `@url <конкретный URL>` — в MVP только `@file` и общий `@web`; расширение позже.
- **НЕ делаем:** свой веб-краулер — Tavily покрывает RAG-кейс; смена провайдера — за одним адаптером.
- **Риск:** `@file` крупного файла «съедает» бюджет инжекта. Митигация: усечение с явным предупреждением, приоритет явному pin'у над авто-ретривалом.

**Флаги:** `PROJECT_FILE_PIN=0/1`, `PROJECT_WEB_SEARCH=0/1` (+ `TAVILY_API_KEY`).

---

### Sprint 6.5 — Two-Level Retrieval (File → Chunk) (L)

**Что это даёт пользователю:** на широкий вопрос («посмотри биллинг») система сначала находит **нужные
файлы** (по summary-эмбеддингам), затем ищет чанки только внутри них — Cursor-уровень качества, когда
ответ требует обзора 30–50 файлов, а не одного фрагмента.

**Конкурентный паритет/превосходство:** vs. **Cursor** — двухуровневый ретривал (file-level → chunk-level)
— это его архитектура codebase-поиска; мы достигаем её **без Live GitHub API**, на своём индексе.
(Обозначено в Phase 5.7 как «будущий апгрейд» — Phase 6 его реализует, по накопленным метрикам 5.3/5.5.)

#### Ключевое решение: summary-эмбеддинг файла рядом с чанками

- Для каждого `ProjectFile` при индексировании дешёвая модель генерирует краткое описание (~150–200
  слов: назначение + ключевые сущности) → отдельный **summary-эмбеддинг** (поле/строка рядом с чанками).
- **Уровень 1:** запрос → вектор-поиск по summary-эмбеддингам → top-5 релевантных **файлов**.
- **Уровень 2:** `hybrid_search`/`rerank` (6.1/6.3) ограничивается чанками только этих файлов.
- Это снижает «шум» от похожих чанков из нерелевантных файлов и резко улучшает широкие вопросы.

#### Файлы

| Файл | Действие |
|------|----------|
| `src/aitext/models.py` | **+** `ProjectFile.summary` (TextField) + summary-эмбеддинг (отдельная строка `ProjectChunk` с маркером `chunk_index=-1`, либо новое поле) |
| `src/aitext/migrations/00XX_file_summary.py` | **новая** (аддитивная): `summary` |
| `src/aitext/embeddings.py` | **+** `embed_file_summary(file)` (генерация summary дешёвой LLM + эмбеддинг); `file_level_search(project, query, top_files=5)` |
| `src/aitext/search.py` | `hybrid_search(..., restrict_file_ids=[...])` — поиск чанков в пределах отобранных файлов |
| `src/aitext/tasks.py` | при `PROJECT_TWO_LEVEL` — сначала `file_level_search`, затем `hybrid_search(restrict_file_ids=...)`; `embed_project_file` доп. ставит `embed_file_summary` |
| `src/aitext/management/commands/backfill_summaries.py` | **новый**: бэкфилл summary-эмбеддингов для существующих файлов |
| `src/config/settings.py` | `PROJECT_TWO_LEVEL`, `PROJECT_TWO_LEVEL_FILES=5` |

#### Компромиссы

- **Делаем:** summary-индекс файлов, file→chunk поиск, бэкфилл.
- **НЕ делаем:** граф зависимостей / call-graph между файлами — это R&D (совпадает с компромиссом Sprint 5.2); summary «достаточно хорош» для отбора файлов.
- **НЕ делаем форсированно:** включать раньше метрик — это самый дорогой апгрейд; запускаем, когда метрики 5.3/5.5 покажут, что широкие вопросы реально страдают.
- **Стоимость:** один доп. дешёвый LLM-вызов + эмбеддинг на файл при индексировании (умеренно); бэкфилл логирует токены, как `backfill_embeddings`.

**Флаги:** `PROJECT_TWO_LEVEL=0/1`.

---

## Сводка новых флагов окружения (Phase 6)

```
# Sprint 6.1 — Hybrid Search (RRF) + Adaptive top_k + Conversation-aware
PROJECT_HYBRID_SEARCH=0     # RRF-слияние FTS + вектор (вместо «или»)
PROJECT_RRF_K=60            # константа RRF (каноническая)
PROJECT_ADAPTIVE_TOPK=0     # динамический top_k по типу вопроса (8/12/20)
PROJECT_CONV_SEARCH=0       # учитывать последние N сообщений чата в запросе
PROJECT_CONV_WINDOW=4       # размер окна диалога для conversation-aware

# Sprint 6.2 — Query Expansion
PROJECT_QUERY_EXPANSION=0   # LLM генерирует альтернативные формулировки
PROJECT_EXPAND_MODEL=gpt-4o-mini
PROJECT_EXPAND_N=3          # сколько вариантов запроса генерировать

# Sprint 6.3 — Reranking (Cross-Encoder, CPU)
PROJECT_RERANK=0
PROJECT_RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
PROJECT_RERANK_CANDIDATES=50  # сколько кандидатов берём до reranking
PROJECT_RERANK_TOPK=15        # сколько отдаём в инжект после reranking

# Sprint 6.4 — @file / @web явный контекст
PROJECT_FILE_PIN=0          # @file <path> → весь файл в контекст
PROJECT_WEB_SEARCH=0        # @web → веб-поиск (Tavily) в контекст
TAVILY_API_KEY=             # ключ Tavily Search API

# Sprint 6.5 — Two-Level Retrieval (File → Chunk)
PROJECT_TWO_LEVEL=0         # сначала отбор файлов, потом чанки внутри них
PROJECT_TWO_LEVEL_FILES=5   # сколько файлов отбирать на уровне 1
```

## Порядок выкатки и риски

1. **6.1 первым — фундамент retrieval-стека.** RRF-hybrid + adaptive top_k + conversation-aware дают
   прирост recall при стоимости $0 и разблокируют конвейер для 6.2/6.3 (им нужен общий пул кандидатов).
   Главное внутреннее изменение — `vector_search` учится отдавать кандидатов; делаем как обёртку, чтобы
   текущие вызовы не сломались.
2. **6.2 сразу за 6.1** — query expansion = ещё один источник запросов в **тот же** RRF. S-спринт,
   самая высокая отдача на единицу времени для широких вопросов (+30–40% recall, ~$0.00003/сообщение).
3. **6.3 за 6.2** — reranking замыкает конвейер (retrieve-wide → rerank-narrow). Главный
   инфра-риск фазы (размер образа + холодный старт модели) — изолирован extras-зависимостью и флагом.
4. **6.4 параллелизуем** с 6.1–6.3 (независим: явный pin/web, не трогает ретривал-скоринг). `@web` —
   наш дифференциатор, можно выкатить как «громкую» фичу для маркетинга.
5. **6.5 — последним и по метрикам.** Самый дорогой (L) и самый «Cursor-подобный»; включаем, когда
   метрики 5.3/5.5 покажут, что широкие вопросы реально страдают, а не превентивно.

**Главные риски, заложенные в дизайн заранее:**
- **Контракт `vector_search` (6.1).** Меняем поведение функции, которую зовут из нескольких мест.
  Митигация: новый `vector_search_candidates` + старая сигнатура как обёртка; покрыть тестами оба пути.
- **Конвейерная связность 6.1→6.2→6.3.** Это одна труба ретривала; презентовать и тестировать как
  последовательность ступеней, не как независимые флаги (хотя каждый и за своим флагом).
- **Размер образа / холодный старт reranker'а (6.3).** Extras-зависимость, ленивая загрузка, грациозный
  no-op при отсутствии модели — прод не падает на lean-деплое.
- **Латентность на широких вопросах.** Expansion (LLM) + reranking (CPU) суммируются. Митигация:
  adaptive — расширять/реранкить выборочно (широкие вопросы), кэш эмбеддингов/вариантов, top-N cap.
- **B3 (exact-scan вектора) усугубляется top-50.** Кандидатов берём больше (50 вместо 12). На гигантских
  монорепо seq-scan заметнее — ловим порогом-алертом из метрик 5.5; hnsw — по данным, не превентивно.
- **`@web`/Tavily — внешняя зависимость и стоимость.** Гейт по `TAVILY_API_KEY` + флаг; биллинг
  существующим путём; смена провайдера — за одним адаптером `web_search.py`.

---

# Phase 7 — «Code Workspace»

*Архитектор: Opus 4.8. Дата плана: 2026-06-22.*
*Цель: превратить Git-вкладку Project Space из «браузера репозитория с предложенными коммитами» в*
*полноценное **рабочее место разработчика** — редактируешь код прямо в Space и одной кнопкой*
*деплоишь результат. Phase 4–6 сделали Space умным по знаниям и коду; Phase 7 замыкает петлю*
*«AI предложил → я доработал → задеплоил», не выходя из браузера.*

## Тезис фазы

Сегодня цикл изменения кода в Space разорван на середине. AI умеет предлагать коммиты
(`extract_commit_from_response`, Phase 4.3) и PR (`push_project_commit`, Phase 5.2), пользователь
видит дерево репо и содержимое файлов (Sprint 3). Но **между «посмотреть» и «запушить» нет звена
«отредактировать»**, а после пуша нет звена «выкатить» — пользователь уходит в IDE и на сервер
руками. Phase 7 добавляет ровно эти два недостающих звена: **встроенный редактор кода** (7.1) и
**deploy-хук** (7.2). Обе фичи аддитивны, обе встают поверх уже работающего commit/push-flow и **не
требуют нового backend-кода для записи** — Sprint 3 уже всё умеет.

> **Ground truth — что у нас УЖЕ есть (важно для честной оценки 7.1).**
> - **Эндпоинт чтения содержимого файла существует** с Sprint 3: `ConnectorFileContentView`
>   (`src/api/views/connectors.py:195`) — `GET /v1/projects/<pk>/connectors/<cid>/file/?path=...`
>   (путь **singular** `/file/`, не путать с `/files/` = `ConnectorReadFilesView`, который отдаёт
>   дерево). Маршрут — `src/api/urls.py:168`. Клиентский метод `getRepoFileContent(projectId, connId, path)`
>   тоже уже есть (`frontend/lib/api/client.ts:636`) и уже вызывается со страницы проекта
>   (`frontend/app/projects/[id]/page.tsx:1018`). **Создавать эндпоинт не нужно — это уже работает.**
>   Это меняет оценку 7.1 с M на **S (чисто фронтенд)**.
> - **Запись/коммит существует** с Sprint 3: `createCommit` → `ProjectCommit(status='pending')` →
>   `CommitConfirmView` (`connectors.py:266`) → `push_project_commit` (атомарный Git Data API).
>   Редактор 7.1 НЕ пишет в репо напрямую — он впадает в этот же flow.
> - **Полинг-статуса как паттерн существует**: `ConnectorSyncView` (`connectors.py:301`) + фронтовый
>   цикл 45 с / каждые 3 с (`handleSync`). Deploy-статус 7.2 переиспользует ровно этот паттерн.
> - **HMAC-подпись исходящих вебхуков существует**: `src/api/services/webhooks.py:25`
>   (`hmac.new(secret, body, sha256).hexdigest()`, заголовок `X-Aineron-Signature: sha256=...`).
>   Deploy-вебхук 7.2 подписывается **этим же** способом. Входящий HMAC-приём — `ConnectorWebhookView`
>   (`connectors.py:314`) как прецедент.
> - **Шифрование секретов существует**: `crypto.py` Fernet (`encrypt_token`/`decrypt_token`), которым
>   уже шифруется `ProjectConnector.access_token_enc`. `deploy_secret` шифруется тем же.

## Принципы Phase 7 (что НЕ трогаем)

| НЕ трогаем | Почему |
|------------|--------|
| Flow `ProjectCommit`: `createCommit` → `CommitConfirmView` → `push_project_commit` | Редактор 7.1 — ещё один **источник** коммитов в готовый flow, а не новый путь записи. Никакого нового push-кода. |
| `ConnectorFileContentView` / `getRepoFileContent` | Уже отдаёт содержимое файла. Редактор только **рендерит** результат — контракт не меняем. |
| Эндпоинты дерева (`ConnectorReadFilesView`, `TreeNode`/`buildTree`) | Дерево слева остаётся как есть; редактор встаёт справа в split-pane, не переписывая навигацию. |
| Полинг-инфра (`ConnectorSyncView` + 45с/3с цикл на фронте) | Deploy-статус 7.2 копирует этот паттерн, не вводит новый канал. |
| HMAC исходящих вебхуков (`services/webhooks.py`) + Fernet (`crypto.py`) | Deploy-вебхук и `deploy_secret` 7.2 используют готовые примитивы безопасности. |
| Флаги `PROJECT_*` = `0/1`, дефолт `0` | Каждая фича Phase 7 — за флагом; при всех `=0` поведение = текущий Phase 6. **Исключение:** `INTERNAL_DEPLOY_ENABLED=0` — опасная capability, выключена по умолчанию намеренно (инверсия логики `PROJECT_PUBLIC_HARDENING=1`). |

## Переиспользование (по образцу таблиц Phase 4/5/6)

| Что переиспользуем | Откуда | Где в Phase 7 |
|--------------------|--------|---------------|
| `getRepoFileContent` + `ConnectorFileContentView` | `client.ts:636`, `connectors.py:195` | 7.1: редактор грузит содержимое файла этим методом |
| `createCommit` + `confirmCommit('push')` | `client.ts`, `connectors.py:227/266` | 7.1: «Commit изменения» из редактора впадает в готовый push-flow |
| `ProjectCommit.files` (`[{path, content}]`) + `kind/status` | `aitext/models.py:369` | 7.1: правка файла из pending-коммита перед пушем (ревью AI-коммита) |
| `TreeNode` / `buildTree` / `listRepoFiles` | `frontend/app/projects/[id]/page.tsx` | 7.1: дерево слева в split-pane (без изменений) |
| Полинг-паттерн `handleSync` (45с/3с) + `ConnectorSyncView` | `page.tsx`, `connectors.py:301` | 7.2: полинг статуса деплоя |
| HMAC `services/webhooks.py:25` + `ConnectorWebhookView` | `src/api/services/webhooks.py`, `connectors.py:314` | 7.2: подпись deploy-вебхука / прецедент входящего HMAC |
| `crypto.py` Fernet (`encrypt_token`/`decrypt_token`) | `src/aitext/crypto.py` | 7.2: шифрование `deploy_secret` (как `access_token_enc`) |
| Конвенция аддитивных миграций | `aitext/migrations/0022_audit_log.py` (последняя) | 7.2: `0023_connector_deploy.py` |

---

## Дорожная карта Phase 7 (порядок = отдача × независимость)

| Sprint | Тема | Сложность | Срок (1 разработчик) | Зависит от | Тип |
|--------|------|-----------|----------------------|-----------|-----|
| **7.1** | Встроенный редактор кода (Monaco) в Git-вкладке | **S** (чисто фронт) | ~2–3 дня | — (backend готов с Sprint 3) | Ценность |
| **7.2** | Deploy-хук: кнопка [Deploy] (внешний вебхук + internal `deploy.sh`) | **M** | ~3–4 дня | — (независим от 7.1) | Ценность + инфра |

**Честная оценка целиком:** ~1–1.5 недели в одиночку. 7.1 и 7.2 **независимы** и параллелизуемы.
7.1 — почти полностью фронтенд (backend-чтение и backend-запись готовы), наибольшая ценность на
единицу времени. 7.2 — основной риск фазы сосредоточен в одной точке (internal deploy = выполнение
shell-команды на проде), поэтому именно ей уделяется бóльшая часть оценки.

---

### Sprint 7.1 — Встроенный редактор кода в Git-вкладке (S)

**Что это даёт пользователю:** открыл файл репо прямо в Space → подсветка синтаксиса 100+ языков →
кнопка [Редактировать] → правка → [Commit изменения] с сообщением → пуш через готовый flow. Три
сценария: (1) AI предложил коммит → подправить файл из pending-коммита перед пушем; (2) быстро
поправить самому без IDE; (3) просто посмотреть код (read-only по умолчанию).

**Конкурентный паритет/превосходство:** vs. **Cursor / GitHub web-editor (`.dev`)** — редактирование
кода в браузере с подсветкой; мы даём это **внутри Space рядом с AI-чатом и базой знаний**, без
установки IDE. vs. **Claude/ChatGPT/Perplexity Projects** — **полное превосходство**: ни один не
редактирует и не коммитит файлы в реальный git-репозиторий из чат-интерфейса.

#### Ключевое решение №1: Monaco с ленивой загрузкой (`next/dynamic`, `ssr:false`)

Monaco (`@monaco-editor/react`) — движок VS Code: автоопределение языка по расширению, подсветка
100+ языков, бесплатен. Весит ~5 МБ — **нельзя** грузить на страницу проекта по умолчанию. Решение:
`next/dynamic(() => import('...'), { ssr: false })` — Monaco не умеет SSR и подтягивается только при
первом открытии файла. Альтернатива **CodeMirror 6** (~300 КБ) — за тем же флагом для медленных
соединений/мобильных, но Monaco — дефолт по качеству фич.

#### Ключевое решение №2: read-only по умолчанию, явный commit (без автосохранения)

- Открытие файла = read-only просмотр (нельзя случайно сломать). [Редактировать] → edit-режим.
- Изменения — в локальном React-state, НЕ автосохранение. При наличии diff появляется
  [Commit изменения] + поле commit message.
- Commit = `createCommit(projectId, {connector_id, commit_message, files:[{path, content}]})` →
  `confirmCommit(commitId, 'push')`. **Ноль нового backend-кода** — это готовый flow Sprint 3.
- Закрытие файла с несохранёнными правками → `beforeunload`-гард («Есть несохранённые изменения»).

#### Ключевое решение №3: ревью pending-коммита в редакторе

AI-коммит (Phase 4.3) приходит как `ProjectCommit(status='pending', files=[{path, content}])`. В
списке коммитов клик на файл pending-коммита открывает его контент (из `commit.files`, **не** из
репо — это предложенная, ещё не запушенная версия) в редакторе. Правка → пересобирается
`commit.files` → `confirmCommit('push')` пушит уже доработанную версию. Это сценарий №1 («AI
исправил → подправлю перед пушем»), ради которого редактор и нужен в первую очередь.

#### Файлы

| Файл | Действие |
|------|----------|
| `frontend/components/projects/CodeEditor.tsx` | **новый**: Monaco через `next/dynamic({ssr:false})`; props `value/language/readOnly/onChange`; commit-панель (message + [Commit изменения]); `beforeunload`-гард на dirty-state |
| `frontend/app/projects/[id]/page.tsx` | в `ConnectorsTab`: `selectedFile` state (`{path, content, dirty}`); split-pane (дерево 30% / редактор 70%); клик в `TreeNode` → `getRepoFileContent` → открыть в редакторе; клик на файл pending-коммита → открыть `commit.files[i].content` |
| `frontend/lib/api/client.ts` | **уже есть** `getRepoFileContent`, `createCommit`, `confirmCommit` — переиспользуем, новых методов не требуется |
| `src/api/views/connectors.py` | **без изменений** — `ConnectorFileContentView` уже отдаёт содержимое (`GET .../file/?path=`) |
| `src/api/urls.py` | **без изменений** — маршрут `connector_file_content` существует (`:168`) |
| `package.json` (frontend) | **+** `@monaco-editor/react` (и опц. `@uiw/react-codemirror` для лёгкого режима) |

> **Замечание о ground truth (важно для оценки).** ТЗ предполагало возможное создание эндпоинта
> `GET .../connectors/{cid}/files/?path=...` и правки `connectors.py`/`urls.py`. По факту эндпоинт
> существует с Sprint 3 под путём **`/file/`** (singular), а не `/files/?path=`, и клиентский метод
> `getRepoFileContent` уже им пользуется. Поэтому 7.1 — **чисто фронтенд-спринт (S)**, а не M:
> backend-чтение и backend-запись (commit-flow) готовы, добавляется только UI редактора.

#### Компромиссы

- **Делаем:** Monaco (lazy, read-only→edit), commit из редактора в готовый flow, правка файла из
  pending-коммита, `beforeunload`-гард.
- **НЕ делаем:** diff-вьювер «до/после» в редакторе (Monaco `DiffEditor` умеет, но это +scope) —
  пока обычный редактор; визуальный diff — позже.
- **НЕ делаем:** мультифайловые табы / открытие нескольких файлов одновременно — один активный файл
  в split-pane; табы — позже.
- **НЕ делаем:** LSP/автодополнение по проекту (как в IDE) — Monaco даёт подсветку и базовую
  intellisense по языку, но не семантику репо; это IDE-территория.
- **Риск:** вес Monaco (~5 МБ). Митигация: `ssr:false` + ленивый импорт (грузится только при первом
  открытии файла), флаг `PROJECT_CODE_EDITOR`, опц. CodeMirror для lean-режима.

**Флаги:** `PROJECT_CODE_EDITOR=0/1` (при `=0` клик на файл — старое поведение «только просмотр
содержимого», без split-pane и edit-режима).

---

### Sprint 7.2 — Deploy-хук: кнопка [Deploy] (M)

**Что это даёт пользователю:** после коммита/пуша — одна кнопка [Deploy] рядом с
[Синхронизировать]: внешний пользователь дёргает свой deploy-вебхук (его сервер делает
`git pull && restart`), владелец сервиса — выкатывает сам aineron.ru через `bash deploy.sh`. Статус:
[В процессе…] → [Задеплоено] / [Ошибка деплоя] + опц. хвост лога.

**Конкурентный паритет/превосходство:** vs. **Vercel/Netlify deploy-hooks, Cursor** — кнопка деплоя
прямо из рабочего пространства; уникальность — **деплой в той же вкладке, где AI предложил коммит и
ты его доработал** (замкнутая петля commit→review→deploy без выхода в CI/терминал). Особенно силён
B2B-сценарий: один соавтор (Phase 5.1, роль editor) коммитит через AI, другой (owner) ревьюит и
жмёт [Deploy].

#### Ключевое решение №1: ДВА раздельных пути деплоя с разной авторизацией

Это главное архитектурное решение спринта — пути нельзя смешивать:

1. **Внешний deploy-вебхук** (для репозиториев пользователей). `POST` на
   `ProjectConnector.deploy_webhook_url` с HMAC-подписью тела (`deploy_secret`). Триггерит **любой
   владелец проекта** для **своего** сервера. Безопасность вынесена на сторону получателя (его
   webhook-receiver проверяет подпись и решает, что выполнять).
2. **Internal deploy самого aineron.ru** (`bash deploy.sh`). Это **платформенно-административное**
   действие, а не действие произвольного `project.user`. Гейт: **`request.user.is_staff` /
   `is_superuser`** (владелец сервиса), а НЕ владелец проекта. Запускает `subprocess` без
   `shell=True`, по whitelist (`INTERNAL_DEPLOY_SCRIPT`), с таймаутом 120 с и rate-limit ≤1/30 с.
   Флаг `INTERNAL_DEPLOY_ENABLED=0` по умолчанию — это RCE-смежная поверхность, включается осознанно.

> **Почему не «только owner проекта», как в ТЗ.** Деплой самого aineron.ru через `deploy.sh` — это
> выполнение shell-команды на проде. Дать его любому, кто создал проект, — дыра. Internal deploy
> отвязан от владения проектом и привязан к роли платформы (`is_staff`). Внешний путь (вебхук на
> чужой сервер) безопасен для любого owner — там мы лишь шлём подписанный POST, исполнение — не у нас.

#### Ключевое решение №2: статус деплоя — переиспользуем sync-полинг

Не изобретаем канал: deploy возвращает `deploy_status` (`pending/running/success/error`) и опц.
`deploy_log` (хвост stdout, N строк). Фронт полит ровно как `handleSync` (45 с / каждые 3–5 с) до
терминального статуса. Опц. модель `ProjectDeployLog` хранит последние N деплоев для истории в UI.

#### Ключевое решение №3: безопасность по образцу существующих примитивов

- `deploy_webhook_url` + `deploy_secret` шифруются Fernet (`crypto.py`), как `access_token_enc`.
- Подпись тела — `services/webhooks.py:25` (HMAC-SHA256, `X-Aineron-Signature: sha256=...`).
- Internal subprocess: `subprocess.run([INTERNAL_DEPLOY_SCRIPT], shell=False, timeout=120)`,
  whitelist скрипта из settings, без интерполяции пользовательского ввода в команду.

#### Файлы

| Файл | Действие |
|------|----------|
| `src/aitext/models.py` | **+** `ProjectConnector.deploy_webhook_url` (nullable Char), `deploy_secret` (Fernet, как `access_token_enc`), `deploy_status`/`last_deploy_at`; **новая** (опц.) `ProjectDeployLog(connector, status, log, created_at)` |
| `src/aitext/migrations/0023_connector_deploy.py` | **новая** (аддитивная): поля деплоя + опц. `ProjectDeployLog` (последняя миграция — `0022_audit_log`) |
| `src/api/views/connectors.py` | **+** `ConnectorDeployView` (`POST .../connectors/<cid>/deploy/`) — шлёт подписанный POST на `deploy_webhook_url`; `GET` отдаёт `deploy_status`/лог (полинг). Owner проекта. |
| `src/api/views/deploy.py` | **новый**: `InternalDeployView` — гейт `is_staff`/`is_superuser` + флаг `INTERNAL_DEPLOY_ENABLED` + rate-limit; `subprocess.run([INTERNAL_DEPLOY_SCRIPT], shell=False, timeout=120)` |
| `src/api/urls.py` | **+** `projects/<pk>/connectors/<cid>/deploy/`, **+** `internal/deploy/` |
| `src/config/settings.py` | `PROJECT_DEPLOY_HOOK`, `INTERNAL_DEPLOY_ENABLED`, `INTERNAL_DEPLOY_SCRIPT=/app/deploy.sh` |
| `frontend/app/projects/[id]/page.tsx` | в `ConnectorsTab`: кнопка [Deploy] рядом с [Синхронизировать]; полинг статуса (паттерн `handleSync`); опц. хвост лога; поле deploy-вебхука в настройках коннектора |
| `frontend/lib/api/client.ts` + `types.ts` | `triggerDeploy(projectId, connId)`, `getDeployStatus(projectId, connId)`; поля деплоя в `ProjectConnector` |

#### Компромиссы

- **Делаем:** внешний deploy-вебхук (HMAC), internal `deploy.sh` (staff-only, флаг), полинг статуса,
  опц. лог последних деплоев.
- **НЕ делаем:** полноценный CI/CD (стадии, артефакты, rollback) — это отдельный продукт; мы даём
  «дёрнуть деплой», не оркестрацию.
- **НЕ делаем:** стриминг полного лога деплоя в реальном времени — только хвост N строк по
  завершении (стрим — позже, если будет спрос).
- **НЕ делаем:** деплой произвольной командой из UI — internal путь жёстко привязан к
  `INTERNAL_DEPLOY_SCRIPT` из settings, без пользовательского ввода в команду.
- **Риск (главный в фазе):** internal deploy = выполнение shell на проде. Митигация: `is_staff`-гейт
  (не owner проекта), `INTERNAL_DEPLOY_ENABLED=0` по умолчанию, `shell=False` + whitelist + таймаут +
  rate-limit. Внешний путь риск не несёт (исполнение — на чужом сервере).

**Флаги:** `PROJECT_DEPLOY_HOOK=0/1` (внешний вебхук), `INTERNAL_DEPLOY_ENABLED=0/1` (internal
`deploy.sh`, **выключен по умолчанию** — опасная capability).

---

## Сводка новых флагов окружения (Phase 7)

```
# Sprint 7.1 — Встроенный редактор кода
PROJECT_CODE_EDITOR=0       # Monaco-редактор в Git-вкладке (read-only→edit→commit)

# Sprint 7.2 — Deploy-хук
PROJECT_DEPLOY_HOOK=0       # кнопка [Deploy] → внешний deploy-вебхук (HMAC)
INTERNAL_DEPLOY_ENABLED=0   # internal-деплой самого aineron.ru (bash deploy.sh) — ОПАСНО, off by default
INTERNAL_DEPLOY_SCRIPT=/app/deploy.sh   # whitelist-скрипт для internal-деплоя (subprocess, shell=False)
```

## Порядок выкатки и риски

1. **7.1 первым — почти вся ценность за S-бюджет.** Backend (чтение файла + commit/push-flow) готов с
   Sprint 3; добавляется только UI Monaco. Главное техническое решение — ленивая загрузка
   (`next/dynamic`, `ssr:false`), чтобы 5 МБ Monaco не падали на страницу проекта по умолчанию.
2. **7.2 параллелизуем с 7.1** — независим. Внутри 7.2 — **сначала внешний deploy-вебхук** (безопасен,
   исполнение на стороне пользователя), **затем** internal `deploy.sh` (опасная capability, отдельный
   флаг, staff-гейт).

**Главные риски, заложенные в дизайн заранее:**
- **Internal deploy = RCE-смежная поверхность (7.2).** Выполнение shell на проде. Митигация:
  `is_staff`/`is_superuser`-гейт (НЕ owner проекта — см. ключевое решение №1), `INTERNAL_DEPLOY_ENABLED=0`
  по умолчанию, `subprocess` с `shell=False` + whitelist-скрипт из settings + таймаут 120 с +
  rate-limit ≤1/30 с. Это единственное место фазы, заслуживающее веса уровня B4.
- **Вес Monaco (7.1).** ~5 МБ. Митигация: `ssr:false` + ленивый импорт + флаг + опц. CodeMirror.
- **Несохранённые правки в редакторе (7.1).** `beforeunload`-гард; commit — явный, без автосохранения.
- **Утечка deploy-секрета (7.2).** `deploy_secret` шифруется Fernet (`crypto.py`), тело вебхука
  подписывается HMAC (`services/webhooks.py`) — те же примитивы, что у `access_token_enc` и исходящих
  вебхуков; ничего нового не изобретаем.
- **Путаница двух deploy-путей (7.2).** Внешний вебхук (любой owner → свой сервер) и internal
  (`is_staff` → aineron.ru) — раздельные вью (`ConnectorDeployView` vs `InternalDeployView`) и
  раздельные флаги; не смешиваются.

  План обновлён. Теперь по вопросу — нужно ли что-то ещё или остановиться?

  Что реализовано — это уже уровень выше Claude.ai Projects и Perplexity Spaces:
  - База знаний + векторный RAG с гибридным поиском (RRF)
  - Подключение GitHub/Gitea, AI-коммиты, PR
  - Query expansion, @file/@web директивы, two-level retrieval
  - Редактор кода прямо в интерфейсе
  - Публичные Spaces, коллаборация, Telegram-бот, аудит-лог

  Что имеет смысл делать дальше — только если есть реальные пользователи и обратная связь. Технически можно добавить:

  ┌────────────────────────────────────────────────────────┬────────────────────────────────────────────────────┐
  │                          Идея                          │                      Ценность                      │
  ├────────────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
  │ PROJECT_RERANK=1 + облегчить модель (CPU-only PyTorch) │ Лучше качество поиска при большой базе             │
  ├────────────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
  │ backfill_summaries — запустить для существующих файлов │ Активирует two-level retrieval для старых проектов │
  ├────────────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
  │ Billing за использование RAG/embed-токенов             │ Монетизация тяжёлых операций                       │
  ├────────────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
  │ Поддержка .pdf, .docx в базе знаний                    │ Расширение форматов                                │
  └────────────────────────────────────────────────────────┴────────────────────────────────────────────────────┘

  Мой совет: остановиться и накапливать обратную связь от пользователей. Все базовые и продвинутые сценарии покрыты. Следующий шаг должен диктовать рынок, а не план.

---

## Large-file commit fixes (сессия 2026-06-23)

### Контекст проблемы

Прокси laozhang.ai жёстко ограничивает output Claude до **16 384 токенов (~55K символов)** — параметр `max_tokens` игнорируется. Файл `src/studio/tasks.py` = 64 298 символов в KB → AI неизбежно обрезает вывод на 55K. Кнопка «Подтвердить коммит» не работала для таких файлов.

**Подтверждение**: dashboard laozhang.ai, поле «Завершение: 16384» для обоих Claude-запросов в логах — это хард-кап прокси, не наш `max_tokens`.

### Что сделано

| # | Файл | Изменение | Коммит |
|---|------|-----------|--------|
| 1 | `frontend/components/chat/MarkdownContent.tsx` | Незакрытый FILE-блок (обрезанный) рендерится как `FileBlock` вместо каракулей. Оранжевый баннер предупреждения `truncated=true`. Интерфейс `Segment` получил поле `truncated?: boolean` | `d3ecd65` |
| 2 | `src/aitext/commit_extract.py` | Полный рерайт: KB tail-stitch (окна 500/200/80 символов), fallback через `_fetch_from_connector()` из tasks.py, предупреждения в commit message | `d3ecd65`, `43afd10`, `f28fca2` |
| 3 | `src/aitext/codebase.py` | Баг: `vector_search()` возвращал строку, `build_codebase_context` итерировал по символам → `'str' object has no attribute 'extracted_text'`. Исправлено: `vector_search_candidates()` → список file_id → `ProjectFile.objects.filter(id__in=...)` | `643d182` |

### Текущее поведение (с костылями)

```
AI output (55K) → незакрытый FILE-блок → _stitch_tail_from_kb()
  → ищет последние 500 симв. AI в KB-файле → дописывает хвост
  → ProjectCommit с предупреждением в commit message
```

**Ограничение**: если изменения были в последних ~9K символов файла (хвост) — хвост перетирается оригиналом из KB. Коммит будет создан, но правки в хвосте потеряются.

---

## Phase 8 — EDIT Blocks Architecture (план)

### Цель

Убрать kostyli — сделать надёжные коммиты для файлов **любого размера** с изменениями **в любом месте**, тратя минимум выходных токенов.

### Ключевая идея

AI выводит **только изменённые фрагменты** в формате SEARCH/REPLACE. Сервер применяет патчи к полному файлу из KB/GitHub. Итог — полный правильный файл без участия лимита output.

Для малых файлов (< 30K симв.) — прежний FILE-блок (полный файл, просто и надёжно).  
Для больших файлов (≥ 30K симв.) — новый EDIT-блок.

### Формат EDIT-блока

```
=== EDIT: src/studio/tasks.py ===
<<<SEARCH>>>
def _build_sandbox_context(project, lang):
    """old docstring"""
    return {}
<<<REPLACE>>>
def _build_sandbox_context(project, lang):
    """Returns sandbox context dict for given project and language."""
    return {"lang": lang, "project_id": project.id}
<<<END>>>
<<<SEARCH>>>
MAX_OUTPUT_TOKENS = 16384
<<<REPLACE>>>
MAX_OUTPUT_TOKENS = 32768
<<<END>>>
=== END EDIT ===
```

- Несколько `<<<SEARCH>>>...<<<REPLACE>>>...<<<END>>>` в одном EDIT-блоке — несколько правок одного файла.
- Несколько `=== EDIT: path === ... === END EDIT ===` подряд — несколько файлов.
- SEARCH должен содержать 5–20 строк контекста вокруг правки для надёжного поиска.
- Совместим с существующим FILE-блоком — оба формата могут быть в одном ответе.

### Архитектура реализации

#### 1. `src/aitext/commit_extract.py` — новые функции

```python
# Паттерн EDIT-блока
_EDIT_BLOCK_RE = re.compile(
    r'===\s*EDIT:\s*([^\n=]+?)\s*===\n([\s\S]*?)===\s*END EDIT\s*===',
    re.MULTILINE,
)
# Паттерн одного SEARCH/REPLACE внутри EDIT-блока
_HUNK_RE = re.compile(
    r'<<<SEARCH>>>\n([\s\S]*?)<<<REPLACE>>>\n([\s\S]*?)<<<END>>>',
    re.MULTILINE,
)

def parse_edit_blocks(text: str) -> dict[str, list[dict]]:
    """Возвращает {path: [{'search': str, 'replace': str}, ...]}"""
    result = {}
    for m in _EDIT_BLOCK_RE.finditer(text):
        path = m.group(1).strip()
        hunks = [
            {'search': h.group(1), 'replace': h.group(2)}
            for h in _HUNK_RE.finditer(m.group(2))
        ]
        if hunks:
            result[path] = hunks
    return result

def apply_edit_blocks(source: str, hunks: list[dict]) -> str:
    """Применяет SEARCH/REPLACE патчи к тексту файла.
    
    Стратегия: точное совпадение → нормализованное (strip trailing ws) → ошибка.
    """
    result = source
    for hunk in hunks:
        search, replace = hunk['search'], hunk['replace']
        if search in result:
            result = result.replace(search, replace, 1)
            continue
        # Нормализованный поиск — убираем trailing whitespace в каждой строке
        def _norm(s): return '\n'.join(line.rstrip() for line in s.split('\n'))
        norm_result = _norm(result)
        norm_search = _norm(search)
        if norm_search in norm_result:
            # Находим позицию нормализованного поиска, применяем в оригинале
            idx = norm_result.find(norm_search)
            # Подсчитываем количество символов до idx в нормализованной версии
            # через маппинг строк (надёжнее чем char-offset)
            lines_before = norm_result[:idx].count('\n')
            orig_lines = result.split('\n')
            search_lines = norm_search.count('\n') + 1
            orig_block = '\n'.join(orig_lines[lines_before:lines_before + search_lines])
            result = result.replace(orig_block, replace, 1)
        else:
            raise ValueError(f"SEARCH не найден в файле: {search[:80]!r}")
    return result
```

#### 2. Приоритетная логика в `extract_commit_from_response()`

```
Порядок парсинга:
  1. parse_file_blocks()   — полные FILE-блоки (малые файлы, ≤55K)
  2. parse_edit_blocks()   — EDIT-блоки (большие файлы, патчи)
  3. _find_truncated_file() + KB tail-stitch  — legacy fallback
  4. return None
```

Если EDIT-блоки найдены:
- для каждого пути вызываем `_get_full_file_source(project, path)` → полный файл из KB/GitHub
- применяем `apply_edit_blocks(source, hunks)` → patched content
- если `patched == source` — предупреждение «ничего не изменилось»
- если `apply_edit_blocks` бросил `ValueError` — логируем, пропускаем файл

#### 3. Обновление системного промпта (`AI_COMMIT_INSTRUCTION`)

Промпт должен быть контекстно-зависимым. В `inject_commit_instruction()` определяем есть ли в проекте большие файлы:

```python
def inject_commit_instruction(project, messages_for_api: list) -> None:
    if not project.connectors.exists():
        return
    
    # Проверяем наличие больших файлов в KB
    from .models import ProjectFile
    has_large_files = ProjectFile.objects.filter(
        project=project, status='ready', enabled=True,
    ).extra(where=["char_length(extracted_text) > 30000"]).exists()
    
    if has_large_files:
        messages_for_api.append({"role": "system", "content": AI_COMMIT_INSTRUCTION_WITH_EDITS})
    else:
        messages_for_api.append({"role": "system", "content": AI_COMMIT_INSTRUCTION})
```

`AI_COMMIT_INSTRUCTION_WITH_EDITS` объясняет оба формата и говорит: «файлы > 30K символов — используй EDIT-блоки».

#### 4. Подсказка в KB-контексте (`tasks.py`)

Когда большой файл инжектируется в контекст, добавляем аннотацию:

```python
# В build_project_knowledge_context() или build_codebase_context()
if len(content) > 30_000:
    header = f"[БОЛЬШОЙ ФАЙЛ: {len(content)} симв. — для правок используй EDIT-блоки]"
    injected = f"=== FILE: {path} ===\n{header}\n{content[:30_000]}...\n[обрезано для контекста]"
else:
    injected = f"=== FILE: {path} ===\n{content}\n=== END FILE ==="
```

### Порядок внедрения (Sprint 8)

| # | Задача | Файл |
|---|--------|------|
| 8.1 | `parse_edit_blocks()` + `apply_edit_blocks()` + тесты | `src/aitext/commit_extract.py` |
| 8.2 | Встроить в `extract_commit_from_response()` — приоритет EDIT после FILE | `src/aitext/commit_extract.py` |
| 8.3 | Контекстный `AI_COMMIT_INSTRUCTION` — два варианта промпта | `src/aitext/commit_extract.py` |
| 8.4 | Аннотация больших файлов в KB-инжекции | `src/aitext/tasks.py` |
| 8.5 | Frontend: парсинг и рендер EDIT-блоков (свёртываемый diff-вид) | `frontend/components/chat/MarkdownContent.tsx` |
| 8.6 | Удалить tail-stitch после подтверждения работы EDIT-блоков | `src/aitext/commit_extract.py` |

### Сравнение подходов

| Подход | Изменения в хвосте | Файлы любого размера | Токены вывода | Сложность |
|--------|-------------------|----------------------|---------------|-----------|
| FILE-блок (текущий) | Нет — файл обрезается | Нет (лимит ~55K) | Весь файл | Низкая |
| KB tail-stitch (текущий) | **Нет** — хвост из KB | Частично | Весь AI-вывод | Средняя |
| **EDIT-блоки (Phase 8)** | **Да** | **Да** | Только изменения | Средняя |
| Построчный вывод (line ranges) | Да | Да | Только изменения | Высокая (нужны номера строк) |
| AST-патч (function-level) | Да | Да | Только функция | Высокая (language-specific) |

**EDIT-блоки — оптимальный баланс** между надёжностью, универсальностью и сложностью реализации. Не требует изменений в протоколе хранения файлов, переиспользует `_get_full_file_source()` и `_fetch_from_connector()`, работает для любого языка.

### Ключевое отличие от tail-stitch

Tail-stitch предполагает, что хвост **не изменялся**. Это работает в 80% случаев, но ломается для правок в конце файла.

EDIT-блоки вообще не делают предположений о хвосте — AI явно указывает что именно изменить, сервер применяет хирургически точно.
