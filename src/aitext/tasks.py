import uuid
import os
import re
import base64
import logging
import datetime
import requests as _req
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from openai import OpenAI
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from .models import Message, NeuralNetwork, GeneratedImage, Project, ProjectFile
from .file_utils import prepare_media_for_ai
from .fal_utils import generate_with_falai, validate_and_merge_settings
from users.models import UserSpending
from .code_formatter import CodeFormatter

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r'<[^>]+>')

def _strip_html(text: str) -> str:
    """Удаляет HTML-теги из текста (для передачи в LLM без мусора)."""
    if not text:
        return ''
    return _HTML_TAG_RE.sub('', text).strip()

_client = None

FULL_INJECT_LIMIT = 50_000    # символов на файл — порог full-inject vs лексический RAG
EDIT_HINT_THRESHOLD = 80_000  # файлы крупнее этого — AI получает подсказку про EDIT-блоки

def _get_inject_limit():
    return int(getattr(settings, 'PROJECT_INJECT_LIMIT', 200_000))


# Любое упоминание файла с кодовым расширением в запросе — инжектируем полностью.
# Ищет: tasks.py, src/studio/tasks.py и т.д. Не срабатывает на уже обработанные @file.
_FILE_MENTION_RE = re.compile(
    r'(?<![/@])'
    r'((?:[\w-]+/)*[\w-]+\.(?:py|ts|tsx|js|jsx|html|css|json|yml|yaml|sh|md|go|rs|java|rb|php|sql|xml))'
    r'(?!\w)',
    re.IGNORECASE,
)

# Запрос «дай этот файл» / «напечатай его» без явного имени файла в запросе.
_IMPLICIT_FILE_RE = re.compile(
    r'\b(?:напечатай|дай|покажи|выведи|выдай|дай\s+мне|покажи\s+мне)\b.{0,60}'
    r'\b(?:этот|его|полн\w*|весь|целик\w*|исправл\w*|обновл\w*)',
    re.IGNORECASE | re.DOTALL,
)


def _fetch_from_connector(project, fpath: str) -> str | None:
    """Фетчит файл напрямую из GitHub/Gitea коннектора проекта (как Perplexity).

    Используется как fallback когда файл не найден в KB (не попал в лимит синхронизации).
    Если fpath — частичный путь (studio/tasks.py вместо src/studio/tasks.py),
    пытается найти полный путь через DB (repo_path__endswith).
    """
    try:
        from .sync import _github_file, _gitea_file
        from .crypto import decrypt_token
        from django.db.models import Q
        connector = project.connectors.order_by('created_at').first()
        if not connector:
            return None
        token = decrypt_token(connector.access_token_enc)

        # Если частичный путь — ищем полный repo_path через DB
        full_path = fpath
        if '/' not in fpath or not fpath.startswith('src/'):
            pf_match = project.knowledge_files.filter(
                status='ready', enabled=True
            ).filter(
                Q(repo_path=fpath) | Q(repo_path__endswith='/' + fpath)
            ).first()
            if pf_match:
                full_path = pf_match.repo_path

        if connector.connector_type == 'github':
            content = _github_file(connector, token, full_path)
        else:
            content = _gitea_file(connector, token, full_path)
        logger.info(f'[get_file] fetched "{full_path}" directly from connector ({len(content)} chars)')
        return content
    except Exception as e:
        logger.warning(f'[get_file] direct connector fetch "{fpath}" failed: {e}')
        return None


def _detect_explicit_file_request(query: str) -> list[str]:
    """Находит любые упоминания файлов с расширением в запросе (без @file директив)."""
    if not query:
        return []
    seen: set[str] = set()
    result = []
    for m in _FILE_MENTION_RE.finditer(query):
        fpath = m.group(1)
        if fpath not in seen:
            seen.add(fpath)
            result.append(fpath)
    logger.debug('[get_file] detected file mentions: %s', result)
    return result

AGGREGATE_INJECT_LIMIT = 200_000  # оставляем как fallback-константу; в коде используем _get_inject_limit()


def _retrieve_relevant_chunks(text: str, query: str, chunk_size: int = None, top_k: int = None) -> str:
    """Простой лексический поиск: разбивает текст на чанки, возвращает top_k по пересечению слов с запросом."""
    if chunk_size is None:
        chunk_size = int(getattr(settings, 'PROJECT_CHUNK_SIZE', 500))
    if top_k is None:
        top_k = int(getattr(settings, 'PROJECT_TOP_K', 6))
    if not query:
        return text[:FULL_INJECT_LIMIT]
    chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
    q_words = set(query.lower().split())
    scored = []
    for idx, chunk in enumerate(chunks):
        c_words = set(chunk.lower().split())
        score = len(q_words & c_words)
        scored.append((score, idx, chunk))
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = sorted(scored[:top_k], key=lambda x: x[1])
    return "\n...\n".join(c for _, _, c in top)


def _inject_file(f, user_message_text: str, inject_limit: int, total_chars: int,
                 force_full: bool = False) -> tuple[str, int]:
    """Возвращает (snippet_with_label, chars_added) для одного ProjectFile.

    force_full=True — инжектить весь файл целиком (для явных запросов типа
    «дай полный tasks.py»), игнорируя порог FULL_INJECT_LIMIT.
    Файлы > EDIT_HINT_THRESHOLD получают аннотацию [БОЛЬШОЙ ФАЙЛ] — подсказка AI
    использовать EDIT-блоки вместо полного FILE-блока.
    """
    text = f.extracted_text
    text_len = len(text)
    is_large = text_len > FULL_INJECT_LIMIT
    full_label = (getattr(f, 'repo_path', None) or f.filename)
    if force_full or not is_large:
        snippet = text
        if text_len > EDIT_HINT_THRESHOLD:
            label = (
                f"{full_label} "
                f"[БОЛЬШОЙ ФАЙЛ: {text_len} симв. — для правок используй EDIT-блоки, "
                f"SEARCH копируй дословно из этого текста]"
            )
        else:
            label = full_label
    else:
        snippet = _retrieve_relevant_chunks(text, user_message_text)
        label = f"{full_label} (фрагменты)"
    remaining = inject_limit - total_chars
    if len(snippet) > remaining:
        snippet = snippet[:remaining]
    return f"### {label}\n{snippet}", len(snippet)


