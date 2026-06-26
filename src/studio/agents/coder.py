import re
import logging

from django.conf import settings
from .base import BaseAgent, pick_prompt
from ..models_catalog import ESCALATION_MAP, MODEL_TIER
from .blocks import parse_file_blocks, FILE_CLOSE

log = logging.getLogger('studio.agents')

FILE_SYSTEM_TMA = (
    "Ты senior-разработчик Telegram Mini App (Vite + React + TypeScript + @twa-dev/sdk).\n"
    "Напиши ОДИН ПОЛНЫЙ исходный файл для TMA.\n"
    "TMA-правила:\n"
    "- В App.tsx: первая строка useEffect() — WebApp.ready(); вторая — WebApp.expand()\n"
    "- Тема: читай WebApp.colorScheme, применяй через CSS-переменные Telegram (--tg-theme-bg-color и т.д.)\n"
    "- Никогда не используй window.location.href для навигации внутри Mini App\n"
    "- package.json: @twa-dev/sdk, react ^18, vite ^6, @vitejs/plugin-react\n"
    "- vite.config.ts: server:{host:true,port:3000,hmr:false}, base:'./'\n"
    "- validate_tma_init_data.py: HMAC-SHA256 с секретом WebAppData (обязательно на сервере!)\n"
    "- Если платежи: WebApp.openInvoice(invoiceUrl, callback) — не Stripe, не ЮКасса\n"
    "Общие требования:\n"
    "- Файл 100% полный, без TODO, без заглушек\n"
    "- Выводи ТОЛЬКО содержимое файла — без markdown-блоков, без объяснений\n"
)

# ── System prompts ────────────────────────────────────────────────────────────

MANIFEST_SYSTEM_RU = (
    "Ты senior-разработчик. По шагу из COMMITS.md определи список файлов для создания/изменения.\n"
    "Верни СТРОГО JSON: {\"files\": [\"relative/path/file.ext\", ...]}\n"
    "Только файлы напрямую затронутые этим шагом. Без объяснений."
)

MANIFEST_SYSTEM_EN = (
    "You are a senior developer. For one step from COMMITS.md, list all files to create or modify.\n"
    "Return STRICTLY JSON: {\"files\": [\"relative/path/file.ext\", ...]}\n"
    "Only files directly created or modified in THIS step. No explanations."
)

FILE_SYSTEM_RU = (
    "Ты senior-разработчик. Напиши ОДИН ПОЛНЫЙ исходный файл. НИКОГДА не обрезай.\n"
    "Обязательные требования:\n"
    "- Файл 100% полный: все JSX-теги закрыты, все функции закрыты, export default присутствует\n"
    "- Production-ready: полная функциональность, обработка всех состояний (loading, error, empty)\n"
    "- НЕ пиши TODO, заглушки или placeholder-комментарии\n"
    "- Реализуй ВСЕ элементы UI: навигацию, кнопки, иконки, стили — всё как в настоящем продукте\n"
    "- Next.js: 'use client' там где нужно; dev-скрипт: \"next dev -p 3000 -H 0.0.0.0\"\n"
    "- Vite/React: vite.config.ts с server:{host:true,port:3000,hmr:false}\n"
    "- MOCK-ДАННЫЕ: если проект использует БД или API — создай src/lib/mock-data.ts с 10-20 реалистичными\n"
    "  записями. В компонентах/роутах используй как fallback: если env-переменная БД не задана — возвращай mock.\n"
    "- Выводи ТОЛЬКО содержимое файла — без markdown-блоков, без объяснений\n"
    "Код-комментарии можно на русском."
)

FILE_SYSTEM_EN = (
    "You are a senior software engineer. Write ONE COMPLETE source file. NEVER truncate.\n"
    "Mandatory requirements:\n"
    "- 100% complete: ALL JSX tags closed, ALL functions closed, export default present\n"
    "- Production-ready: full functionality, handle all states (loading, error, empty, success)\n"
    "- NO TODO comments, stubs, or placeholder code — real implementation only\n"
    "- Implement ALL UI elements: navigation, buttons, icons, styles — everything a real product needs\n"
    "- Next.js: add 'use client' where needed; dev script: \"next dev -p 3000 -H 0.0.0.0\"\n"
    "- Vite/React: vite.config.ts with server:{host:true,port:3000,hmr:false}\n"
    "- MOCK DATA: if the project uses a database or external API — create src/lib/mock-data.ts with\n"
    "  10-20 realistic records. Use as fallback in components/routes when DB env var is not set.\n"
    "- Output ONLY the raw file content — no markdown fences, no explanations\n"
    "Code comments may be in Russian."
)

