# PROJECT SPACES — Справочник реализации

Апгрейд «Проектов» до полноценных **Project Spaces**: рабочее пространство с базой знаний (файлы),
инструкциями (system prompt), подключённым git-репозиторием и AI, который читает код и предлагает коммиты.

**ВСЕ 8 ФАЗ ЗАВЕРШЕНЫ** (по состоянию на 2026-06-23).

---

## Статус реализации

| Фаза | Что сделано | Ключевые коммиты |
|------|-------------|------------------|
| **Фаза 1** — База знаний | `ProjectFile` + Celery-извлечение текста + инжект в контекст (SSE + Celery) | `bf16907` |
| **Фаза 2** — UX инструкций | Вкладка «Инструкции», счётчик символов, markdown-превью, бейдж в чате | studio-v3 |
| **Фаза 3** — Git-коннектор | `ProjectConnector` + `ProjectCommit`, GitHub/Gitea PAT, браузер файлов, push | `b9f8296` |
| **Фаза 4** — RAG + Sync + Collab | pgvector RAG, inbound-синк, AI-коммиты, Telegram Spaces, публичные Spaces | `9bc8a51`, `6af2601`, `927db84` |
| **Фаза 5** — Intelligent Workspaces | Коллаборация, @codebase, FTS-поиск, версии файлов, polling, audit log, TG-upload | `f2f6339`, `3c2d091`, `72e6ab3`, `f9a5338` |
| **Фаза 6** — RAG Supremacy | Hybrid+RRF, query expansion, reranking, @file/@web, two-level retrieval | `c680c8a`, `1955105` |
| **Фаза 7** — Code Workspace | CodeMirror-редактор (JS/HTML/CSS), deploy-хук, коммит из редактора | `c680c8a`, `1955105` |
| **Фаза 8** — EDIT Blocks | SEARCH/REPLACE патч-коммиты для файлов >30K символов, EditBlock компонент | `45a8841` |

---

## Ключевые модели (`src/aitext/models.py`)

| Модель | Назначение |
|--------|-----------|
| `Project` | Рабочее пространство: `name`, `system_prompt`, `is_public`, `public_slug`, `public_views` |
| `ProjectFile` | Файл базы знаний: `source` (upload/repo), `embed_status`, `extracted_text`, `connector`, `repo_path`, `embed_error` |
| `ProjectChunk` | Векторный чанк файла: `embedding` (pgvector 1536-dim), `chunk_index` (-1 = summary для two-level) |
| `ProjectConnector` | Git-коннектор: `connector_type` (github/gitea), `access_token_enc` (Fernet), `last_synced_sha`, `sync_status` |
| `ProjectCommit` | Предложенный коммит: `files` (JSON), `status` (pending/pushed/rejected/failed), `kind` (commit/pull_request) |
| `ProjectCollaborator` | Соавтор: `role` (viewer/editor), `accepted_at` |
| `ProjectFileVersion` | История версий файла: `content_snapshot`, `repo_sha` |
| `ProjectAuditEntry` | Журнал действий: `actor`, `action`, `files_used` (JSON) |

---

## API-эндпоинты (`src/api/urls.py`)

```
GET/POST    v1/projects/
PATCH/DEL   v1/projects/<pk>/
POST        v1/projects/<pk>/publish/
GET         v1/public/spaces/<slug>/                    # публичный read-only

GET/POST    v1/projects/<pk>/files/
GET         v1/projects/<pk>/files/search/?q=
GET/PATCH/DEL   v1/projects/<pk>/files/<id>/
GET         v1/projects/<pk>/files/<id>/versions/
POST        v1/projects/<pk>/files/<id>/versions/<vid>/restore/
POST        v1/projects/<pk>/files/<id>/reembed/        # повторный эмбеддинг

GET/POST    v1/projects/<pk>/collaborators/
GET/DEL     v1/projects/<pk>/collaborators/<cid>/
GET         v1/projects/<pk>/audit/

GET/POST    v1/projects/<pk>/connectors/
GET/DEL     v1/projects/<pk>/connectors/<cid>/
GET         v1/projects/<pk>/connectors/<cid>/files/    # дерево репо
GET         v1/projects/<pk>/connectors/<cid>/file/     # содержимое файла
POST        v1/projects/<pk>/connectors/<cid>/sync/     # ручной синк
POST        v1/projects/<pk>/connectors/<cid>/webhook/  # inbound webhook
POST        v1/projects/<pk>/connectors/<cid>/deploy/   # deploy-хук

GET/POST    v1/projects/<pk>/commits/
POST        v1/projects/<pk>/commits/<id>/confirm/
DELETE      v1/projects/<pk>/commits/<id>/
```