def build_project_knowledge_context(project, user_message_text: str = '', recent_context: str = '', current_msg_id: int | None = None) -> tuple[str, list[dict]]:
    """Собирает контекст из файлов базы знаний проекта.

    Phase 4/5 (без флагов Phase 6):
      PROJECT_VECTOR_RAG=1 — векторный поиск по embedded-файлам + лексика по остальным.
      PROJECT_VECTOR_RAG=0 — только лексика.

    Phase 6 (при соответствующих флагах, контракт не изменяется):
      6.4 PROJECT_FILE_PIN     — @file/@web директивы в запросе.
      6.1 PROJECT_HYBRID_SEARCH — RRF-слияние FTS+вектор на уровне чанков.
      6.1 PROJECT_CONV_SEARCH   — conversation-aware запрос (последние N сообщений).
      6.1 PROJECT_ADAPTIVE_TOPK — динамический top_k по типу вопроса.
      6.2 PROJECT_QUERY_EXPANSION — LLM-варианты запроса + RRF.
      6.3 PROJECT_RERANK        — cross-encoder rerank top-50 → top-15.
      6.5 PROJECT_TWO_LEVEL     — двухуровневый ретривал (файл → чанк).
    """
    inject_limit = _get_inject_limit()
    parts = []
    total_chars = 0
    used_file_ids = []

    query = user_message_text or ''

    # ── Sprint 6.4: @file / @web директивы ───────────────────────────────────
    directives = {'files': [], 'web': False, 'clean_query': query}
    if getattr(settings, 'PROJECT_FILE_PIN', False) and query:
        try:
            from .retrieval import parse_context_directives
            directives = parse_context_directives(query)
            query = directives.get('clean_query', query)
        except Exception as e:
            logger.warning(f'[6.4] parse_context_directives failed: {e}')

    # @file: inject pinned files (полный extracted_text, обходит ретривал)
    for fpath in directives.get('files', []):
        if total_chars >= inject_limit:
            break
        try:
            from .models import ProjectFile
            from django.db.models import Q
            pf = (
                project.knowledge_files.filter(status='ready', enabled=True)
                .filter(Q(filename=fpath) | Q(filename__endswith='/' + fpath) | Q(repo_path=fpath) | Q(repo_path__endswith='/' + fpath))
                .first()
            )
            if pf and pf.extracted_text:
                snippet = pf.extracted_text[:inject_limit - total_chars]
                parts.append(f"### @file {fpath}\n{snippet}")
                total_chars += len(snippet)
                if pf.id not in used_file_ids:
                    used_file_ids.append(pf.id)
        except Exception as e:
            logger.warning(f'[6.4] @file "{fpath}" failed: {e}')

    # ── Явные запросы файлов: «дай полный tasks.py», «покажи файл X» ────────
    # Детектируем имена файлов в запросе (без @-префикса) и инжектим полностью.
    # Если fpath — голое имя (tasks.py) и матчей несколько — инжектим все с полными путями,
    # чтобы модель сама разобралась какой нужен.
    _explicit_not_found = []
    for fpath in _detect_explicit_file_request(query):
        if total_chars >= inject_limit:
            break
        try:
            from .models import ProjectFile
            from django.db.models import Q
            matches = list(
                project.knowledge_files.filter(status='ready', enabled=True)
                .filter(Q(filename=fpath) | Q(filename__endswith='/' + fpath) | Q(repo_path=fpath) | Q(repo_path__endswith='/' + fpath))
                .exclude(id__in=used_file_ids)
            )
            if matches:
                for pf in matches:
                    if total_chars >= inject_limit:
                        break
                    if not pf.extracted_text:
                        continue
                    snippet, added = _inject_file(pf, query, inject_limit, total_chars, force_full=True)
                    parts.insert(0, snippet)
                    total_chars += added
                    used_file_ids.append(pf.id)
                    logger.info(f'[get_file] injected from KB "{pf.repo_path}" ({added} chars) project {project.id}')
            else:
                # Файл не в KB (не попал в лимит синка) — фетчим напрямую с GitHub/Gitea
                content = _fetch_from_connector(project, fpath)
                if content:
                    remaining = inject_limit - total_chars
                    snippet = content[:remaining]
                    parts.insert(0, f"### {fpath}\n{snippet}")
                    total_chars += len(snippet)
                    logger.info(f'[get_file] fetched from connector "{fpath}" ({len(snippet)} chars) project {project.id}')
                else:
                    _explicit_not_found.append(fpath)
                    logger.warning(f'[get_file] file "{fpath}" not found anywhere (project {project.id})')
        except Exception as e:
            logger.warning(f'[get_file] explicit file "{fpath}" failed: {e}')

    # Implicit: «напечатай этот» / «дай его» — имя файла не в текущем запросе, но есть в истории
    if not _detect_explicit_file_request(query) and recent_context and _IMPLICIT_FILE_RE.search(query):
        for fpath in _detect_explicit_file_request(recent_context):
            if total_chars >= inject_limit:
                break
            try:
                from .models import ProjectFile
                from django.db.models import Q
                matches = list(
                    project.knowledge_files.filter(status='ready', enabled=True)
                    .filter(Q(filename=fpath) | Q(filename__endswith='/' + fpath) | Q(repo_path=fpath) | Q(repo_path__endswith='/' + fpath))
                    .exclude(id__in=used_file_ids)
                )
                if matches:
                    for pf in matches:
                        if total_chars >= inject_limit:
                            break
                        if not pf.extracted_text:
                            continue
                        snippet, added = _inject_file(pf, query, inject_limit, total_chars, force_full=True)
                        parts.insert(0, snippet)
                        total_chars += added
                        used_file_ids.append(pf.id)
                        logger.info(f'[get_file] implicit inject "{pf.repo_path}" from history ({added} chars)')
                else:
                    content = _fetch_from_connector(project, fpath)
                    if content:
                        remaining = inject_limit - total_chars
                        snippet = content[:remaining]
                        parts.insert(0, f"### {fpath}\n{snippet}")
                        total_chars += len(snippet)
                        logger.info(f'[get_file] implicit fetch "{fpath}" from connector ({len(snippet)} chars)')
            except Exception as e:
                logger.warning(f'[get_file] implicit file "{fpath}" failed: {e}')

    # Если файл явно запрошен но не найден в БД — предупреждаем модель чтобы не генерировала фейк
    if _explicit_not_found:
        not_found_msg = (
            f"ВАЖНО: следующие файлы запрошены пользователем, но НЕ найдены в базе знаний проекта: "
            f"{', '.join(_explicit_not_found)}. "
            "НЕ генерируй содержимое этих файлов из памяти — это приведёт к ошибкам. "
            "Сообщи пользователю что файл не синхронизирован в базу знаний проекта и нужно "
            "обновить синхронизацию в настройках проекта."
        )
        parts.insert(0, not_found_msg)

    # @web: Tavily search
    if directives.get('web') and getattr(settings, 'PROJECT_WEB_SEARCH', False) and query:
        try:
            from .web_search import web_search as _ws
            web_result = _ws(query)
            if web_result and total_chars < inject_limit:
                snippet = web_result[:inject_limit - total_chars]
                parts.append(snippet)
                total_chars += len(snippet)
        except Exception as e:
            logger.warning(f'[6.4] @web failed: {e}')

    # ── Sprint 6.1: Conversation-aware query ─────────────────────────────────
    effective_query = query
    if getattr(settings, 'PROJECT_CONV_SEARCH', False) and query:
        try:
            from .retrieval import build_search_query
            effective_query = build_search_query(project, query, current_msg_id=current_msg_id)
        except Exception as e:
            logger.warning(f'[6.1] build_search_query failed: {e}')

    # ── Sprint 6.1: Adaptive top_k ────────────────────────────────────────────
    if getattr(settings, 'PROJECT_ADAPTIVE_TOPK', False) and effective_query:
        try:
            from .retrieval import adaptive_top_k
            top_k = adaptive_top_k(effective_query)
        except Exception:
            top_k = int(getattr(settings, 'PROJECT_TOP_K', 6))
    else:
        top_k = int(getattr(settings, 'PROJECT_TOP_K', 6))

    # ── Sprint 6.5: Two-level retrieval: file-level filter ────────────────────
    restrict_file_ids = None
    if getattr(settings, 'PROJECT_TWO_LEVEL', False) and effective_query:
        try:
            from .embeddings import file_level_search
            top_files = file_level_search(
                project, effective_query, int(getattr(settings, 'PROJECT_TWO_LEVEL_FILES', 5))
            )
            if top_files:
                restrict_file_ids = [f.id for f in top_files]
        except Exception as e:
            logger.warning(f'[6.5] file_level_search failed: {e}')

    # ── Sprint 6.2: Query expansion ───────────────────────────────────────────
    queries = [effective_query] if effective_query else []
    if getattr(settings, 'PROJECT_QUERY_EXPANSION', False) and effective_query:
        try:
            from .retrieval import expand_query
            expanded = expand_query(effective_query)
            if expanded:
                queries = expanded
        except Exception as e:
            logger.warning(f'[6.2] expand_query failed: {e}')

    # ── Sprint 6.1+6.3: Hybrid search (RRF) + optional rerank ────────────────
    if getattr(settings, 'PROJECT_HYBRID_SEARCH', False) and queries:
        try:
            from .search import hybrid_search
            candidates_n = (
                int(getattr(settings, 'PROJECT_RERANK_CANDIDATES', 50))
                if getattr(settings, 'PROJECT_RERANK', False)
                else top_k
            )
            candidates = hybrid_search(
                project, queries, top_k=candidates_n,
                restrict_file_ids=restrict_file_ids,
            )

            if getattr(settings, 'PROJECT_RERANK', False) and candidates:
                try:
                    from .rerank import rerank
                    candidates = rerank(
                        effective_query, candidates,
                        top_k=int(getattr(settings, 'PROJECT_RERANK_TOPK', 15)),
                    )
                except Exception as e:
                    logger.warning(f'[6.3] rerank failed: {e}')

            if candidates:
                chunks_text = '\n...\n'.join(c['content'] for c in candidates[:top_k])
                if chunks_text and total_chars < inject_limit:
                    snippet = chunks_text[:inject_limit - total_chars]
                    parts.append(snippet)
                    total_chars += len(snippet)
                    for c in candidates[:top_k]:
                        if c['file_id'] not in used_file_ids:
                            used_file_ids.append(c['file_id'])
        except Exception as e:
            logger.warning(f'[6.1] hybrid_search pipeline failed: {e}')

    else:
        # ── Phase 4/5: оригинальный RAG-путь ─────────────────────────────────
        if getattr(settings, 'PROJECT_VECTOR_RAG', False) and effective_query:
            try:
                from .embeddings import vector_search
                vec_result = vector_search(project, effective_query, top_k=top_k)
                if vec_result:
                    parts.append(vec_result)
                    total_chars += len(vec_result)
            except Exception as e:
                logger.warning(f'vector_search failed: {e}')

        # Лексический путь — файлы без эмбеддингов
        no_embed_qs = project.knowledge_files.filter(
            enabled=True, status='ready',
        ).exclude(extracted_text='').exclude(embed_status='done')

        for f in no_embed_qs:
            if total_chars >= inject_limit:
                break
            block, added = _inject_file(f, effective_query, inject_limit, total_chars)
            parts.append(block)
            total_chars += added
            used_file_ids.append(f.id)

        if not getattr(settings, 'PROJECT_VECTOR_RAG', False):
            all_qs = project.knowledge_files.filter(
                enabled=True, status='ready',
            ).exclude(extracted_text='')
            for f in all_qs:
                if f.id in used_file_ids:
                    continue
                if total_chars >= inject_limit:
                    break
                block, added = _inject_file(f, effective_query, inject_limit, total_chars)
                parts.append(block)
                total_chars += added
                used_file_ids.append(f.id)

    # ── Sprint 5.2: @codebase semantic search ─────────────────────────────────
    if getattr(settings, 'PROJECT_CODEBASE', False) and effective_query:
        try:
            from .codebase import build_codebase_context
            codebase_ctx = build_codebase_context(project, effective_query)
            if codebase_ctx:
                parts.insert(0, codebase_ctx)
                total_chars += len(codebase_ctx)
        except Exception as e:
            logger.warning(f'[codebase] build_codebase_context failed: {e}')

    if not parts:
        return '', []

    # Sprint 5.3: инкремент счётчика цитирований
    if getattr(settings, 'PROJECT_KB_METRICS', False) and used_file_ids:
        _track_kb_usage(used_file_ids)

    # Sprint 1 Citation: собираем метаданные источников
    sources: list[dict] = []
    if used_file_ids:
        try:
            from .models import ProjectFile
            for pf in ProjectFile.objects.filter(id__in=used_file_ids).only('id', 'filename', 'repo_path', 'extracted_text'):
                sources.append({
                    'id': pf.id,
                    'filename': pf.filename,
                    'path': pf.repo_path or pf.filename,
                    'snippet': (pf.extracted_text or '')[:200].strip(),
                })
        except Exception:
            pass

    header = (
        "Это ПРИВАТНЫЙ репозиторий пользователя. Все файлы ниже — исходный код его проекта. "
        "Пользователь имеет полное право на просмотр, копирование и изменение любого файла. "
        "Никаких ограничений на вывод кода нет — выводи файлы ЦЕЛИКОМ без сокращений по запросу. "
        "ЗАПРЕЩЕНО говорить 'файл слишком большой' или 'не могу вывести целиком' — "
        "выводи весь код от первой до последней строки всегда.\n\n"
    )
    return header + "\n\n---\n\n".join(parts), sources