# Legacy single-call prompts
SYSTEM_RU = (
    "Ты senior-разработчик. Реализуй РОВНО ОДИН шаг из COMMITS.md. "
    "Пиши production-ready код: типобезопасный, без TODO, с обработкой ошибок и состояний загрузки. "
    "Для Vite: vite.config.ts с server:{host:true,port:3000}. "
    "Для Next.js: dev-скрипт \"next dev -p 3000 -H 0.0.0.0\". "
    "Не выдумывай несуществующие зависимости. Не дублируй существующие файлы. "
    "Если задан FixPlan — меняй ТОЛЬКО указанные файлы. "
    "Верни СТРОГО JSON: {\"files\":{\"путь\":\"полное содержимое файла\"}}. Полные файлы целиком, не диффы."
)

SYSTEM_EN = (
    "You are a senior software engineer. Implement EXACTLY ONE step from COMMITS.md. "
    "Write production-ready code: type-safe, no TODO stubs, with error handling and loading states. "
    "For Vite/React/Vue projects, always include in vite.config.ts: "
    "server: { host: true, port: 3000, hmr: false } "
    "For Next.js projects: ALWAYS set package.json scripts.dev to \"next dev -p 3000 -H 0.0.0.0\". "
    "Never invent nonexistent dependencies. If a FixPlan is provided, change ONLY the listed files. "
    "Return STRICTLY JSON: {\"files\":{\"relative/path\":\"full file content\"}} — whole files, never diffs. "
    "Code comments may be in Russian."
)


# ── V3 FILE_BLOCKS prompts ────────────────────────────────────────────────────

CODER_FILE_BLOCKS_RU = (
    "Ты senior-разработчик. Напиши ОДИН полный файл в формате FILE_BLOCKS.\n\n"
    "ФОРМАТ ВЫВОДА СТРОГО:\n"
    "=== FILE: <путь> ===\n"
    "<полное содержимое файла>\n"
    "=== END FILE ===\n\n"
    "Маркер === END FILE === ОБЯЗАТЕЛЕН в конце — это сигнал завершения файла.\n"
    "НЕ используй JSON. НЕ оборачивай код в markdown-fences (```).\n\n"
    "ТРЕБОВАНИЯ:\n"
    "- Файл 100% полный и production-ready: все JSX-теги закрыты, все функции закрыты, export присутствует.\n"
    "- НЕ обрезай. НЕ пиши TODO, заглушки или placeholder-комментарии.\n"
    "- Реализуй ВСЕ элементы UI: навигацию, кнопки, иконки, стили.\n"
    "- Обработай состояния: loading, empty, error.\n"
    "- Next.js: 'use client' там где нужно; dev-скрипт: \"next dev -p 3000 -H 0.0.0.0\".\n"
    "- Vite/React: vite.config.ts с server:{host:true,port:3000,hmr:false}.\n"
    "- MOCK-ДАННЫЕ: если проект использует БД или API — создай src/lib/mock-data.ts с 10-20 реалистичными\n"
    "  записями. В компонентах/роутах используй их как fallback: если env-переменная БД не задана —\n"
    "  возвращай mock-данные. Это нужно чтобы превью работало без настройки инфраструктуры.\n"
    "Комментарии в коде можно на русском."
)
CODER_FILE_BLOCKS_EN = (
    "You are a senior software engineer. Write ONE complete source file in FILE_BLOCKS format.\n\n"
    "OUTPUT FORMAT STRICTLY:\n"
    "=== FILE: <path> ===\n"
    "<full file content>\n"
    "=== END FILE ===\n\n"
    "The marker === END FILE === is MANDATORY at the end — it signals completion.\n"
    "Do NOT use JSON. Do NOT wrap the code in markdown fences (```).\n\n"
    "REQUIREMENTS:\n"
    "- 100% complete, production-ready: ALL JSX tags closed, ALL functions closed, export present.\n"
    "- NEVER truncate. NO TODO comments, stubs or placeholders.\n"
    "- Implement ALL UI elements: navigation, buttons, icons, styles.\n"
    "- Handle states: loading, empty, error.\n"
    "- Next.js: add 'use client' where needed; dev script \"next dev -p 3000 -H 0.0.0.0\".\n"
    "- Vite/React: vite.config.ts with server:{host:true,port:3000,hmr:false}.\n"
    "- MOCK DATA: if the project uses a database or external API — create src/lib/mock-data.ts with\n"
    "  10-20 realistic records. In components/routes use them as fallback: if the DB env variable is\n"
    "  not set — return mock data. This ensures preview works without any infrastructure setup.\n"
    "Code comments may be in Russian."
)


