# PROJECT SPACES — План реализации

Апгрейд фичи **«Проекты»** до полноценных **«Project Spaces»** по аналогии с
Claude.ai Projects, Perplexity Spaces и ChatGPT Projects.

Цель: проект становится не просто папкой для чатов, а рабочим пространством со
своей **базой знаний** (файлы), **инструкциями** (system prompt) и
**подключённым git-репозиторием** (GitHub / Gitea), который AI читает и в который
предлагает коммиты.

---

## 0. Что уже работает (не переписываем)

Прежде чем планировать новое — фиксируем, что значительная часть фундамента
**уже есть** в кодовой базе.

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

**Вывод:** Для Gitea-коннектора **писать новый git-слой не нужно** — переиспользуем
эти функции. Нужны лишь две новые: листинг дерева файлов (`GET .../contents/`)
и работа с GitHub API (для внешних репозиториев).

### 0.3. Инфраструктура извлечения текста из файлов УЖЕ есть

`src/aitext/file_utils.py` → `extract_text_from_file(file_path, original_filename, file_data=None)`
плюс специализированные парсеры: `extract_text_from_pdf`, `extract_text_from_docx`,
`extract_text_from_txt`, `extract_text_from_excel`, `extract_text_from_pptx`,
`extract_text_from_archive`.

`FileAttachment` (`src/aitext/models.py`, строка 304) уже хранит результат в поле
`extracted_text` (TextField). UUID PK, choices `media_type` (image/video/audio/pdf/other).

**Вывод:** База знаний проекта переиспользует ровно тот же конвейер извлечения.
Новая модель `ProjectFile` хранит метаданные + `extracted_text`, а инжект текста
в контекст — это +5 строк рядом с уже существующим инжектом system prompt.

### 0.4. Persistent Memory работает

В `tasks.py` уже собирается `memory_ctx` (`build_memory_context`), история сжимается
(`get_history_with_compression`, `should_compress`). Контекст проекта (файлы) встаёт
в ту же сборку `messages_for_api` — между system prompt и историей.

### 0.5. Текущая модель Project

`src/aitext/models.py`, строка 213:

```python
class Project(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='projects')
    name = models.CharField(max_length=100)
    system_prompt = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#0a7cff')
    icon = models.CharField(max_length=30, default='Folder')
    created_at = models.DateTimeField(auto_now_add=True)
```

`Chat.project` — FK с `on_delete=SET_NULL`. API: `ProjectListCreateView`,
`ProjectDetailView` (`src/api/views/projects.py`, маршруты `v1/projects/` и
`v1/projects/<pk>/` в `src/api/urls.py`, строки 142–143).

---

## ФАЗА 1 — База знаний проекта (Project Files)

Пользователь загружает файлы в проект (PDF, .md, .txt, код), AI автоматически
ссылается на них в **каждом** чате внутри проекта.

### 1.1. Модель `ProjectFile`

Новая модель в `src/aitext/models.py` (рядом с `Project`). Переиспользуем тот же
конвейер извлечения, что и `FileAttachment`, но привязка — к проекту, а не к сообщению.

```python
class ProjectFile(models.Model):
    """Файл базы знаний проекта. Извлечённый текст инжектится в контекст всех чатов проекта."""
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='files', verbose_name='Проект'
    )
    filename = models.CharField(max_length=255, verbose_name='Имя файла')
    file_path = models.CharField(max_length=500, verbose_name='Путь к файлу')
    file_size = models.IntegerField(verbose_name='Размер (байты)')
    mime_type = models.CharField(max_length=100, blank=True, verbose_name='MIME тип')

    # Результат extract_text_from_file() — тот же конвейер, что у FileAttachment
    extracted_text = models.TextField(blank=True, null=True, verbose_name='Извлечённый текст')
    char_count = models.IntegerField(default=0, verbose_name='Кол-во символов')

    # Стратегия инжекта: full = целиком в контекст; rag = по релевантности (Фаза 1.5)
    INJECT_MODES = [('full', 'Целиком'), ('rag', 'По релевантности')]
    inject_mode = models.CharField(max_length=10, choices=INJECT_MODES, default='full')

    enabled = models.BooleanField(default=True, verbose_name='Активен')
    status = models.CharField(
        max_length=20, default='processing',
        choices=[('processing', 'Обработка'), ('ready', 'Готов'), ('failed', 'Ошибка')],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Файл проекта'
        verbose_name_plural = 'Файлы проектов'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.project.name} — {self.filename}"
```