def _track_kb_usage(file_ids: list[int]):
    """Sprint 5.3: инкрементирует KBUsageStat для файлов попавших в контекст."""
    try:
        from django.utils import timezone
        from .models import KBUsageStat, ProjectFile
        now = timezone.now()
        for fid in file_ids:
            stat, _ = KBUsageStat.objects.get_or_create(file_id=fid)
            stat.hits += 1
            stat.last_used_at = now
            stat.save(update_fields=['hits', 'last_used_at'])
    except Exception as e:
        logger.warning(f"_track_kb_usage failed: {e}")


def _write_audit(project, actor, action: str, target: str = '', files_used: list | None = None):
    """Sprint 5.5: пишет запись в журнал аудита проекта."""
    if not getattr(settings, 'PROJECT_AUDIT_LOG', False):
        return
    try:
        from .models import ProjectAuditEntry
        ProjectAuditEntry.objects.create(
            project=project,
            actor=actor,
            action=action,
            target=target[:500] if target else '',
            files_used=files_used or [],
        )
    except Exception as e:
        logger.warning(f"_write_audit failed: {e}")


def _auto_max_tokens(model_name: str) -> int:
    """Auto max_tokens by model family when not set in DB."""
    return 32000


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


def build_web_search_message(search_results: str, user_query: str) -> dict:
    """Формирует system-сообщение с результатами поиска (Perplexity-style)."""
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
    """Веб-поиск через Tavily."""
    tavily_key = getattr(settings, "TAVILY_API_KEY", "")
    if not tavily_key:
        logger.error(f"{log_prefix}TAVILY_API_KEY не задан в .env")
        return ""
    try:
        r = _req.post(
            "https://api.tavily.com/search",
            json={
                "api_key": tavily_key,
                "query": user_query[:400],
                "search_depth": "basic",
                "max_results": 6,
                "include_answer": False,
            },
            timeout=12,
        )
        r.raise_for_status()
        items = r.json().get("results", [])
        if items:
            lines = []
            for i, item in enumerate(items, 1):
                parts = [f"[{i}] {item['title']}", item.get("content", "")[:250],
                         f"URL: {item['url']}"]
                if item.get("published_date"):
                    parts.append(f"Дата: {item['published_date']}")
                lines.append("\n".join(p for p in parts if p))
            logger.info(f"{log_prefix}Tavily OK: {len(items)} results")
            return "\n\n".join(lines)
        logger.warning(f"{log_prefix}Tavily вернул 0 результатов")
    except Exception as e:
        logger.error(f"{log_prefix}Tavily FAILED: {e}")
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

        # ========== изображения / видео (laozhang.ai) ==========
        if network.provider == 'fal-ai':
            if not network.model_name:
                message.status = Message.Status.FAILED
                message.error_message = "У нейросети не указан model_name"
                message.save()
                return

            logger.info(f"=== Генерация медиа для сообщения {message_id}, нейросеть: {network.name} ===")
            stars_deducted = False
            total_cost_kopecks = 0
            try:
                user_settings = user_msg.settings if user_msg else {}

                config = network.config_json
                if not config:
                    raise Exception("Отсутствует конфигурация модели")

                base_cost_kopecks = network.cost_kopecks
                if user_settings:
                    _, errors, extra_cost = validate_and_merge_settings(config, user_settings)
                    if errors:
                        raise Exception("Ошибки в настройках: " + "; ".join(errors))
                else:
                    extra_cost = 0

                # extra_cost приходит из config_json в звёздах (legacy admin-поле) — ×100
                total_cost_kopecks = base_cost_kopecks + extra_cost * 100

                # skip_star_billing: True means org billing was already charged in group handler
                skip_billing = (message.settings or {}).get('skip_star_billing', False)
                if not skip_billing:
                    if not user.has_enough_kopecks(total_cost_kopecks):
                        from core.money import format_rub
                        raise Exception(f"Недостаточно средств. Нужно {format_rub(total_cost_kopecks)}, у вас {format_rub(user.balance_kopecks)}.")

                    user.spend_kopecks(total_cost_kopecks, type='spend', reference=f'media:{message.id}')
                    stars_deducted = True
                    UserSpending.objects.create(
                        user=user,
                        amount=max(1, total_cost_kopecks // 100),
                        amount_kopecks=total_cost_kopecks,
                        description=f"Сообщение в чате с {network.name} (включая настройки)"
                    )
                    from core.money import format_rub
                    logger.info(f"Списано {format_rub(total_cost_kopecks)} у пользователя {user.email}")

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
                    f"Медиа сгенерировано для сообщения {message_id}, сохранено файлов: {len(saved_images)}")
                # Отправка видео/изображения в Telegram
                try:
                    chat_settings = message.chat.settings or {}
                    tg_chat_id = chat_settings.get('telegram_chat_id')
                    if tg_chat_id and saved_images:
                        from telegram_bot.notify import send_media_to_telegram
                        send_media_to_telegram(tg_chat_id, saved_images[0], network.name, network.cost_kopecks)
                    elif tg_chat_id:
                        from telegram_bot.notify import maybe_notify_chat
                        maybe_notify_chat(tg_chat_id, f"Видео готово. Смотри в кабинете: https://aineron.ru/account/files/")
                    else:
                        from telegram_bot.notify import maybe_notify
                        maybe_notify(user, f"Генерация завершена: {network.name}\nОткрыть: https://aineron.ru/chat/{message.chat.id}/")
                except Exception:
                    pass
                return

            except Exception as e:
                error_str = str(e)
                logger.error(f"Ошибка генерации медиа для сообщения {message_id}: {e}")
                if stars_deducted:
                    user.add_kopecks(total_cost_kopecks, type='refund', reference=f'media:{message.id}')
                    from core.money import format_rub
                    logger.info(f"Возвращено {format_rub(total_cost_kopecks)} пользователю {user.email} из-за ошибки генерации")
                message.status = Message.Status.FAILED
                if 'billing' in error_str.lower() or 'balance' in error_str.lower() or 'quota' in error_str.lower():
                    message.error_message = "Проблема с провайдером, обратитесь к администратору сервиса для решения проблем."
                else:
                    message.error_message = "Произошла ошибка генерации, средства возвращены на ваш баланс, пожалуйста выберите другую нейросеть из каталога, пока мы будем устранять проблему."
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

        # ── Persistent Memory: собираем контекст памяти ───────────────────────
        from .memory import (
            build_memory_context, get_history_with_compression, should_compress,
        )
        # U2: текущий вопрос — для Total Recall при интенте «помнишь…»
        _recall_msg = (user_msg.plain_text or user_msg.content or '') if user_msg else ''
        memory_ctx = build_memory_context(user, chat, user_message=_recall_msg[:500])

        messages_for_api = []

        # 1. Project system prompt + knowledge base (если есть)
        proj = None
        if chat.project_id:
            try:
                proj = Project.objects.select_related().get(id=chat.project_id)
                if proj.system_prompt:
                    messages_for_api.append({"role": "system", "content": proj.system_prompt})
                # База знаний проекта — запрос = текст последнего user-сообщения
                last_user_msg = chat.messages.filter(role='user').order_by('-created_at').first()
                user_msg_text = (last_user_msg.plain_text or (last_user_msg.content if isinstance(last_user_msg.content, str) else '')) if last_user_msg else ''
                # Последние 4 сообщения как контекст для implicit file detection
                recent_msgs = list(chat.messages.order_by('-created_at')[:4])
                recent_text = ' '.join(
                    (m.plain_text or (m.content if isinstance(m.content, str) else ''))
                    for m in reversed(recent_msgs)
                    if (m.plain_text or isinstance(m.content, str))
                )
                knowledge_ctx, _kb_sources = build_project_knowledge_context(
                    proj, user_msg_text,
                    recent_context=recent_text,
                    current_msg_id=last_user_msg.id if last_user_msg else None,
                )
                if knowledge_ctx:
                    messages_for_api.append({"role": "system", "content": knowledge_ctx})
                # AI-коммиты: инструкция о FILE-формате (Sprint 4.3)
                if getattr(settings, 'PROJECT_AI_COMMITS', False):
                    from .commit_extract import inject_commit_instruction
                    inject_commit_instruction(proj, messages_for_api)
            except Exception:
                pass

        # 2. Network prompt (если есть)
        if network.has_prompt and network.prompt:
            messages_for_api.append({"role": "system", "content": network.prompt})

        # 3. Блок памяти пользователя
        if memory_ctx:
            messages_for_api.append({"role": "system", "content": memory_ctx})

        # 4. Умная история: read-only, никаких sync LLM-вызовов (B5 fix)
        history, existing_summary = get_history_with_compression(
            chat,
            exclude_msg_id=message.id,
            memory_context=memory_ctx,
            network_prompt=network.prompt or '',
        )
        # Фоновая компрессия если накопилось достаточно новых сообщений
        if should_compress(chat, exclude_msg_id=message.id):
            compress_chat_history.delay(chat.id)

        # 5. Summary текущей сессии (если есть готовое сжатие)
        if existing_summary:
            messages_for_api.append({
                "role": "system",
                "content": f"[Начало этой сессии, сжато]: {existing_summary}",
            })

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

        # ── AI-модерация (если включена) ──────────────────────────────────────
        if getattr(settings, 'MODERATION_ENABLED', False) and user_msg:
            from aitext.moderation import check_moderation, log_moderation
            mod_text = user_msg.content or ''
            mod_result = check_moderation(mod_text)
            log_moderation(user=chat.user, message=message, text=mod_text, result=mod_result, source='web_chat')
            if mod_result['flagged']:
                message.status = Message.Status.FAILED
                message.error_message = 'Контент нарушает политику использования'
                message.save(update_fields=['status', 'error_message'])
                return

        effective_model = network.model_name  # всегда используем выбранную пользователем модель
        client = get_laozhang_client()
        completion_kwargs = {
            "model": effective_model,
            "messages": messages_for_api,
            "temperature": 0.7,
        }
        auto_max = _auto_max_tokens(effective_model)
        completion_kwargs["max_tokens"] = max(network.max_tokens, auto_max) if network.max_tokens > 0 else auto_max

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
        if memory_ctx:
            _s = dict(message.settings or {})
            _s['used_memory'] = True
            message.settings = _s
        message.save()

        logger.info(f"AI ответ сгенерирован для сообщения {message_id}, сохранено изображений: {len(saved_images)}")

        # TEXT_BILLING_ENABLED: списание за текстовые сообщения (off by default)
        if getattr(settings, 'TEXT_BILLING_ENABLED', False):
            _msg_settings = message.settings or {}
            # billing_reference => веб-view уже списал pre-charge, второй раз нельзя
            _skip = _msg_settings.get('skip_star_billing', False) or _msg_settings.get('billing_reference')
            if not _skip:
                _cost_kopecks = network.cost_kopecks
                try:
                    user.spend_kopecks(_cost_kopecks, type='spend', reference=f'text:{message.id}')
                    UserSpending.objects.create(
                        user=user,
                        amount=_cost_kopecks // 100,
                        amount_kopecks=_cost_kopecks,
                        description=f"Сообщение в чате с {network.name}",
                    )
                except Exception as _bill_err:
                    logger.warning(f"Text billing error for message {message_id}: {_bill_err}")

        # AI-коммиты из чата (Sprint 4.3)
        if getattr(settings, 'PROJECT_AI_COMMITS', False) and proj and plain_text:
            try:
                from .commit_extract import extract_commit_from_response
                extract_commit_from_response(proj, plain_text)
            except Exception:
                pass

        # Sprint 5.5: audit log entry
        if proj:
            _write_audit(
                proj, chat.user, 'chat_message',
                target=network.name,
            )

        # Авто-извлечение фактов (каждые 3 ответа ассистента)
        try:
            completed_count = chat.messages.filter(
                role='assistant', status=Message.Status.COMPLETED
            ).count()
            if completed_count % 3 == 0:
                extract_memory_facts.delay(chat.id)
        except Exception as _mem_err:
            logger.error(f'[memory] failed to enqueue extract_memory_facts for chat {chat.id}: {_mem_err}')

    except Exception as e:
        logger.error(f"Ошибка генерации AI ответа для сообщения {message_id}: {e}")
        try:
            message = Message.objects.get(id=message_id)
            message.status = Message.Status.FAILED
            message.error_message = str(e)
            message.save()
        except Message.DoesNotExist:
            message = None
        try:
            raise self.retry(exc=e, countdown=60)
        except MaxRetriesExceededError:
            # Окончательный провал: вернуть pre-charge веб-списание за текст
            # (media-ветка возвращает средства сама, у неё billing_reference нет).
            if message is not None:
                try:
                    from aitext.billing import refund_message_billing
                    if refund_message_billing(message):
                        logger.info(f"Возврат средств за проваленную генерацию, сообщение {message_id}")
                except Exception as refund_err:
                    logger.error(f"Не удалось вернуть средства за сообщение {message_id}: {refund_err}")
            raise