---

## Ключевые файлы backend

| Файл | Назначение |
|------|-----------|
| `src/aitext/tasks.py` | `build_project_knowledge_context()` — единая точка инжекта; `generate_ai_response`; `embed_project_file`; `sync_connector_task`; `extract_commit_from_response()` |
| `src/aitext/embeddings.py` | `chunk_text()`, `smart_chunk()`, `embed_chunks()`, `vector_search()`, `vector_search_candidates()`, `_get_query_embedding()` (Redis-кэш 24ч), `embed_file_summary()`, `file_level_search()` |
| `src/aitext/search.py` | `search_knowledge()` (FTS+vector), `hybrid_search()` (RRF) |
| `src/aitext/retrieval.py` | `adaptive_top_k()`, `build_search_query()` (conversation-aware), `parse_context_directives()` (@file/@web), `expand_query()` (LLM expansion) |
| `src/aitext/rerank.py` | Cross-encoder reranker (CPU, `ms-marco-MiniLM-L-6-v2`), ленивый синглтон |
| `src/aitext/web_search.py` | Tavily-клиент: нормализованные сниппеты + источники, graceful no-op без ключа |
| `src/aitext/sync.py` | `sync_connector()` — diff дерева репо по SHA, upsert `ProjectFile(source='repo')` |
| `src/aitext/codebase.py` | `codebase_search()` (вектор по repo-файлам), `repo_tree_map()` |
| `src/aitext/github_client.py` | REST GitHub API: `list_tree`, `get_file_content`, `push_files` (атомарный Git Data API), `create_branch`, `create_pull` |
| `src/studio/gitea_client.py` | Gitea API с параметром `base_url` для внешних репо |
| `src/aitext/crypto.py` | Fernet-шифрование PAT-токенов: `encrypt_token`, `decrypt_token` |
| `src/aitext/file_utils.py` | `extract_text_from_file()` — PDF/DOCX/TXT/Excel/PPTX/архивы |
| `src/aitext/permissions.py` | `project_role(user, project)` → owner/editor/viewer/None |
| `src/api/views/connectors.py` | Все view: коннекторы, файлы репо, коммиты, синк, webhook, deploy |
| `src/api/views/project_files.py` | Файлы KB: загрузка, поиск, версии, восстановление, reembed |
| `src/api/views/collaborators.py` | Соавторы: приглашение, роли, удаление |
| `src/api/views/projects.py` | Проекты, публикация, публичный view, audit log |

---

## Ключевые файлы frontend

| Файл | Назначение |
|------|-----------|
| `frontend/app/projects/[id]/page.tsx` | Главная страница проекта: вкладки Файлы/Инструкции/Git/Команда/Журнал; коммиты с кнопками Подтвердить/Отклонить/Удалить |
| `frontend/app/s/[slug]/page.tsx` | Публичная страница Space (SSR, OG-теги, SEO) |
| `frontend/components/chat/MarkdownContent.tsx` | Рендер ответов AI: `PreBlock` (кнопки Copy/Download), `FileBlock`, `EditBlock` |
| `frontend/components/code-editor/CodeEditor.tsx` | CodeMirror-редактор с подсветкой JS/HTML/CSS; коммит без автопуша |
| `frontend/lib/api/client.ts` | Все API-методы: `listProjects`, `createConnector`, `confirmCommit`, `deleteCommit`, `syncConnector`, `reembedFile`, … |
| `frontend/lib/api/types.ts` | Типы: `Project`, `ProjectFile`, `ProjectConnector`, `ProjectCommit`, `ProjectCollaborator` |

---

## RAG-пайплайн (как работает контекст)