**Миграция:** `python manage.py makemigrations aitext` → одна аддитивная миграция,
только новая таблица + индекс по `project`. Существующие данные не трогаются.

### 1.2. API-эндпоинты

Новый view-файл `src/api/views/project_files.py` + регистрация в `src/api/urls.py`:

```
GET    v1/projects/<pk>/files/            — список файлов проекта
POST   v1/projects/<pk>/files/            — загрузить файл (multipart)
DELETE v1/projects/<pk>/files/<file_id>/  — удалить файл
PATCH  v1/projects/<pk>/files/<file_id>/  — toggle enabled / сменить inject_mode
```

Загрузка переиспользует логику `src/api/views/uploads.py` (`ChatFileUploadView`):
сохранение файла в `media/`, вызов `extract_text_from_file()`. Извлечение текста для
крупных PDF/архивов выносим в **Celery-задачу** `process_project_file.delay(file_id)`
(`src/aitext/tasks.py`), чтобы не блокировать HTTP-запрос. Пока задача не завершилась —
`status='processing'`; фронт показывает спиннер и поллит список.

Проверки: владелец проекта = `request.user`; лимит файлов на проект (напр. 20);
лимит суммарного размера (напр. 50 МБ) — конфиг в `settings.py`.

### 1.3. Критический момент — инжект в контекст (tasks.py)

Главное изменение Фазы 1 — **5 строк** рядом с уже работающим инжектом system prompt.
В `src/aitext/tasks.py`, сразу после блока «1. Project system prompt» (строка 304):

```python
# 1. Project system prompt (если есть)
if chat.project_id:
    try:
        proj = Project.objects.get(id=chat.project_id)
        if proj.system_prompt:
            messages_for_api.append({"role": "system", "content": proj.system_prompt})

        # 1b. База знаний проекта (Project Files)
        kb_block = build_project_knowledge_context(proj, user_msg)  # см. ниже
        if kb_block:
            messages_for_api.append({"role": "system", "content": kb_block})
    except Exception:
        pass
```

Новая функция `build_project_knowledge_context(proj, user_msg)` (в `src/aitext/tasks.py`
или отдельном `src/aitext/project_context.py`):

```python
FULL_INJECT_LIMIT = 50_000  # символов на файл — ГРАНИЦА FULL ↔ RAG

def build_project_knowledge_context(proj, user_msg) -> str:
    """Собирает блок знаний проекта для system-сообщения."""
    files = proj.files.filter(enabled=True, status='ready')
    if not files:
        return ''

    parts = []
    for f in files:
        text = f.extracted_text or ''
        if f.char_count <= FULL_INJECT_LIMIT:
            # FULL: маленький файл — целиком
            parts.append(f"### Файл: {f.filename}\n{text}")
        else:
            # RAG-граница: крупный файл — только релевантные фрагменты
            snippet = retrieve_relevant_chunks(text, query=user_msg.plain_text, top_k=5)
            parts.append(f"### Файл: {f.filename} (фрагменты)\n{snippet}")

    body = "\n\n".join(parts)
    return (
        "Ниже — материалы базы знаний этого проекта. "
        "Используй их как источник истины при ответах.\n\n" + body
    )
```

### 1.4. ГРАНИЦА FULL-INJECT ↔ RAG (явно)

Это ключевое архитектурное решение Фазы 1:

- **Файл ≤ 50 000 символов (`FULL_INJECT_LIMIT`)** → инжектится **целиком**.
  Просто, надёжно, без эмбеддингов. Покрывает 90% реальных случаев (md, txt,
  небольшие PDF, файлы кода).
- **Файл > 50 000 символов** → **RAG-граница**: текст режется на чанки, по запросу
  пользователя извлекаются top-k релевантных фрагментов (`retrieve_relevant_chunks`).

**Важно для MVP:** на старте `retrieve_relevant_chunks` реализуется **без векторной БД** —
простой лексический отбор (BM25 / пересечение по ключевым словам через `rapidfuzz`
или встроенный TF-подсчёт). Это снимает зависимость от pgvector/эмбеддингов в первом
релизе. Векторный RAG (эмбеддинги через laozhang.ai + pgvector) — отдельный
инкремент **Фазы 1.5**, когда появится спрос на большие документы.

Суммарный размер инжекта ограничиваем сверху (`max_input_tokens` сети уже учитывается
ниже в `tasks.py` при сборке истории) — если знаний больше бюджета, режем по приоритету
(сначала enabled-файлы по дате, RAG-фрагменты вместо full).

### 1.5. Frontend (Фаза 1)

- `frontend/app/projects/` — вкладка **«Файлы»** в настройках проекта.
- Drag&drop загрузка, список файлов с размером, статусом (обработка/готов/ошибка),
  тумблером `enabled`, кнопкой удаления. Иконки — **только Lucide React**
  (`FileText`, `Upload`, `Trash2`, `Loader2`), без эмодзи.
- API-клиент: добавить методы в `frontend/lib/api/` (рядом с существующими project-методами).
- В окне чата — бейдж «База знаний: N файлов» рядом с индикатором инструкций (см. Фаза 2).

---

## ФАЗА 2 — UX инструкций проекта (System Instructions)

Бэкенд **уже работает** (см. 0.1). Это чисто фронтенд-задача: сделать `system_prompt`
видимым и удобным.

**Изменений в бэкенде НЕТ.** `system_prompt` уже в модели `Project`, уже сохраняется
через `ProjectDetailView` (PATCH), уже инжектится в `tasks.py`.

### Frontend (`frontend/app/projects/`)

1. **Отдельная вкладка «Инструкции»** в настройках проекта (вместо узкого поля).
2. Полноразмерный textarea-редактор с **счётчиком символов** и мягким лимитом
   (напр. предупреждение на 4000 символов — это контекстный бюджет).
3. **Превью** — рендер markdown инструкции (переиспользуем `react-markdown`,
   который уже стоит для чата).
4. **Индикатор в чате**: когда чат принадлежит проекту с непустым `system_prompt` —
   показывать ненавязчивый бейдж «Инструкции проекта активны» (Lucide `Sparkles`/`Info`),
   по клику — popover с текстом инструкции (read-only).
5. Подсказки-шаблоны инструкций («Тон ответов», «Формат», «Роль»).

---

## ФАЗА 3 — Git-коннектор (GitHub / Gitea)

Подключение GitHub-репозитория или существующего Gitea-репо к проекту. AI читает
файлы репозитория по запросу и **предлагает коммиты** → пользователь одобряет →
коммит пушится.

### 3.1. Модель `ProjectConnector`

`src/aitext/models.py`:

```python
class ProjectConnector(models.Model):
    """Подключённый git-репозиторий проекта (GitHub или Gitea)."""
    TYPES = [('github', 'GitHub'), ('gitea', 'Gitea')]

    project = models.OneToOneField(
        Project, on_delete=models.CASCADE, related_name='connector', verbose_name='Проект'
    )
    type = models.CharField(max_length=10, choices=TYPES)
    repo_url = models.URLField(verbose_name='URL репозитория')
    owner = models.CharField(max_length=200, verbose_name='Владелец (owner)')
    repo = models.CharField(max_length=200, verbose_name='Имя репозитория')
    default_branch = models.CharField(max_length=100, default='main')

    # Токен доступа. ХРАНИМ ЗАШИФРОВАННЫМ (Fernet, ключ из settings)
    access_token = models.TextField(verbose_name='Токен доступа (encrypted)')

    connected_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Git-коннектор проекта'
        verbose_name_plural = 'Git-коннекторы проектов'
```