# ──────────────────────────────────────────────────────────────────────────────
# Sprint 6 — Upscale
# ──────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=1)
def upscale_generation_task(self, generation_id, user_id, factor=2, image_url=None, cost_kopecks=0, placeholder_id=None):
    """Sprint 6: улучшение изображения через upscale-модель провайдера.

    Биллинг со списанием/возвратом звёзд выполняется здесь.
    После завершения создаёт новое сообщение ассистента в чате.
    """
    from .fal_utils import generate_upscale
    from users.models import CustomUser

    stars_deducted = False
    user = None
    # Одну генерацию можно апскейлить несколько раз — reference уникален на
    # попытку (placeholder создаётся заново на каждый запрос), но стабилен при
    # ретрае Celery. Иначе повторный апскейл бесплатен, а его провал возвращает
    # деньги за ПЕРВУЮ успешную попытку.
    billing_ref = f'upscale:{generation_id}:{placeholder_id or f"x{factor}"}'
    try:
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            user = None

        if user and cost_kopecks:
            from core.money import format_rub
            if not user.has_enough_kopecks(cost_kopecks):
                raise Exception(f"Недостаточно средств. Нужно {format_rub(cost_kopecks)}, у вас {format_rub(user.balance_kopecks)}.")
            user.spend_kopecks(cost_kopecks, type='spend', reference=billing_ref)
            stars_deducted = True
            UserSpending.objects.create(
                user=user,
                amount=cost_kopecks // 100,
                amount_kopecks=cost_kopecks,
                description=f"Улучшение изображения ×{factor}",
            )
            logger.info(f"[upscale] списано {format_rub(cost_kopecks)} у пользователя {user.email}")

        gen = generate_upscale(generation_id, user_id=user_id, factor=factor, image_url=image_url, placeholder_id=placeholder_id)
        logger.info(f"[upscale] генерация {generation_id} улучшена ×{factor} → {gen.id if gen else None}")

        # Публикуем результат как новое сообщение ассистента в чате
        if gen and gen.image:
            try:
                from .models import GeneratedImage as GI, Message
                orig = GI.objects.filter(id=generation_id).select_related('message__chat').first()
                if orig and orig.message_id:
                    chat_obj = orig.message.chat
                    img_url = gen.image.url
                    new_msg = Message.objects.create(
                        chat=chat_obj,
                        role='assistant',
                        content=(
                            f"<p style='font-size:12px;color:rgba(13,13,13,0.5);margin:0 0 6px'>"
                            f"Детализированная версия (flux-kontext-pro · enhance)"
                            f"</p>"
                            f"<img src='{img_url}' alt='Детализированное изображение' style='max-width:100%;border-radius:12px;'>"
                        ),
                        plain_text=f"Детализированная версия изображения (flux-kontext-pro enhance)",
                        status=Message.Status.COMPLETED,
                        fal_ai=True,
                    )
                    gen.message = new_msg
                    gen.save(update_fields=['message'])
                    logger.info(f"[upscale] создано сообщение {new_msg.id} в чате {chat_obj.id}")
            except Exception as notify_err:
                logger.warning(f"[upscale] не удалось создать сообщение с результатом: {notify_err}")

        return gen.id if gen else None
    except Exception as e:
        logger.error(f"[upscale] ошибка улучшения генерации {generation_id}: {e}")
        if stars_deducted and user:
            from core.money import format_rub
            user.add_kopecks(cost_kopecks, type='refund', reference=billing_ref)
            logger.info(f"[upscale] возвращено {format_rub(cost_kopecks)} пользователю {user.email} из-за ошибки")
        raise