_STACK_RULES = {
    "nextjs": (
        "- App Router only: всё в app/, никаких pages/. Не смешивай два роутера в одном проекте.\n"
        "- Серверные компоненты по умолчанию: 'use client' добавляй ТОЛЬКО при useState/useEffect/onClick/браузерных API.\n"
        "- Данные тяни прямо в async серверном компоненте через await fetch()/ORM — не используй useEffect для первичной загрузки серверных данных.\n"
        "- fetch кэшируй осознанно: { cache: 'no-store' } для динамики, { next: { revalidate: N } } для ISR.\n"
        "- Метаданные через export const metadata или export async function generateMetadata() — не вставляй <head>/<title> вручную в JSX.\n"
        "- Картинки через next/image с обязательными width/height; внешние домены добавь в images.remotePatterns в next.config.\n"
        "- Навигация через next/link и useRouter из 'next/navigation' (НЕ из 'next/router').\n"
        "- params и searchParams в page.tsx это Promise (Next 15): объявляй props как Promise и await их.\n"
        "- TypeScript strict: пропсы и возвращаемые типы явно, никаких any.\n"
        "- Route Handlers в app/api/.../route.ts экспортируют именованные GET/POST и возвращают NextResponse."
    ),
    "react": (
        "- Vite + React + TypeScript: точка входа src/main.tsx, корневой App.tsx, index.html в корне проекта.\n"
        "- Хуки только на верхнем уровне компонента: никаких useState/useEffect внутри условий или циклов.\n"
        "- useEffect всегда с корректным массивом зависимостей; для очистки — возвращай cleanup-функцию.\n"
        "- Пропсы типизируй через interface/type без React.FC; деструктурируй пропсы в сигнатуре.\n"
        "- Списки рендери со стабильным key (id сущности), НЕ используй индекс массива как key при изменяемых списках.\n"
        "- Состояние не мутируй напрямую: новые объекты/массивы через спред, обновления-от-предыдущего через setState(prev => ...).\n"
        "- Запросы данных в useEffect обрабатывай loading/error/empty и отменяй гонки через AbortController или флаг ignore.\n"
        "- Оберни рискованные ветки в ErrorBoundary (class-компонент с componentDidCatch).\n"
        "- Стили: CSS Modules (Component.module.css) или Tailwind — выбери один подход на весь проект.\n"
        "- Не обращайся к DOM напрямую: используй useRef вместо document.getElementById."
    ),
    "vue": (
        "- Vite + Vue 3 + TypeScript: только Composition API, каждый компонент через <script setup lang=\"ts\"> (не Options API).\n"
        "- Пропсы через defineProps<{...}>() с TS-дженериком; значения по умолчанию через withDefaults.\n"
        "- События через const emit = defineEmits<{(e:'name', payload:T):void}>() — не вызывай методы родителя напрямую.\n"
        "- ref() для примитивов, reactive() для объектов; производные через computed(), не пересчитывай вручную.\n"
        "- В <script> обращайся к ref через .value; в <template> .value не нужен.\n"
        "- Не деструктурируй reactive-объект (теряется реактивность) — используй toRefs() при необходимости.\n"
        "- v-for всегда с :key по стабильному id; не сочетай v-for и v-if на одном элементе.\n"
        "- Переиспользуемую логику выноси в композаблы useXxx() в src/composables/.\n"
        "- Двустороннее связывание форм через v-model; для кастомных компонентов — defineModel() (Vue 3.4+).\n"
        "- Сайд-эффекты в onMounted; чистка таймеров/подписок в onUnmounted."
    ),
    "html": (
        "- Чистый HTML5/CSS3/JS без фреймворков и CDN-зависимостей React/Vue.\n"
        "- Семантическая разметка: header/nav/main/section/article/aside/footer вместо сплошных div.\n"
        "- Один <h1> на страницу, корректная иерархия заголовков без пропусков уровней.\n"
        "- Доступность: alt у всех img, label[for] у инпутов, aria-* и role где нужно, видимый :focus-стиль.\n"
        "- CSS-переменные в :root для цветов/отступов/типографики — без хардкода по всему файлу.\n"
        "- Адаптивность: <meta name=\"viewport\">, rem/%/clamp, медиазапросы mobile-first.\n"
        "- JS через <script type=\"module\">; никаких inline-обработчиков onclick= в разметке.\n"
        "- Обработчики через addEventListener, элементы через querySelector; делегирование событий для списков.\n"
        "- Внешние данные через fetch с try/catch и обработкой loading/error/empty в UI.\n"
        "- Внешние ссылки target=\"_blank\" с rel=\"noopener noreferrer\"."
    ),
    "python": (
        "- FastAPI (предпочтительно) + Python 3.11+; запуск: uvicorn main:app --host 0.0.0.0 --port 3000 --reload.\n"
        "- Полные аннотации типов на всех функциях и эндпоинтах; модели данных на Pydantic v2.\n"
        "- Pydantic v2: model_config = ConfigDict(...) вместо class Config; .model_dump()/.model_validate() вместо .dict()/.parse_obj().\n"
        "- Каждый эндпоинт с response_model= в декораторе и явным status_code (201 для создания).\n"
        "- I/O-эндпоинты объявляй async def; не блокируй event loop синхронными вызовами.\n"
        "- CORS обязательно: app.add_middleware(CORSMiddleware, allow_origins=[\"*\"], allow_methods=[\"*\"], allow_headers=[\"*\"]).\n"
        "- Ошибки через raise HTTPException(status_code=..., detail=...), не возвращай голые dict с кодом ошибки.\n"
        "- Конфиг и секреты через pydantic-settings/os.environ, никогда не хардкодь ключи.\n"
        "- Структура: main.py (create app), routers/, models/ (Pydantic); не пихай всё в один файл.\n"
        "- requirements.txt с fastapi, uvicorn[standard], pydantic; версии указывай.\n"
        "- Если Flask: фабрика create_app(), Blueprint'ы, flask-cors, jsonify для ответов."
    ),
    "django": (
        "- Django 5.x; модели с явными типами полей, обязательно __str__ и Meta (ordering/verbose_name).\n"
        "- DRF: ViewSet + ModelSerializer + router в urls.py; serializer с fields= (не '__all__' для записи).\n"
        "- ForeignKey/OneToOne с обязательным on_delete; не редактируй применённые миграции вручную.\n"
        "- settings.py: SECRET_KEY/DEBUG/ALLOWED_HOSTS из окружения; DEBUG=False по умолчанию для прода.\n"
        "- INSTALLED_APPS включает приложения и 'rest_framework'; runserver на 0.0.0.0:3000.\n"
        "- URL-маршрутизация: корневой urls.py с include() приложений; используй name= и path().\n"
        "- Запросы оптимизируй: select_related (FK) и prefetch_related (M2M) против N+1.\n"
        "- Бизнес-логика в моделях/сервисах, а не во вьюхах; вьюхи тонкие.\n"
        "- Чувствительные операции под permission_classes/authentication; не открывай AllowAny по умолчанию.\n"
        "- Не используй objects.all() без пагинации в API — подключи DRF pagination."
    ),
    "telegram_bot": (
        "- python-telegram-bot v20+ (async): ApplicationBuilder().token(BOT_TOKEN).build(), запуск app.run_polling().\n"
        "- BOT_TOKEN строго из os.environ['BOT_TOKEN']; никогда не хардкодь токен в коде.\n"
        "- Все хендлеры async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE); внутри await на всех send/reply.\n"
        "- Регистрация: app.add_handler(CommandHandler('start', start)), MessageHandler(filters.TEXT & ~filters.COMMAND, ...).\n"
        "- FSM-диалоги через ConversationHandler с states/entry_points/fallbacks; выход — ConversationHandler.END.\n"
        "- Состояние пользователя в context.user_data / context.chat_data, не в глобальных переменных.\n"
        "- Инлайн-кнопки: InlineKeyboardMarkup + CallbackQueryHandler; в хендлере await update.callback_query.answer().\n"
        "- Длинный/спецтекст экранируй под parse_mode (MarkdownV2/HTML); следи за разметкой чтобы не падал send.\n"
        "- Для разработки run_polling(); для прода run_webhook(url=...) — не оба одновременно.\n"
        "- Глобальный error handler через app.add_error_handler(...) для логирования и graceful-ответа."
    ),
}