```
build_project_knowledge_context(project, user_message)
  ├── parse_context_directives() → @file/@web директивы
  ├── @file → полный extracted_text нужного файла (обходит RAG)
  ├── @web → web_search (Tavily) → сниппеты + источники
  ├── build_search_query() → conversation-aware запрос (окно 4 сообщения)
  ├── expand_query() → 3 варианта (PROJECT_QUERY_EXPANSION)
  ├── hybrid_search()
  │     ├── vector_search_candidates(top_n=50) ← exact cosine per-project (no ANN)
  │     ├── FTS SearchVector по extracted_text
  │     └── RRF-слияние rank-слоёв (PROJECT_HYBRID_SEARCH)
  ├── rerank(top_50 → top_15) ← cross-encoder CPU (PROJECT_RERANK)
  ├── two-level: file_level_search(summary) → chunk search в файлах (PROJECT_TWO_LEVEL)
  └── inject в messages_for_api (cap: AGGREGATE_INJECT_LIMIT = 400_000 символов)
```

Инжект вызывается в трёх местах: `tasks.py:generate_ai_response`, `api/views/chats.py:StreamMessageView`, `telegram_bot/handlers/chat.py`.

Лексический fallback работает всегда при `embed_status != 'done'` — деградация плавная.

---

## EDIT Blocks (Фаза 8)

AI использует формат SEARCH/REPLACE вместо полного FILE-блока для больших файлов:

```
=== EDIT: path/to/file.py ===
<<<<<<< SEARCH
старый код (уникальный фрагмент)
=======
новый код
>>>>>>> REPLACE
```

- `apply_edit_blocks(path, blocks)` в `src/studio/agents/blocks.py` — применяет патчи с uniqueness guard
- `extract_commit_from_response()` — приоритет: EDIT-блоки → FILE-блоки → нет коммита
- `EDIT_HINT_THRESHOLD = 80_000` символов — порог, выше которого AI получает подсказку использовать EDIT
- `max_tokens = 32_000` во всех путях генерации

---

## Переменные окружения

```bash
# Git-коннекторы (обязательно)
PROJECT_CONNECTOR_FERNET_KEY=<Fernet.generate_key()>

# RAG-флаги
PROJECT_VECTOR_RAG=1              # pgvector embeddings (база)
PROJECT_EMBED_MODEL=text-embedding-3-small
PROJECT_EMBED_DIMS=1536
PROJECT_HYBRID_SEARCH=1           # RRF: FTS + vector
PROJECT_ADAPTIVE_TOPK=1           # динамический top_k (8/12/20)
PROJECT_CONV_SEARCH=1             # conversation-aware запрос
PROJECT_QUERY_EXPANSION=0         # LLM expansion (доп. стоимость)
PROJECT_RERANK=0                  # CPU cross-encoder (доп. CPU)
PROJECT_TWO_LEVEL=0               # two-level file→chunk (по метрикам)
PROJECT_SMART_CHUNK=1             # чанкинг по границам функций/классов
PROJECT_FILE_PIN=1                # @file директива
PROJECT_WEB_SEARCH=1              # @web директива (Tavily)

# Коллаборация и безопасность
PROJECT_COLLAB=1                  # соавторы: viewer/editor
PROJECT_PUBLIC_HARDENING=1        # throttle+кэш публичных Spaces
PROJECT_AUDIT_LOG=1               # per-project audit log
PROJECT_FILE_VERSIONS=1           # история версий файлов
PROJECT_SYNC_POLLING=1            # polling-fallback синка (beat)
PROJECT_CODEBASE=1                # @codebase: семантика по repo-файлам
PROJECT_PR_PROPOSALS=1            # PR-режим вместо прямого коммита

# Внешние ключи
TAVILY_API_KEY=<ключ>
```

---

## Диагностика

| Симптом | Проверить |
|---------|-----------|
| Файл не попадает в RAG | `embed_status` в `/files/`; кнопка «Повторить» → `POST /files/<id>/reembed/` |
| Синк репо завис | `connector.sync_status`; Celery-лог `sync_connector_task` |
| Коммит не пушится | `ProjectCommit.status = 'failed'`; Celery-лог `push_project_commit` |
| Публичный Space 404 | `project.is_public=True` и `public_slug` не пустой |
| Дублирование файлов в контексте | Дедуп по `file_id` в `build_project_knowledge_context` (исправлено 2026-06-22) |
| Web-поиск → ошибка в проекте | Контекст-гард: при total ctx >30K символов, поиск обрезается до 2000 символов |