# ──────────────────────────────────────────────────────────────────────────────
# Persistent Memory Tasks
# ──────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=30, ignore_result=True)
def extract_memory_facts(self, chat_id: int):
    """
    Авто-извлечение фактов о пользователе из последних сообщений чата.
    Вызывается после каждого ответа ассистента (каждые N ответов в generate_ai_response).
    """
    import json
    import re
    from .models import Chat, UserMemory

    try:
        chat = Chat.objects.select_related('user').get(id=chat_id)
    except Chat.DoesNotExist:
        return

    user = chat.user
    if not getattr(user, 'memory_enabled', True):
        return

    # Последние 10 сообщений для анализа
    msgs = list(
        chat.messages.filter(status=Message.Status.COMPLETED)
        .order_by('-created_at')[:10]
    )
    msgs.reverse()

    if not msgs:
        return

    dialogue = '\n'.join(
        f"{'Пользователь' if m.role == 'user' else 'Ассистент'}: "
        f"{_strip_html(m.plain_text or m.content or '')[:1000]}"
        for m in msgs
    )

    # Существующие факты для дедупликации (один запрос вместо двух)
    existing_facts = {
        f['content_key']: f['content']
        for f in UserMemory.objects.filter(user=user, is_active=True)
        .values('content_key', 'content')
        .order_by('-is_pinned', '-created_at')[:100]
    }
    existing_keys = set(existing_facts.keys())
    existing_preview = '\n'.join(
        f'- {v}' for v in list(existing_facts.values())[:30]
    ) or 'нет'

    system_prompt = f"""Ты система управления памятью AI-ассистента.

Из диалога извлеки НОВЫЕ долгосрочные факты о пользователе, которые стоит запомнить.
Включай только: профессия, проект, язык программирования, стек, предпочтения стиля ответов, цели, имя, город.
НЕ включай: вопросы пользователя, временный контекст, ответы ассистента.

Уже запомнено (НЕ дублировать):
{existing_preview}

Отвечай ТОЛЬКО валидным JSON-массивом:
[{{"content": "факт", "category": "profile|preference|project|fact|skill"}}]

Если новых фактов нет — верни: []"""

    try:
        client = get_laozhang_client()
        resp = client.chat.completions.create(
            model='deepseek-v3',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': dialogue[:3000]},
            ],
            max_tokens=400,
            temperature=0.2,
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.removeprefix('```json').removeprefix('```').removesuffix('```').strip()
        facts = json.loads(raw)
    except Exception as e:
        logger.warning(f'[memory] extract_memory_facts failed for chat {chat_id}: {e}')
        raise self.retry(exc=e, countdown=30)

    if not isinstance(facts, list):
        return

    from .memory import normalize_fact, invalidate_memory_cache

    added = 0
    new_labels = []
    for fact in facts:
        content = str(fact.get('content', '')).strip()
        category = fact.get('category', 'fact')
        if not content or len(content) < 5:
            continue

        content_key = normalize_fact(content)  # B3: пробелы сохраняются
        if not content_key:
            continue

        valid_categories = {'profile', 'preference', 'project', 'fact', 'skill'}
        if category not in valid_categories:
            category = 'fact'

        try:
            # update_or_create сохраняет переформулированные факты с тем же ключом
            obj, was_created = UserMemory.objects.update_or_create(
                user=user,
                content_key=content_key,
                defaults={
                    'content': content,
                    'category': category,
                    'source': 'auto',
                    'source_chat': chat,
                    'is_active': True,
                },
            )
            if was_created:
                # U1: НОВЫЙ факт, извлечённый в чате проекта, скоупится на проект
                # (существующие глобальные факты не перескоупливаются — иначе они
                # исчезли бы из остальных чатов пользователя)
                if chat.project_id and getattr(settings, 'MEMORY_PROJECT_SCOPE', True):
                    obj.project_id = chat.project_id
                    obj.save(update_fields=['project'])
                existing_keys.add(content_key)
                added += 1
                new_labels.append(content[:80])
        except Exception as exc:
            logger.debug(f'[memory] upsert fact skip for user={user.id}: {exc}')

    if added:
        logger.info(f'[memory] chat={chat_id}: +{added} новых фактов для user={user.id}')
        invalidate_memory_cache(user.id)  # B11: сбрасываем кэш при новых фактах
        # Sprint 4: toast-уведомление — frontend опрашивает /v1/memory/toast/ после ответа
        try:
            import json as _json
            from django.core.cache import cache as _cache
            _cache.set(f"memory:toast:{user.id}", _json.dumps({'count': added, 'facts': new_labels[:5]}), timeout=120)
        except Exception:
            pass