def _is_truncated(content: str) -> bool:
    """Return True if file content looks cut off mid-code."""
    s = content.rstrip()
    if not s:
        return True
    last = s[-1]
    if last not in ('}', ';', '>', "'", '"', ')'):
        return True
    # Brace balance: significantly more opens than closes = likely truncated
    open_b = s.count('{')
    close_b = s.count('}')
    if open_b > close_b + 3:
        return True
    return False


def _select_context_files(step_text: str, existing_files: dict, max_files: int = 8) -> dict:
    """Return files relevant to this step: explicitly mentioned + highest priority."""
    mentioned = []
    for p in existing_files:
        if p in step_text:
            mentioned.append(p)
    for token in re.findall(r'`([^`]+)`', step_text):
        if token in existing_files and token not in mentioned:
            mentioned.append(token)
    # Pad with remaining files up to max_files
    rest = [p for p in existing_files if p not in mentioned]
    selected = mentioned[:max_files] + rest[:max(0, max_files - len(mentioned))]
    return {p: existing_files[p] for p in selected[:max_files]}


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from model output."""
    text = re.sub(r'^```[\w]*\n?', '', text.strip(), flags=re.MULTILINE)
    text = re.sub(r'\n?```\s*$', '', text, flags=re.MULTILINE)
    return text.strip()


class CoderAgent(BaseAgent):
    name = 'coder'
    last_model: str = ''

    def _pick_model(self, step_title: str) -> str:
        base = self.resolve_model()
        if '[COMPLEX]' in (step_title or '') and MODEL_TIER.get(base) in ('fast', 'coder'):
            return ESCALATION_MAP.get(base, base)
        return base

    # ── Phase 1: manifest ─────────────────────────────────────────────────────

    def _get_manifest(self, step_index: int, step_text: str,
                      existing_files: dict, model: str) -> list[str]:
        """Quick call: ask the model which files this step creates/modifies."""
        self.log('Определяю список файлов для генерации...')
        system = pick_prompt(MANIFEST_SYSTEM_RU, MANIFEST_SYSTEM_EN)
        listing = '\n'.join(f'- {p}' for p in existing_files) or '(empty)'
        commits_block = self._commits_block()
        user = (
            f"PROJECT.md:\n{self.project.project_md_content}{commits_block}\n\n"
            f"Step #{step_index}:\n{step_text}\n\n"
            f"Existing project files:\n{listing}"
        )
        try:
            data = self.run_json(system, user, model=model, max_tokens=32000)
            raw = data.get('files', [])
            if isinstance(raw, list) and raw:
                files = [str(f) for f in raw if f]
                self.log(f'Список файлов ({len(files)}): {", ".join(files)}')
                return files
            self.log('Манифест вернул пустой список', level='warning')
        except Exception as exc:
            self.log(f'Манифест не удался: {exc}', level='warning')
            log.warning('coder: manifest call failed (%s)', exc)
        return []

    # ── Phase 2: per-file generation ─────────────────────────────────────────

    def _generate_one_file(self, path: str, step_index: int, step_text: str,
                           existing_files: dict, model: str) -> str:
        """Generate a single file with full context. Returns raw file content."""
        existing_content = existing_files.get(path, '')
        if existing_content:
            if _is_truncated(existing_content):
                existing_str = (
                    f"\n\nIMPORTANT: {path} currently exists but is TRUNCATED/INCOMPLETE. "
                    "Write it COMPLETELY from scratch — do NOT continue or patch the existing content."
                )
            else:
                existing_str = (
                    f"\n\nCurrent content of {path} (modify/replace as needed):\n"
                    f"```\n{existing_content[:10000]}\n```"
                )
        else:
            existing_str = ''

        context = _select_context_files(
            step_text, {k: v for k, v in existing_files.items() if k != path}, max_files=10
        )
        context_str = '\n'.join(
            f'### {p}\n```\n{c[:5000]}\n```' for p, c in context.items()
        )
        listing = '\n'.join(f'- {p}' for p in existing_files) or '(empty)'
        commits_block = self._commits_block()

        is_tma = (
            getattr(settings, 'STUDIO_V4_TMA', False)
            and getattr(self.project, 'target_stack', '') == 'tma'
        )
        if settings.STUDIO_V3:
            system = FILE_SYSTEM_TMA if is_tma else pick_prompt(CODER_FILE_BLOCKS_RU, CODER_FILE_BLOCKS_EN)
            # Per-stack rules (TMA has its own dedicated prompt — skip for it)
            if not is_tma:
                stack = getattr(self.project, 'target_stack', '')
                stack_rules = _STACK_RULES.get(stack, '')
                if stack_rules:
                    system = f"{system}\n\n## Правила стека ({stack}):\n{stack_rules}"
            # V3: добавляем DESIGN.md и лимит строк (если заданы в Коммите 5)
            max_lines, role = self._file_spec(path)
            design = self._design_excerpt()
            design_block = f"\n\nDESIGN.md (соблюдай дизайн-систему):\n{design}" if design else ''
            limit_block = (
                f"\n\nЛИМИТ: файл должен быть <= {max_lines} строк. Роль файла: {role}"
                if role or max_lines else ''
            )
            user = (
                f"PROJECT.md:\n{self.project.project_md_content}{commits_block}\n\n"
                f"Step #{step_index}:\n{step_text}{limit_block}\n\n"
                f"FILE TO WRITE: {path}{existing_str}{design_block}\n\n"
                f"All project files (for reference):\n{listing}\n\n"
                f"Relevant file contents:\n{context_str}\n\n"
                f"Output the file wrapped in:\n=== FILE: {path} ===\n...\n=== END FILE ==="
            )
            on_delta = None
            if settings.STUDIO_V4_STREAMING:
                import time as _time
                from ..events import publish_event
                _buf: dict = {'text': '', 'ts': _time.monotonic()}
                _pid = str(self.project.id)
                _path = path

                def on_delta(chunk_text, _b=_buf, _pp=_pid, _fp=_path):
                    _b['text'] += chunk_text
                    now = _time.monotonic()
                    if len(_b['text']) >= 80 or (now - _b['ts']) >= 0.2:
                        publish_event(_pp, {
                            'type': 'file_delta', 'path': _fp, 'chunk': _b['text'],
                        })
                        _b['text'] = ''
                        _b['ts'] = now

            raw = self.run_prompt_with_continuation(
                system, user, model=model, max_tokens=32000, temperature=0.15,
                stop_marker=FILE_CLOSE, on_delta=on_delta,
            )
            if settings.STUDIO_V4_STREAMING and on_delta is not None:
                from ..events import publish_event as _pub
                if _buf['text']:
                    _pub(str(self.project.id), {
                        'type': 'file_delta', 'path': path, 'chunk': _buf['text'],
                    })
                _pub(str(self.project.id), {'type': 'file_delta_done', 'path': path})
            files, incomplete = parse_file_blocks(raw)
            # per-file: ожидаем ровно один блок; берём по точному пути или единственный
            content = files.get(path)
            if content is None and len(files) == 1:
                content = next(iter(files.values()))
            if content is None:
                self.log(f'FILE_BLOCKS не распарсился для {path}, fallback на сырой текст', level='warning')
                content = _strip_fences(raw)
            if path in incomplete or (len(files) == 1 and incomplete):
                self.log(f'{path}: блок обрезан (нет END-маркера) даже после дозапросов', level='warning')
            return content

        # --- legacy путь (STUDIO_V3=False): голый текст ---
        system = FILE_SYSTEM_TMA if is_tma else pick_prompt(FILE_SYSTEM_RU, FILE_SYSTEM_EN)
        user = (
            f"PROJECT.md:\n{self.project.project_md_content}{commits_block}\n\n"
            f"Step #{step_index}:\n{step_text}\n\n"
            f"FILE TO WRITE: {path}{existing_str}\n\n"
            f"All project files (for reference):\n{listing}\n\n"
            f"Relevant file contents:\n{context_str}"
        )
        legacy_delta = None
        if settings.STUDIO_V4_STREAMING:
            import time as _time2
            from ..events import publish_event as _pub2
            _buf2: dict = {'text': '', 'ts': _time2.monotonic()}
            _pid2 = str(self.project.id)
            _path2 = path

            def legacy_delta(chunk_text, _b=_buf2, _pp=_pid2, _fp=_path2):
                _b['text'] += chunk_text
                now = _time2.monotonic()
                if len(_b['text']) >= 80 or (now - _b['ts']) >= 0.2:
                    _pub2(_pp, {'type': 'file_delta', 'path': _fp, 'chunk': _b['text']})
                    _b['text'] = ''
                    _b['ts'] = now

        raw = self.run_prompt_with_continuation(
            system, user, model=model, max_tokens=32000, temperature=0.15,
            on_delta=legacy_delta,
        )
        if settings.STUDIO_V4_STREAMING and legacy_delta is not None:
            from ..events import publish_event as _pub3
            if _buf2['text']:
                _pub3(str(self.project.id), {
                    'type': 'file_delta', 'path': path, 'chunk': _buf2['text'],
                })
            _pub3(str(self.project.id), {'type': 'file_delta_done', 'path': path})
        return _strip_fences(raw)

    def _file_spec(self, path: str) -> tuple[int, str]:
        """Из interview_data['plan'] достаёт {max_lines, role} для файла, если есть."""
        plan = (self.project.interview_data or {}).get('plan', [])
        for step in plan:
            for f in step.get('files', []):
                if f.get('path') == path:
                    return f.get('max_lines', 200), f.get('role', '')
        return 200, ''

    def _design_excerpt(self) -> str:
        d = getattr(self.project, 'design_md_content', '') or ''
        state = ((getattr(self.project, 'interview_data', {}) or {})).get('design_state')
        if state:
            files_list = ', '.join(state.get('last_step_files', [])) or '—'
            status_icon = '✓ зелёная' if state.get('build_status') == 'green' else '✗ красная'
            state_block = (
                f"\n\n## Прогресс реализации:\n"
                f"- Завершено шагов: {state.get('completed_steps', 0)}\n"
                f"- Файлы последнего шага: {files_list}\n"
                f"- Сборка: {status_icon}"
            )
            return d[:4500] + state_block
        return d[:5000]

    def _commits_summary(self) -> str:
        """Только заголовки шагов плана — вместо полного COMMITS.md при STUDIO_V4_COMMITS_CACHE."""
        import re as _re
        md = getattr(self.project, 'commits_md_content', '') or ''
        titles = _re.findall(r'^##\s+(?:Step|Шаг)\s+\d+[^\n]*', md, _re.MULTILINE)
        return '\n'.join(titles)

    def _commits_block(self) -> str:
        """Возвращает блок контекста COMMITS.md: полный или краткий (по флагу)."""
        if settings.STUDIO_V4_COMMITS_CACHE:
            summary = self._commits_summary()
            return f"\n\nПлан (заголовки шагов):\n{summary}" if summary else ''
        commits_md = getattr(self.project, 'commits_md_content', '') or ''
        return f"\n\nFull implementation plan (COMMITS.md):\n{commits_md}" if commits_md else ''

    def _generate_files(self, file_list: list[str], step_index: int, step_text: str,
                        existing_files: dict, model: str) -> dict:
        """Generate files sequentially, one by one with full context."""
        results: dict[str, str] = {}
        total = len(file_list)
        for i, path in enumerate(file_list):
            self.log(f'Генерирую файл {i + 1}/{total}: {path}')
            try:
                content = self._generate_one_file(
                    path, step_index, step_text, existing_files, model
                )
                if content:
                    results[path] = content
                    log.info('coder: generated %s (%d chars)', path, len(content))
                else:
                    self.log(f'Файл {path} вернул пустой результат', level='warning')
                    log.warning('coder: empty result for %s', path)
            except Exception as exc:
                self.log(f'Ошибка генерации {path}: {exc}', level='warning')
                log.error('coder: failed to generate %s: %s', path, repr(exc))
        return results

    # ── Legacy single-call (primary for normal iterations) ────────────────────

    def _run_legacy(self, step_index: int, step_text: str,
                    existing_files: dict, model: str) -> dict:
        """Single-call approach: full context in one request (streaming prevents timeout)."""
        system = pick_prompt(SYSTEM_RU, SYSTEM_EN)
        full = _select_context_files(step_text, existing_files, max_files=10)
        listing = '\n'.join(f'- {p}' for p in existing_files) or '(empty)'
        body = '\n'.join(f'### {p}\n```\n{c[:6000]}\n```' for p, c in full.items())
        user = (
            f"PROJECT.md:\n{self.project.project_md_content}\n\n"
            f"Step #{step_index}:\n{step_text}\n\n"
            f"All project files:\n{listing}\n\n"
            f"Content of relevant files:\n{body}"
        )
        data = self.run_json(system, user, model=model, max_tokens=32000)
        raw = data.get('files', {})
        files = {}
        for p, c in raw.items():
            if isinstance(c, str):
                files[p] = c
            elif isinstance(c, dict):
                files[p] = c.get('content') or c.get('code') or str(c)
            else:
                files[p] = str(c)
        return files

    # ── Main entry point ──────────────────────────────────────────────────────

    def run(self, step_index: int, step_text: str, existing_files: dict,
            allowed_files: list = None) -> dict:
        model = self._pick_model(step_text)
        self.last_model = model
        self.log(f'Модель: {model}')

        # Fix iteration (allowed_files задан) — всегда per-file, в обоих режимах
        if allowed_files:
            self.log(f'Исправляю {len(allowed_files)} файлов: {", ".join(allowed_files)}')
            log.info('coder step %d fix iter: %d files: %s',
                     step_index, len(allowed_files), allowed_files)
            results = self._generate_files(allowed_files, step_index, step_text, existing_files, model)
            if not results and not settings.STUDIO_V3:
                self.log('Per-file генерация ничего не вернула — пробую одиночный запрос', level='warning')
                return self._run_legacy(step_index, step_text, existing_files, model)
            self.log(f'Готово: {len(results)} файлов')
            return results

        if settings.STUDIO_V3:
            # V3 основной путь: манифест файлов → per-file FILE_BLOCKS
            self.log('V3: получаю список файлов шага...')
            file_list = self._get_manifest(step_index, step_text, existing_files, model)
            if not file_list:
                self.log('Манифест пустой — fallback на одиночный запрос', level='warning')
                return self._run_legacy(step_index, step_text, existing_files, model)
            results = self._generate_files(file_list, step_index, step_text, existing_files, model)
            if not results:
                self.log('Per-file ничего не вернула — fallback на одиночный запрос', level='warning')
                return self._run_legacy(step_index, step_text, existing_files, model)
            self.log(f'Готово (V3 per-file): {len(results)} файлов')
            return results

        # --- legacy путь (STUDIO_V3=False): single-call JSON, идентичен прежнему ---
        self.log('Генерирую все файлы одним запросом...')
        log.info('coder step %d: single-call legacy', step_index)
        try:
            results = self._run_legacy(step_index, step_text, existing_files, model)
            if results:
                self.log(f'Готово: {len(results)} файлов')
                log.info('coder step %d: got %d files from single-call', step_index, len(results))
                return results
        except Exception as exc:
            self.log(f'Одиночный запрос не удался ({exc}) — получаю список файлов', level='warning')
            log.warning('coder step %d: single-call failed (%s) — falling back to per-file', step_index, exc)

        file_list = self._get_manifest(step_index, step_text, existing_files, model)
        if not file_list:
            self.log('Манифест пустой — повторяю одиночный запрос', level='warning')
            log.warning('coder step %d: empty manifest — retrying legacy', step_index)
            return self._run_legacy(step_index, step_text, existing_files, model)

        results = self._generate_files(file_list, step_index, step_text, existing_files, model)
        if not results:
            self.log('Per-file генерация ничего не вернула — повторяю одиночный запрос', level='warning')
            return self._run_legacy(step_index, step_text, existing_files, model)

        self.log(f'Готово (per-file): {len(results)} файлов')
        return results