**Безопасность токена:** `access_token` шифруется через `cryptography.Fernet`
(ключ — из `settings.SECRET_KEY`-производного или отдельной env-переменной
`PROJECT_CONNECTOR_FERNET_KEY`). В API наружу токен **никогда** не отдаётся (write-only
в сериализаторе).

### 3.2. Модель `ProjectCommit`

```python
class ProjectCommit(models.Model):
    """Предложенный AI коммит, ожидающий подтверждения пользователя."""
    STATUSES = [
        ('pending', 'Ожидает подтверждения'),
        ('approved', 'Одобрен'),
        ('rejected', 'Отклонён'),
        ('pushed', 'Запушен'),
        ('failed', 'Ошибка'),
    ]
    connector = models.ForeignKey(
        ProjectConnector, on_delete=models.CASCADE, related_name='commits'
    )
    message = models.CharField(max_length=500, verbose_name='Сообщение коммита')
    branch = models.CharField(max_length=100, default='main')

    # {"path/to/file.py": "новое содержимое", ...} — формат put_files_batch()
    files = models.JSONField(default=dict, verbose_name='Файлы (path -> content)')

    status = models.CharField(max_length=10, choices=STATUSES, default='pending')
    git_sha = models.CharField(max_length=64, blank=True, verbose_name='SHA после пуша')
    error = models.TextField(blank=True)

    created_by_message = models.ForeignKey(
        'Message', on_delete=models.SET_NULL, null=True, blank=True,
        help_text='Сообщение чата, в котором AI предложил коммит',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
```

Формат `files` (`{path: content}`) совпадает с сигнатурой
`gitea_client.put_files_batch(owner, repo, files, message, branch)` — пуш получается
тривиальным.

**Миграция:** одна аддитивная миграция `aitext` — две новые таблицы.

### 3.3. API-эндпоинты

`src/api/views/connectors.py` + маршруты в `src/api/urls.py`.

> **Решение по адресации:** `ProjectConnector` — это `OneToOne` к проекту (один
> репозиторий на проект), поэтому коннектор адресуется через `<pk>` проекта, а не
> через отдельный `{id}` коннектора. Если в будущем понадобится несколько репо на
> проект — меняем на `ForeignKey` и добавляем `connectors/<connector_id>/...`.

```
POST   v1/projects/<pk>/connectors/                      — подключить репо (type, repo_url, token)
GET    v1/projects/<pk>/connectors/                      — текущий коннектор (без токена)
DELETE v1/projects/<pk>/connectors/                      — отключить

GET    v1/projects/<pk>/connectors/read-files/?path=...  — листинг / чтение файлов репо
POST   v1/projects/<pk>/connectors/propose-commit/       — AI предлагает коммит → ProjectCommit(pending)
POST   v1/projects/<pk>/connectors/confirm-commit/       — {commit_id, action: approve|reject}
GET    v1/projects/<pk>/connectors/commits/              — список pending/прошлых коммитов
```

#### read-files
- **Gitea**: переиспользуем `gitea_client.get_file_content(owner, repo, path, ref)`.
  Для листинга дерева добавляем **одну** новую функцию `list_files(owner, repo, path='', ref)`
  → `GET /repos/{owner}/{repo}/contents/{path}` (Gitea и GitHub имеют почти идентичный
  contents-API).
- **GitHub**: новый тонкий клиент `src/aitext/github_client.py` с `get_file_content` и
  `list_files` через `https://api.github.com/repos/{owner}/{repo}/contents/...`
  (Bearer-токен из расшифрованного `access_token`). Кладём рядом с `gitea_client.py`
  по аналогии.