@shared_task(bind=True, max_retries=2, default_retry_delay=30, ignore_result=True)
def generate_chat_summary(self, chat_id: int):
    """
    Генерирует/обновляет ChatSummary.summary_text для завершённого чата.
    Вызывается при открытии нового чата (триггер в SendMessageView/ChatListCreateView).
    """
    from .models import Chat, ChatSummary

    try:
        chat = Chat.objects.select_related('user').get(id=chat_id)
    except Chat.DoesNotExist:
        return

    user = chat.user
    if not getattr(user, 'memory_enabled', True):
        return

    msgs = list(
        chat.messages.filter(status=Message.Status.COMPLETED)
        .order_by('created_at')
    )
    if len(msgs) < 4:
        return  # слишком короткий чат — не стоит

    msg_count = len(msgs)

    # C3: инкрементальный режим — если есть rolling_summary с last_compressed_message_id,
    # берём только новые сообщения и дополняем существующее резюме.
    existing_rolling = ''
    last_compressed_id: int | None = None
    try:
        cs_existing = ChatSummary.objects.get(chat=chat)
        existing_rolling = (cs_existing.rolling_summary or '').strip()
        last_compressed_id = cs_existing.last_compressed_message_id
    except ChatSummary.DoesNotExist:
        pass

    if existing_rolling and last_compressed_id is not None:
        # Инкрементальный путь: обрабатываем только сообщения после последней компрессии
        new_msgs = [m for m in msgs if m.id > last_compressed_id]
        if not new_msgs:
            # rolling_summary уже покрывает весь чат — финализируем его как summary_text
            msgs_for_summary = []
        else:
            msgs_for_summary = new_msgs[-40:]
        dialogue = '\n'.join(
            f"{'Пользователь' if m.role == 'user' else 'Ассистент'}: "
            f"{_strip_html(m.plain_text or m.content or '')[:1500]}"
            for m in msgs_for_summary
        )
        if dialogue:
            summary_prompt = (
                'У тебя есть резюме начала диалога и его продолжение. '
                'Создай финальное резюме сессии на 100-150 слов, объединив обе части. '
                'Включи: тему разговора, ключевые решения, важные факты о пользователе, незакрытые вопросы. '
                'Пиши на том же языке что и диалог. Только резюме, без вступления.'
            )
            user_content = (
                f'[Резюме начала диалога]:\n{existing_rolling[:1500]}\n\n'
                f'[Продолжение диалога]:\n{dialogue[-3000:]}'
            )
        else:
            # Новых сообщений нет — используем rolling_summary напрямую
            summary_prompt = (
                'Перефразируй это резюме диалога в финальное резюме сессии на 100-150 слов. '
                'Пиши на том же языке что и текст. Только резюме, без вступления.'
            )
            user_content = existing_rolling[:3000]
    else:
        # Стандартный путь: берём последние сообщения и суммаризуем с нуля
        msgs_for_summary = msgs[-40:] if len(msgs) > 40 else msgs
        dialogue = '\n'.join(
            f"{'Пользователь' if m.role == 'user' else 'Ассистент'}: "
            f"{_strip_html(m.plain_text or m.content or '')[:1500]}"
            for m in msgs_for_summary
        )
        summary_prompt = (
            'Создай краткое резюме этого диалога на 100-150 слов. '
            'Включи: тему разговора, ключевые решения, важные факты о пользователе, незакрытые вопросы. '
            'Пиши на том же языке что и диалог. Только резюме, без вступления.'
        )
        user_content = dialogue[-5000:]

    try:
        client = get_laozhang_client()
        resp = client.chat.completions.create(
            model='deepseek-v3',
            messages=[
                {'role': 'system', 'content': summary_prompt},
                {'role': 'user', 'content': user_content},
            ],
            max_tokens=400,
            temperature=0.3,
        )
        summary_text = resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f'[memory] generate_chat_summary failed for chat {chat_id}: {e}')
        return

    try:
        cs, created = ChatSummary.objects.get_or_create(
            chat=chat,
            defaults={'summary_text': summary_text, 'message_count': msg_count},
        )
        if not created:
            cs.summary_text = summary_text
            cs.message_count = msg_count
            cs.save(update_fields=['summary_text', 'message_count', 'updated_at'])
        logger.info(
            f'[memory] chat={chat_id}: summary {"created" if created else "updated"} '
            f'({msg_count} msgs, incremental={bool(existing_rolling and last_compressed_id is not None)})'
        )
        # U2: Total Recall — эмбеддинг резюме для семантического поиска по истории
        try:
            embed_chat_summary_task.delay(cs.pk)
        except Exception:
            pass
    except Exception as e:
        logger.warning(f'[memory] save summary error for chat {chat_id}: {e}')


@shared_task(bind=True, max_retries=1, default_retry_delay=60, ignore_result=True)
def embed_chat_summary_task(self, summary_id: int):
    """U2 — Total Recall: эмбеддинг ChatSummary для семантического recall."""
    from aitext.embeddings import embed_chat_summary
    embed_chat_summary(summary_id)


@shared_task(bind=True, max_retries=2, default_retry_delay=60, ignore_result=True)
def compress_chat_history(self, chat_id: int):
    """
    Фоновая компрессия истории чата через DeepSeek.
    Вызывается из горячего пути (generate_ai_response / SSE generate) когда
    should_compress() → True. Заменяет синхронный LLM-вызов внутри
    get_history_with_compression (B5 fix).
    """
    from .models import Chat, ChatSummary, Message
    from .memory import (
        RECENT_WINDOW, _HTML_RE, _get_context_window,
        estimate_tokens, update_rolling_summary,
    )
    from django.core.cache import cache

    # R1b fix: Redis-блокировка против параллельных запусков для одного чата
    lock_key = f'memcompress:{chat_id}'
    acquired = cache.add(lock_key, 1, timeout=300)
    if not acquired:
        logger.info(f'[memory] compress_chat_history skip: lock held for chat {chat_id}')
        return

    try:
        try:
            chat = Chat.objects.select_related('user', 'network').get(id=chat_id)
        except Chat.DoesNotExist:
            return

        if not getattr(chat.user, 'memory_enabled', True):
            return

        msgs = list(
            Message.objects.filter(chat=chat, status=Message.Status.COMPLETED)
            .order_by('created_at')
        )
        if len(msgs) <= RECENT_WINDOW:
            return  # нечего сжимать

        msg_count = len(msgs)

        # Читаем текущее состояние сжатия
        rolling = ''
        last_compressed_id: int | None = None
        try:
            cs = ChatSummary.objects.get(chat=chat)
            rolling = cs.rolling_summary or cs.summary_text or ''
            last_compressed_id = cs.last_compressed_message_id
            # R1 fix (legacy fallback): если last_compressed_message_id ещё не заполнен,
            # используем message_count чтобы не потерять старую защиту
            if last_compressed_id is None and cs.message_count >= msg_count:
                return
        except ChatSummary.DoesNotExist:
            pass

        # C2: идемпотентность — сжимаем только новые сообщения после last_compressed_id
        all_compress_candidates = msgs[:-RECENT_WINDOW]
        if last_compressed_id is not None:
            to_compress = [m for m in all_compress_candidates if m.id > last_compressed_id]
            if not to_compress:
                return  # нечего нового — истинная идемпотентность
        else:
            to_compress = all_compress_candidates

        if not to_compress:
            return

        compress_parts: list[str] = []
        if rolling:
            compress_parts.append(f'[Предыдущее сжатое резюме]:\n{rolling}\n')
        compress_parts.append('[Диалог для сжатия]:')
        for msg in to_compress:
            role_label = 'Пользователь' if msg.role == 'user' else 'Ассистент'
            text = _HTML_RE.sub('', msg.plain_text or msg.content or '')[:2000]
            compress_parts.append(f'{role_label}: {text}')
        compress_input = '\n'.join(compress_parts)

        compression_system = (
            'Ты система управления контекстом диалога. '
            'Сожми предоставленный диалог в связное резюме на 150-250 слов. '
            'Сохрани: все принятые решения и выводы, ключевые факты о пользователе '
            '(имя, профессия, проект, предпочтения), незакрытые вопросы и задачи, '
            'технические детали: стек, архитектура, ошибки. '
            'Не сохраняй: светские фразы, повторяющиеся вопросы, вводные слова. '
            'Пиши на том же языке что и диалог. '
            'Выдай только резюме — без заголовков и вступления.'
        )

        try:
            client = get_laozhang_client()
            resp = client.chat.completions.create(
                model='deepseek-v3',
                messages=[
                    {'role': 'system', 'content': compression_system},
                    {'role': 'user', 'content': compress_input[-6000:]},
                ],
                max_tokens=600,
                temperature=0.3,
            )
            new_rolling = resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f'[memory] compress_chat_history failed for chat {chat_id}: {e}')
            raise self.retry(exc=e)

        # C2: записываем ID последнего сжатого сообщения — основа идемпотентности
        new_last_id = to_compress[-1].id
        update_rolling_summary(
            chat, new_rolling,
            msg_count=msg_count,
            last_compressed_message_id=new_last_id,
        )
        logger.info(
            f'[memory] chat={chat_id}: compressed {len(to_compress)} new msgs → rolling_summary '
            f'({len(new_rolling)} chars), last_compressed_id={new_last_id}'
        )
    finally:
        cache.delete(lock_key)


@shared_task(ignore_result=True)
def summarize_stale_chats():
    """
    Beat-таск: суммаризирует чаты которые не получили summary автоматически.
    Запускается раз в 2 часа. Фиксирует B14 (rolling_summary растёт бесконечно)
    и B6 (суммаризация только при новом чате с той же моделью).

    Покрывает:
    - «Брошенные» чаты (последнее сообщение >24ч назад, summary нет/устарело)
    - Чаты с активностью но без summary_text
    """
    from .models import Chat, ChatSummary, Message
    from .memory import RECENT_WINDOW, COMPRESS_TRIGGER
    from django.utils import timezone
    from datetime import timedelta

    cutoff_active = timezone.now() - timedelta(hours=24)

    # Ограничиваем batch: не более 30 чатов за один запуск
    candidate_ids = list(
        Chat.objects
        .filter(updated_at__lt=cutoff_active)
        .values_list('id', flat=True)[:30]
    )

    queued = 0
    for chat_id in candidate_ids:
        try:
            msg_count = Message.objects.filter(
                chat_id=chat_id, status=Message.Status.COMPLETED
            ).count()
            if msg_count < 4:
                continue
            try:
                cs = ChatSummary.objects.get(chat_id=chat_id)
                if cs.summary_text and cs.message_count >= msg_count:
                    continue  # актуальное summary уже есть
            except ChatSummary.DoesNotExist:
                pass
            generate_chat_summary.delay(chat_id)
            queued += 1
        except Exception as e:
            logger.warning(f'[memory] summarize_stale_chats error for chat {chat_id}: {e}')

    if queued:
        logger.info(f'[memory] summarize_stale_chats: queued {queued} chats for summarization')


