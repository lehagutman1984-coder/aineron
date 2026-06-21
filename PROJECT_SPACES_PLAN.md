# PROJECT SPACES — План реализации

Апгрейд фичи **«Проекты»** до полноценных **«Project Spaces»** по аналогии с
Claude.ai Projects, Perplexity Spaces и ChatGPT Projects.

Цель: проект становится не просто папкой для чатов, а рабочим пространством со
своей **базой знаний** (файлы), **инструкциями** (system prompt) и
**подключённым git-репозиторием** (GitHub / Gitea), который AI читает и в который
предлагает коммиты.

---

## СТАТУС РЕАЛИЗАЦИИ (2026-06-21)

| Этап | Статус | Коммиты |
|------|--------|---------|
| Спринт 1 — База знаний (ProjectFile + Celery + инжект в контекст) | **ЗАВЕРШЁН** | `bf16907`, `fix(projects)` |
| Спринт 2 — UX Инструкций (вкладка + счётчик + превью + бейдж в чате) | **ЗАВЕРШЁН** | (`studio-v3`) |
| Спринт 3 — Git-коннектор (GitHub/Gitea PAT + браузер файлов + коммиты) | **ЗАВЕРШЁН** | `b9f8296` |
| **Bug-fix пост-аудит** (6 критических исправлений) | **ЗАВЕРШЁН** | `b9f8296` |

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