#### propose-commit
Создаёт `ProjectCommit(status='pending')` с предложенными файлами. **Ничего не пушит.**
Источник предложения — ответ AI в чате: парсим FILE-блоки из ответа модели (как уже
делает Studio-пайплайн при валидации FILE_BLOCKS). Возвращаем diff для предпросмотра.

#### confirm-commit
- `action=reject` → `status='rejected'`, ничего не пушится.
- `action=approve` → `status='approved'`, запускаем Celery-задачу
  `push_project_commit.delay(commit_id)`.

### 3.4. Celery-задача пуша

`src/aitext/tasks.py`:

```python
@shared_task(bind=True, max_retries=3)
def push_project_commit(self, commit_id):
    commit = ProjectCommit.objects.select_related('connector').get(id=commit_id)
    conn = commit.connector
    token = decrypt_token(conn.access_token)
    try:
        if conn.type == 'gitea':
            res = gitea_client.put_files_batch(
                conn.owner, conn.repo, commit.files, commit.message, commit.branch,
            )
        else:  # github
            res = github_client.put_files_batch(
                conn.owner, conn.repo, commit.files, commit.message, commit.branch, token,
            )
        commit.git_sha = res.get('sha', '')
        commit.status = 'pushed'
        commit.save()
    except Exception as e:
        commit.status = 'failed'
        commit.error = str(e)
        commit.save()
        raise self.retry(exc=e, countdown=60)
```

Для Gitea токен уже есть на уровне сервера (`STUDIO_GITEA_ADMIN_TOKEN`); для
пользовательских GitHub-репо токен берётся из расшифрованного `access_token`.
`github_client.put_files_batch` реализует пакетный коммит через GitHub Git Data API
(create blob → tree → commit → update ref) либо последовательные contents-PUT для MVP.

### 3.5. Frontend (Фаза 3)

`frontend/app/projects/` + `frontend/lib/api/`:

1. **Панель «Подключить репозиторий»**: выбор типа (GitHub/Gitea), URL, PAT-токен
   (инструкция, какие scope нужны). Lucide `Github`, `GitBranch`, `KeyRound`.
2. **Браузер файлов репо**: дерево (read-files), просмотр содержимого read-only.
3. **Список pending-коммитов**: для каждого — сообщение, diff по файлам,
   кнопки «Одобрить» / «Отклонить» (confirm-commit). После approve — статус
   обновляется до «Запушен» (поллинг или SSE).
4. Бейдж в чате «Репозиторий подключён: owner/repo».

---

## Спринт-разбивка

| Спринт | Содержание | Сложность |
|--------|-----------|-----------|
| **Спринт 1 — База знаний** | Модель `ProjectFile` + миграция; эндпоинты files (CRUD); Celery `process_project_file`; функция `build_project_knowledge_context` + инжект в `tasks.py`; FULL-граница 50 КБ (лексический отбор для крупных, без векторов); вкладка «Файлы» на фронте | **M** |
| **Спринт 2 — Инструкции UX** | Вкладка «Инструкции» (textarea + счётчик + markdown-превью); индикатор активных инструкций в чате; шаблоны. Бэкенд — 0 изменений | **S** |
| **Спринт 3 — Git-коннектор** | Модели `ProjectConnector` + `ProjectCommit` + миграция; шифрование токена (Fernet); `github_client.py` + `list_files` для Gitea; эндпоинты connectors / read-files / propose-commit / confirm-commit; Celery `push_project_commit`; фронт: панель подключения, браузер файлов, список pending-коммитов | **L** |

Доп. инкремент вне основных спринтов:
- **Фаза 1.5 — Векторный RAG** (эмбеддинги laozhang.ai + pgvector) для документов
  > 50 КБ. Подключается прозрачно за `inject_mode='rag'`. **Сложность M.**

---

## Оценка реализуемости (вердикт)