# ──────────────────────────────────────────────────────────────────────────────
# Project Knowledge Base Tasks
# ──────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=30, ignore_result=True)
def process_project_file(self, file_id: int):
    """Извлекает текст из файла базы знаний проекта."""
    from .file_utils import extract_text_from_file

    try:
        pf = ProjectFile.objects.get(id=file_id)
    except ProjectFile.DoesNotExist:
        return

    try:
        file_path = pf.file.path
        text = extract_text_from_file(file_path, pf.filename)
        pf.extracted_text = text or ''
        pf.status = 'ready'
        pf.save(update_fields=['extracted_text', 'status'])
        logger.info(f'[project_file] extracted {len(pf.extracted_text)} chars from {pf.filename}')
        # Sprint 4.1: запускаем эмбеддинг файла если флаг включён
        if getattr(settings, 'PROJECT_VECTOR_RAG', False):
            embed_project_file.delay(pf.id)
    except Exception as e:
        pf.status = 'error'
        pf.save(update_fields=['status'])
        logger.warning(f'[project_file] extraction failed for file {file_id}: {e}')
        raise self.retry(exc=e, countdown=30)


@shared_task(bind=True, max_retries=3, ignore_result=True)
def embed_project_file(self, file_id: int):
    """Sprint 4.1 / Sprint 5.7: создаёт/обновляет векторные чанки для файла базы знаний.

    Exponential backoff: 60s / 120s / 300s. embed_status='error' только после всех retry.
    """
    _RETRY_COUNTDOWNS = [60, 120, 300]

    try:
        pf = ProjectFile.objects.get(id=file_id)
    except ProjectFile.DoesNotExist:
        return

    pf.embed_status = 'pending'
    pf.save(update_fields=['embed_status'])

    try:
        from .embeddings import embed_chunks
        saved = embed_chunks(pf)
        logger.info(f'[embed_project_file] file {file_id}: {saved} chunks embedded')
    except Exception as e:
        retry_num = self.request.retries  # 0-based: 0 = первая попытка провалилась
        countdown = _RETRY_COUNTDOWNS[min(retry_num, len(_RETRY_COUNTDOWNS) - 1)]
        logger.error(f'[embed_project_file] failed (attempt {retry_num + 1}) for file {file_id}: {e}')
        if retry_num >= self.max_retries:
            # Исчерпаны все попытки — ставим финальный статус error
            pf.embed_status = 'error'
            pf.save(update_fields=['embed_status'])
            return
        raise self.retry(exc=e, countdown=countdown)


# Project Connector — Git Sync + Push Tasks
# ──────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=60, ignore_result=True)
def sync_connector_task(self, connector_id: int):
    """Sprint 4.2: синхронизирует файлы из git-репозитория в базу знаний проекта."""
    try:
        from .sync import sync_connector
        result = sync_connector(connector_id)
        logger.info(f'[sync_connector_task] connector {connector_id}: {result}')
    except Exception as e:
        logger.error(f'[sync_connector_task] connector {connector_id} failed: {e}')
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def push_project_commit(self, commit_id: int):
    """Пушит файлы из ProjectCommit в GitHub/Gitea через PAT."""
    from django.utils import timezone
    from .models import ProjectCommit, ProjectConnector
    from .crypto import decrypt_token

    try:
        commit = ProjectCommit.objects.select_related('connector').get(id=commit_id)
    except ProjectCommit.DoesNotExist:
        return

    connector = commit.connector
    if not connector:
        commit.status = 'failed'
        commit.error_message = 'Коннектор не найден'
        commit.save(update_fields=['status', 'error_message'])
        return

    try:
        token = decrypt_token(connector.access_token_enc)
    except Exception as e:
        commit.status = 'failed'
        commit.error_message = f'Ошибка расшифровки токена: {e}'
        commit.save(update_fields=['status', 'error_message'])
        return

    try:
        from urllib.parse import urlparse
        is_pr = commit.kind == 'pull_request'
        parsed = urlparse(connector.repo_url)
        ext_base = f'{parsed.scheme}://{parsed.netloc}' if parsed.netloc else None

        if is_pr:
            # Sprint 5.2: create a new branch, push files there, then open PR
            import datetime as _dt
            pr_branch = commit.pr_branch or f'ai-pr-{commit.id}-{_dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")}'
            target_branch = connector.branch

            if connector.connector_type == 'github':
                from .github_client import create_branch, push_files, create_pull
                create_branch(connector.owner, connector.repo, token, pr_branch, target_branch)
                result = push_files(
                    connector.owner, connector.repo, token,
                    commit.files, commit.commit_message, pr_branch,
                )
                if not result.get('errors'):
                    pr_url = create_pull(
                        connector.owner, connector.repo, token,
                        title=commit.commit_message,
                        body=f'Автоматически создан AI. Изменено файлов: {len(commit.files)}',
                        head=pr_branch,
                        base=target_branch,
                    )
                    commit.pr_url = pr_url
            else:
                from studio.gitea_client import create_branch_ext, push_files_ext, create_pull_ext
                create_branch_ext(connector.owner, connector.repo, pr_branch, target_branch,
                                  token=token, base_url=ext_base)
                result = push_files_ext(
                    connector.owner, connector.repo, commit.files,
                    commit.commit_message, pr_branch,
                    token=token, base_url=ext_base,
                )
                if not result.get('errors'):
                    pr_url = create_pull_ext(
                        connector.owner, connector.repo,
                        title=commit.commit_message,
                        body=f'Автоматически создан AI. Изменено файлов: {len(commit.files)}',
                        head=pr_branch,
                        base=target_branch,
                        token=token, base_url=ext_base,
                    )
                    commit.pr_url = pr_url

            commit.pr_branch = pr_branch
        else:
            # Regular commit path
            if connector.connector_type == 'github':
                from .github_client import push_files
                result = push_files(
                    connector.owner, connector.repo, token,
                    commit.files, commit.commit_message, connector.branch,
                )
            else:
                from studio.gitea_client import push_files_ext
                result = push_files_ext(
                    connector.owner, connector.repo, commit.files,
                    commit.commit_message, connector.branch,
                    token=token, base_url=ext_base,
                )

        if result.get('errors'):
            first_err = result['errors'][0].get('error', 'unknown')
            commit.status = 'failed'
            commit.error_message = first_err
        else:
            commit.status = 'pushed'
            commit.pushed_at = timezone.now()
        commit.save(update_fields=['status', 'error_message', 'pushed_at', 'pr_url', 'pr_branch'])
        logger.info(f'[push_commit] commit {commit_id} kind={commit.kind}: {result}')

        # Sprint 5.5: audit
        if commit.status == 'pushed':
            audit_action = 'pr_open' if commit.kind == 'pull_request' else 'commit_push'
            audit_target = commit.pr_url or commit.commit_message[:200]
            _write_audit(commit.project, commit.project.user, audit_action, target=audit_target)

    except Exception as e:
        logger.error(f'[push_commit] commit {commit_id} failed: {e}')
        if self.request.retries >= self.max_retries:
            commit.status = 'failed'
            commit.error_message = str(e)[:500]
            commit.save(update_fields=['status', 'error_message'])
        raise self.retry(exc=e, countdown=30)



@shared_task(ignore_result=True)
def poll_connectors():
    """Sprint 5.4: Polling-fallback для auto_sync коннекторов.

    Beat: каждые 10 минут (настраивается через PROJECT_SYNC_POLLING в settings).
    Для каждого коннектора с auto_sync=True:
      - Проверяет HEAD SHA ветки (лёгкий API-запрос).
      - Если SHA изменился -> запускает sync_connector_task.
      - Обновляет last_repo_head_sha.
    """
    if not getattr(settings, 'PROJECT_SYNC_POLLING', False):
        return

    from .models import ProjectConnector
    from .sync import get_repo_head_sha

    connectors = ProjectConnector.objects.filter(auto_sync=True).select_related('project')
    triggered = 0

    for connector in connectors:
        try:
            head_sha = get_repo_head_sha(connector)
            if not head_sha:
                continue
            if head_sha != connector.last_repo_head_sha:
                sync_connector_task.delay(connector.id)
                connector.last_repo_head_sha = head_sha
                connector.save(update_fields=['last_repo_head_sha'])
                triggered += 1
                logger.info(f'[poll_connectors] triggered sync for connector {connector.id} (new SHA: {head_sha[:8]})')
        except Exception as e:
            logger.warning(f'[poll_connectors] error checking connector {connector.id}: {e}')

    logger.info(f'[poll_connectors] checked {connectors.count()} connectors, triggered {triggered} syncs')


