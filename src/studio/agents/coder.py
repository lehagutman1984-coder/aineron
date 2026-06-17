import re
import logging

from .base import BaseAgent, pick_prompt
from ..models_catalog import ESCALATION_MAP, MODEL_TIER

log = logging.getLogger('studio.agents')

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
        if '[COMPLEX]' in (step_title or '') and MODEL_TIER.get(base) == 'fast':
            return ESCALATION_MAP.get(base, base)
        return base

    # ── Phase 1: manifest ─────────────────────────────────────────────────────

    def _get_manifest(self, step_index: int, step_text: str,
                      existing_files: dict, model: str) -> list[str]:
        """Quick call: ask the model which files this step creates/modifies."""
        self.log('Определяю список файлов для генерации...')
        system = pick_prompt(MANIFEST_SYSTEM_RU, MANIFEST_SYSTEM_EN)
        listing = '\n'.join(f'- {p}' for p in existing_files) or '(empty)'
        user = (
            f"PROJECT.md:\n{self.project.project_md_content[:3000]}\n\n"
            f"Step #{step_index}:\n{step_text}\n\n"
            f"Existing project files:\n{listing}"
        )
        try:
            data = self.run_json(system, user, model=model, max_tokens=1200)
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
        system = pick_prompt(FILE_SYSTEM_RU, FILE_SYSTEM_EN)

        existing_content = existing_files.get(path, '')
        existing_str = (
            f"\n\nCurrent content of {path} (modify/replace as needed):\n"
            f"```\n{existing_content[:6000]}\n```"
        ) if existing_content else ''

        # Include relevant context files (excluding target file)
        context = _select_context_files(
            step_text, {k: v for k, v in existing_files.items() if k != path}, max_files=8
        )
        context_str = '\n'.join(
            f'### {p}\n```\n{c[:3000]}\n```' for p, c in context.items()
        )
        listing = '\n'.join(f'- {p}' for p in existing_files) or '(empty)'

        user = (
            f"PROJECT.md:\n{self.project.project_md_content[:4000]}\n\n"
            f"Step #{step_index}:\n{step_text}\n\n"
            f"FILE TO WRITE: {path}{existing_str}\n\n"
            f"All project files (for reference):\n{listing}\n\n"
            f"Relevant file contents:\n{context_str}"
        )

        raw = self.run_prompt(system, user, model=model, max_tokens=24000, temperature=0.15)
        content = _strip_fences(raw)

        if self.last_finish_reason == 'length':
            self.log(f'ВНИМАНИЕ: {path} достиг лимита токенов — файл может быть неполным', level='warning')
            log.warning('coder: %s hit token limit (finish_reason=length)', path)

        return content

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

    # ── Repair truncated files ────────────────────────────────────────────────

    def _repair_file(self, path: str, content: str, model: str) -> str | None:
        """Try to complete a truncated file."""
        self.log(f'Файл {path} обрезан — починяю...', level='warning')
        try:
            tail = content[-800:]
            completion = self.run_prompt(
                "A code file was cut off mid-generation. "
                "Output ONLY the missing closing code to make it syntactically complete. "
                "No markdown fences, no explanations, no repeating existing code.",
                f"File: {path}\n\nEnds abruptly:\n...{tail}\n\nProvide only the missing part:",
                model=model,
                max_tokens=4000,
                temperature=0.1,
            )
            completion = _strip_fences(completion)
            if completion:
                return content.rstrip() + '\n' + completion
        except Exception as exc:
            log.warning('coder: repair failed for %s: %s', path, exc)
        return None

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
        data = self.run_json(system, user, model=model, max_tokens=24000)
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

        # Fix iteration: guardian specified exact files → per-file with full context
        if allowed_files:
            self.log(f'Исправляю {len(allowed_files)} файлов: {", ".join(allowed_files)}')
            log.info('coder step %d fix iter: %d files: %s',
                     step_index, len(allowed_files), allowed_files)
            results = self._generate_files(allowed_files, step_index, step_text, existing_files, model)
            if not results:
                self.log('Per-file генерация ничего не вернула — пробую одиночный запрос', level='warning')
                return self._run_legacy(step_index, step_text, existing_files, model)
            for path, content in list(results.items()):
                if _is_truncated(content):
                    repaired = self._repair_file(path, content, model)
                    if repaired:
                        results[path] = repaired
            self.log(f'Готово: {len(results)} файлов')
            return results

        # Normal iteration: single-call with full context (streaming prevents HTTP timeout)
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

        # Fallback: manifest + per-file generation
        file_list = self._get_manifest(step_index, step_text, existing_files, model)
        if not file_list:
            self.log('Манифест пустой — повторяю одиночный запрос', level='warning')
            log.warning('coder step %d: empty manifest — retrying legacy', step_index)
            return self._run_legacy(step_index, step_text, existing_files, model)

        results = self._generate_files(file_list, step_index, step_text, existing_files, model)
        if not results:
            self.log('Per-file генерация ничего не вернула — повторяю одиночный запрос', level='warning')
            return self._run_legacy(step_index, step_text, existing_files, model)

        for path, content in list(results.items()):
            if _is_truncated(content):
                repaired = self._repair_file(path, content, model)
                if repaired:
                    results[path] = repaired

        self.log(f'Готово (per-file): {len(results)} файлов')
        return results
