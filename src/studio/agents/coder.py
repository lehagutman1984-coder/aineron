import re
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import BaseAgent, get_client, pick_prompt
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
    "Ты senior-разработчик. Напиши ОДИН полный исходный файл целиком — не обрезай.\n"
    "Правила:\n"
    "- Файл на 100% полный: все JSX-теги закрыты, все функции закрыты, экспорт присутствует\n"
    "- Production-ready: без TODO, без заглушек, с обработкой ошибок и состояний загрузки\n"
    "- Next.js: 'use client' там где нужно; dev-скрипт: \"next dev -p 3000 -H 0.0.0.0\"\n"
    "- Vite/React: vite.config.ts с server:{host:true,port:3000,hmr:false}\n"
    "- Не выдумывай несуществующие зависимости\n"
    "- Выводи ТОЛЬКО содержимое файла — без markdown-блоков, без объяснений\n"
    "Код-комментарии можно на русском."
)

FILE_SYSTEM_EN = (
    "You are a senior software engineer. Write ONE complete source file — never truncate it.\n"
    "Rules:\n"
    "- 100% complete: all JSX tags closed, all functions closed, export default present\n"
    "- Production-ready: no TODO stubs, full error handling and loading states\n"
    "- Next.js: add 'use client' where needed; dev script: \"next dev -p 3000 -H 0.0.0.0\"\n"
    "- Vite/React: vite.config.ts with server:{host:true,port:3000,hmr:false}\n"
    "- Never invent nonexistent dependencies\n"
    "- Output ONLY the raw file content — no markdown fences, no explanations\n"
    "Code comments may be in Russian."
)

# Legacy single-call prompts (kept as fallback)
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
    if last in ('}', ';', '>', "'", '"', ')'):
        return False
    tail = s[-30:]
    if any(tail.endswith(kw) for kw in ('default', 'module.exports')):
        return False
    return True


def _select_context_files(step_text: str, existing_files: dict) -> dict:
    """Return up to 6 files explicitly mentioned in the step text."""
    mentioned = [p for p in existing_files if p in step_text]
    for token in re.findall(r'`([^`]+)`', step_text):
        if token in existing_files and token not in mentioned:
            mentioned.append(token)
    return {p: existing_files[p] for p in mentioned[:6]}


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from model output."""
    text = re.sub(r'^```[\w]*\n?', '', text.strip(), flags=re.MULTILINE)
    text = re.sub(r'\n?```\s*$', '', text, flags=re.MULTILINE)
    return text.strip()


def _make_agent(project) -> 'CoderAgent':
    """Create a fresh CoderAgent instance for use in a thread."""
    agent = object.__new__(CoderAgent)
    agent.project = project
    agent.client = get_client()
    agent.last_finish_reason = None
    agent.last_model = ''
    return agent


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
        system = pick_prompt(MANIFEST_SYSTEM_RU, MANIFEST_SYSTEM_EN)
        listing = '\n'.join(f'- {p}' for p in existing_files) or '(empty)'
        user = (
            f"PROJECT.md:\n{self.project.project_md_content[:2000]}\n\n"
            f"Step #{step_index}:\n{step_text}\n\n"
            f"Existing project files:\n{listing}"
        )
        try:
            data = self.run_json(system, user, model=model, max_tokens=800)
            raw = data.get('files', [])
            if isinstance(raw, list):
                return [str(f) for f in raw if f]
        except Exception as exc:
            log.warning('coder: manifest call failed (%s)', exc)
        return []

    # ── Phase 2: per-file generation ─────────────────────────────────────────

    def _generate_one_file(self, path: str, step_index: int, step_text: str,
                           existing_files: dict, model: str) -> str:
        """Generate a single file. Returns raw file content."""
        system = pick_prompt(FILE_SYSTEM_RU, FILE_SYSTEM_EN)

        existing_content = existing_files.get(path, '')
        existing_str = (
            f"\n\nCurrent content of {path} (replace/modify as needed):\n"
            f"```\n{existing_content[:5000]}\n```"
        ) if existing_content else ''

        context = _select_context_files(step_text, {k: v for k, v in existing_files.items() if k != path})
        context_str = '\n'.join(
            f'### {p}\n```\n{c[:3000]}\n```' for p, c in context.items()
        )
        listing = '\n'.join(f'- {p}' for p in existing_files) or '(empty)'

        user = (
            f"PROJECT.md:\n{self.project.project_md_content[:2000]}\n\n"
            f"Step #{step_index}:\n{step_text}\n\n"
            f"FILE TO WRITE: {path}{existing_str}\n\n"
            f"All project files (for reference):\n{listing}\n\n"
            f"Relevant file contents:\n{context_str}"
        )

        raw = self.run_prompt(system, user, model=model, max_tokens=24000, temperature=0.15)
        return _strip_fences(raw)

    def _generate_parallel(self, file_list: list[str], step_index: int, step_text: str,
                           existing_files: dict, model: str) -> dict:
        """Generate all files in file_list in parallel threads."""
        results: dict[str, str] = {}
        lock = threading.Lock()

        def gen(path: str):
            try:
                agent = _make_agent(self.project)
                content = agent._generate_one_file(
                    path, step_index, step_text, existing_files, model
                )
                if content:
                    with lock:
                        results[path] = content
                    log.info('coder: generated %s (%d chars)', path, len(content))
                else:
                    log.warning('coder: empty result for %s', path)
            except Exception as exc:
                log.error('coder: failed to generate %s: %s', path, repr(exc))

        workers = min(len(file_list), 5)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(gen, file_list))

        return results

    # ── Repair truncated files ────────────────────────────────────────────────

    def _repair_file(self, path: str, content: str, model: str) -> str | None:
        """Try to complete a truncated file."""
        try:
            tail = content[-800:]
            agent = _make_agent(self.project)
            completion = agent.run_prompt(
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

    # ── Legacy single-call fallback ───────────────────────────────────────────

    def _run_legacy(self, step_index: int, step_text: str,
                    existing_files: dict, model: str) -> dict:
        """Original single-call approach (fallback when manifest fails)."""
        system = pick_prompt(SYSTEM_RU, SYSTEM_EN)
        full = _select_context_files(step_text, existing_files)
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

        # Determine which files to generate
        if allowed_files:
            # Fix iteration: guardian already listed the exact files to fix
            file_list = allowed_files
            log.info('coder step %d (fix iter): %d files: %s',
                     step_index, len(file_list), file_list)
        else:
            # Normal iteration: ask model for the manifest
            file_list = self._get_manifest(step_index, step_text, existing_files, model)
            if not file_list:
                log.warning('coder step %d: empty manifest — falling back to legacy', step_index)
                return self._run_legacy(step_index, step_text, existing_files, model)
            log.info('coder step %d: manifest %s', step_index, file_list)

        # Generate all files in parallel
        results = self._generate_parallel(file_list, step_index, step_text, existing_files, model)

        if not results:
            log.warning('coder step %d: parallel generation returned nothing — fallback', step_index)
            return self._run_legacy(step_index, step_text, existing_files, model)

        # Repair any still-truncated files
        for path, content in list(results.items()):
            if _is_truncated(content):
                log.warning('coder: %s truncated even in per-file mode — repairing', path)
                repaired = self._repair_file(path, content, model)
                if repaired:
                    results[path] = repaired

        return results
