# PROJECT SPACES — План реализации

Апгрейд фичи **«Проекты»** до полноценных **«Project Spaces»** по аналогии с
Claude.ai Projects, Perplexity Spaces и ChatGPT Projects.

Цель: проект становится не просто папкой для чатов, а рабочим пространством со
своей **базой знаний** (файлы), **инструкциями** (system prompt) и
**подключённым git-репозиторием** (GitHub / Gitea), который AI читает и в который
предлагает коммиты.

---

## СТАТУС РЕАЛИЗАЦИИ (2026-06-22)

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
| **Sprint 5.7** — RAG Quality (лимиты + надёжность эмбеддингов + умный чанкинг) | **В ПЛАНЕ** | — |

**Phase 4 — ПОЛНОСТЬЮ ЗАВЕРШЕНА** (все 5 спринтов).

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