| Компонент | Вердикт | Обоснование |
|-----------|---------|-------------|
| **Project Files (база знаний)** | **ДА** | Конвейер извлечения (`extract_text_from_file`) и хранение (`extracted_text`) уже есть. Инжект — +5 строк рядом с рабочим инжектом system prompt в `tasks.py:297`. Новая модель + один Celery-таск. Риск минимальный. |
| **Инжект в контекст** | **ДА** | Точка вставки уже существует и проверена (`messages_for_api.append`). Бюджет токенов учитывается ниже по коду через `max_input_tokens`. Добавляем один system-блок. |
| **FULL ↔ RAG граница** | **ДА** | MVP — без векторной БД: full-inject ≤ 50 КБ + лексический отбор для крупных. Снимает зависимость от pgvector в первом релизе. Векторный RAG — изолированный инкремент за флагом `inject_mode`. |
| **Instructions UX** | **ДА (тривиально)** | Бэкенд уже работает на 100%. Чисто фронтенд: вкладка, счётчик, превью, индикатор. Нулевой риск регрессий. |
| **Git-коннектор (Gitea)** | **ДА** | `gitea_client.py` уже покрывает чтение (`get_file_content`) и пуш (`put_files_batch`). Нужна **одна** новая функция `list_files`. Формат `ProjectCommit.files` совпадает с `put_files_batch`. |
| **Git-коннектор (GitHub)** | **ДА (с оговоркой)** | Требует нового тонкого клиента `github_client.py` (contents-API + Git Data API для batch). Объём — небольшой, API хорошо документирован. Основной риск — безопасность хранения PAT: решается шифрованием Fernet + write-only в сериализаторе. |
| **Propose → approve → push** | **ДА** | Паттерн «pending → approve → Celery push» уже знаком кодовой базе (Studio коммитит так же). Парсинг FILE-блоков из ответа AI переиспользует логику валидации Studio-пайплайна. |

### Общий вердикт: **РЕАЛИЗУЕМО.**

Все три фичи опираются на уже существующую инфраструктуру (извлечение текста, инжект
system prompt, Gitea-клиент, Celery, паттерн pending-коммитов из Studio). Новый код —
преимущественно модели, тонкие API-вью и фронтенд. Самый объёмный и единственный
по-настоящему новый кусок — `github_client.py` и шифрование токенов в Фазе 3.

**Рекомендуемый порядок:** Спринт 2 (Инструкции, быстрая победа без бэкенда) →
Спринт 1 (База знаний, ядро ценности) → Спринт 3 (Git-коннектор, самый объёмный).

---

## Файлы, которые меняем / создаём

**Backend:**
- `src/aitext/models.py` — модели `ProjectFile`, `ProjectConnector`, `ProjectCommit`
- `src/aitext/migrations/00XX_project_spaces.py` — аддитивные миграции
- `src/aitext/tasks.py` — `build_project_knowledge_context`, инжект (≈стр. 304),
  Celery `process_project_file`, `push_project_commit`
- `src/aitext/project_context.py` *(новый, опц.)* — сборка контекста знаний + RAG-отбор
- `src/aitext/github_client.py` *(новый)* — GitHub contents / Git Data API
- `src/studio/gitea_client.py` — добавить `list_files(owner, repo, path, ref)`
- `src/api/views/project_files.py` *(новый)* — CRUD файлов проекта
- `src/api/views/connectors.py` *(новый)* — коннекторы, read-files, propose/confirm-commit
- `src/api/urls.py` — регистрация новых маршрутов под `v1/projects/<pk>/...`
- `src/config/settings.py` — лимиты файлов проекта, `PROJECT_CONNECTOR_FERNET_KEY`

**Frontend:**
- `frontend/app/projects/` — вкладки «Файлы», «Инструкции», «Репозиторий»
- `frontend/lib/api/` — клиентские методы (project files, connectors, commits)
- `frontend/app/chat/` — индикаторы «Инструкции активны» / «База знаний» / «Репо подключён»