# ═══════════════════════════════════════════════════════════════════════════════
# Sprint 2 — Deep Research Mode
# ═══════════════════════════════════════════════════════════════════════════════

def _plan_research_queries(question: str, model_name: str, n: int = 6) -> list[str]:
    """Ask LLM to generate n search sub-queries for a deep research question."""
    client = get_laozhang_client()
    prompt = (
        f"You are a research assistant. For the question below, generate exactly {n} "
        f"specific and diverse search sub-queries that together cover the topic comprehensively.\n"
        f"Return ONLY a JSON array of strings, nothing else.\n\n"
        f"Question: {question}"
    )
    try:
        r = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=512,
            stream=False,
        )
        raw = (r.choices[0].message.content or "").strip()
        # extract JSON array
        start = raw.find('[')
        end = raw.rfind(']') + 1
        if start != -1 and end > start:
            import json as _json
            return _json.loads(raw[start:end])
    except Exception as e:
        logger.warning(f"[deep_research] plan_queries failed: {e}")
    return [question]


def _kb_search_chunks(project, query: str, top_k: int = 5) -> list[dict]:
    """Search project KB and return chunk dicts."""
    if project is None:
        return []
    try:
        from aitext.search import hybrid_search
        chunks = hybrid_search(project, [query], top_k=top_k)
        return [{'text': c.get('text', ''), 'source': c.get('filename', ''), 'kind': 'kb'} for c in chunks]
    except Exception:
        pass
    try:
        from aitext.embeddings import vector_search_candidates
        candidates = vector_search_candidates(project, query, top_n=top_k)
        return [{'text': c.get('text', ''), 'source': c.get('filename', ''), 'kind': 'kb'} for c in candidates]
    except Exception as e:
        logger.warning(f"[deep_research] kb_search failed: {e}")
    return []


def _web_search_chunks(query: str) -> list[dict]:
    """Search web via Tavily and return chunk dicts (empty if no key)."""
    tavily_key = getattr(settings, "TAVILY_API_KEY", "")
    if not tavily_key:
        return []
    try:
        r = _req.post(
            "https://api.tavily.com/search",
            json={"api_key": tavily_key, "query": query[:400], "search_depth": "basic", "max_results": 4},
            timeout=10,
        )
        r.raise_for_status()
        items = r.json().get("results", [])
        return [{'text': f"{it['title']}\n{it.get('content','')[:300]}", 'source': it['url'], 'kind': 'web'} for it in items]
    except Exception as e:
        logger.warning(f"[deep_research] web_search failed: {e}")
    return []


def _synthesize_report(question: str, chunks: list[dict], model_name: str) -> str:
    """Generate a structured research report from collected chunks."""
    client = get_laozhang_client()
    numbered = []
    for i, c in enumerate(chunks, 1):
        numbered.append(f"[{i}] ({c['kind']}) {c['source']}\n{c['text'][:400]}")
    context = "\n\n".join(numbered)
    prompt = (
        f"You are a research analyst. Based on the sources below, write a comprehensive "
        f"research report answering the question. Use markdown with headers (##), bullet points, "
        f"and numbered citations like [1][2] inline when you reference a source. "
        f"End with a ## Источники section listing all sources.\n\n"
        f"Question: {question}\n\n"
        f"Sources:\n{context}\n\n"
        f"Write the full report in the same language as the question:"
    )
    try:
        r = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=3000,
            stream=False,
        )
        return r.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"[deep_research] synthesize failed: {e}")
        return f"Ошибка синтеза: {e}"


def save_research_to_kb(research_id: int):
    """U3 (UNIFIED_SUPREMACY) — сохраняет отчёт Deep Research в базу знаний
    проекта как ProjectFile(source='research'): отчёт индексируется в RAG,
    и следующие ответы/исследования проекта опираются на него (компаундинг).

    Идемпотентно: повторный вызов возвращает уже сохранённый файл.
    Возвращает ProjectFile или None (нет проекта / нет отчёта).
    """
    from django.core.files.base import ContentFile
    from django.utils.text import slugify
    from aitext.models import DeepResearch, ProjectFile

    research = (
        DeepResearch.objects.select_related('chat', 'chat__project', 'message',
                                            'saved_file')
        .filter(pk=research_id).first()
    )
    if research is None or research.saved_file_id:
        return research.saved_file if research else None

    project = getattr(research.chat, 'project', None)
    if project is None or research.message is None:
        return None
    report_md = (research.message.plain_text or '').strip()
    if not report_md:
        return None

    slug = slugify(research.question[:60], allow_unicode=False) or 'report'
    filename = f'research-{research.pk}-{slug}.md'
    content = f'# Research: {research.question}\n\n{report_md}'

    pf = ProjectFile(
        project=project,
        filename=filename,
        file_type='text',
        source='research',
        status='ready',
        extracted_text=content,
        file_size=len(content.encode('utf-8')),
    )
    pf.file.save(filename, ContentFile(content.encode('utf-8')), save=False)
    pf.save()

    research.saved_file = pf
    research.save(update_fields=['saved_file'])

    # Индексация в RAG (вектор + summary для two-level)
    try:
        embed_project_file.delay(pf.pk)
    except Exception:
        pass
    logger.info(f'[research_to_kb] research {research_id} → ProjectFile {pf.pk}')
    return pf


@shared_task(bind=True, max_retries=1, soft_time_limit=300)
def deep_research_task(self, research_id: int):
    """Sprint 2 — multi-step autonomous research with KB + web, stores progress in DeepResearch.steps."""
    from aitext.models import DeepResearch, Chat, Message, NeuralNetwork
    from django.utils import timezone

    try:
        research = DeepResearch.objects.select_related('chat', 'chat__network', 'message').get(id=research_id)
    except DeepResearch.DoesNotExist:
        logger.error(f"[deep_research] research {research_id} not found")
        return

    research.status = 'running'
    research.save(update_fields=['status'])

    chat = research.chat
    project = getattr(chat, 'project', None)
    network = chat.network
    model_name = network.model_name if network else 'claude-3-5-sonnet-20241022'
    question = research.question

    try:
        # Step 1: plan queries
        research.append_step('plan', f'Планирование поисковых запросов...')
        queries = _plan_research_queries(question, model_name, n=5)
        research.append_step('plan_done', f'Сгенерировано {len(queries)} подзапросов')

        # Step 2: parallel search
        from concurrent.futures import ThreadPoolExecutor, as_completed
        all_chunks = []
        completed_searches = 0

        def _search_one(q):
            try:
                kb = _kb_search_chunks(project, q, top_k=4)
                web = _web_search_chunks(q)
                return q, kb + web
            finally:
                from django.db import close_old_connections
                close_old_connections()

        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = {ex.submit(_search_one, q): q for q in queries}
            for fut in as_completed(futures):
                q, chunks = fut.result()
                completed_searches += 1
                all_chunks.extend(chunks)
                research.append_step(
                    'search',
                    f'Поиск {completed_searches}/{len(queries)}: «{q[:60]}» — {len(chunks)} источников',
                )

        # Step 3: dedup by text prefix
        seen = set()
        deduped = []
        for c in all_chunks:
            key = c['text'][:120].strip()
            if key and key not in seen:
                seen.add(key)
                deduped.append(c)
        deduped = deduped[:20]  # cap at 20 chunks
        research.append_step('dedup', f'Дедупликация: {len(deduped)} уникальных источников')

        # Step 4: synthesize
        research.append_step('synthesize', 'Синтез отчёта...')
        report_md = _synthesize_report(question, deduped, model_name)

        # Step 5: format and save to message
        formatted_html = CodeFormatter.format_ai_response(report_md)
        if research.message:
            research.message.content = formatted_html
            research.message.plain_text = report_md
            research.message.status = 'completed'
            research.message.save(update_fields=['content', 'plain_text', 'status'])

        research.status = 'done'
        research.finished_at = timezone.now()
        research.append_step('done', 'Исследование завершено')
        research.save(update_fields=['status', 'finished_at'])

        # U3: компаундинг — автосохранение отчёта в базу знаний проекта
        try:
            if (project is not None and getattr(project, 'auto_save_research', False)
                    and getattr(settings, 'RESEARCH_TO_KB', True)):
                save_research_to_kb(research.id)
        except Exception as e:
            logger.warning(f'[deep_research] auto-save to KB failed: {e}')

    except Exception as e:
        logger.error(f"[deep_research] task {research_id} failed: {e}", exc_info=True)
        research.status = 'error'
        research.error = str(e)
        research.finished_at = timezone.now()
        research.save(update_fields=['status', 'error', 'finished_at'])
