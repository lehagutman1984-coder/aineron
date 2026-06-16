import re
from .base import BaseAgent, MODEL_FAST, MODEL_SMART

CODER_SYSTEM = (
    "Ты senior-разработчик. Реализуй ОДИН шаг из COMMITS.md. "
    "Верни СТРОГО JSON: {\"files\": {\"относительный/путь\": \"полное содержимое файла\"}}. "
    "Пиши полные файлы целиком, не диффы. Учитывай существующие файлы (даны в контексте)."
)

_COMPLEX_KEYWORDS = (
    'архитектур', 'рефакт', 'оптимиз', 'auth', 'авторизац',
    'security', 'безопасн', 'deploy', 'инфраструктур',
    'database', 'schema', 'мигра', 'middleware',
)


def _pick_model(step_text: str) -> str:
    if '[COMPLEX]' in step_text:
        return MODEL_SMART
    lower = step_text.lower()
    if len(step_text) > 600 or any(kw in lower for kw in _COMPLEX_KEYWORDS):
        return MODEL_SMART
    return MODEL_FAST


def _select_context_files(step_text: str, existing_files: dict) -> dict:
    """Return up to 8 files explicitly mentioned in the step text (by path or backtick)."""
    mentioned = [p for p in existing_files if p in step_text]
    for token in re.findall(r'`([^`]+)`', step_text):
        if token in existing_files and token not in mentioned:
            mentioned.append(token)
    return {p: existing_files[p] for p in mentioned[:8]}


class CoderAgent(BaseAgent):
    name = 'coder'
    model = MODEL_FAST
    last_model: str = MODEL_FAST

    def run(self, step_index: int, step_text: str, existing_files: dict,
            allowed_files: list = None) -> dict:
        model = _pick_model(step_text)
        self.last_model = model
        full = _select_context_files(step_text, existing_files)
        listing = '\n'.join(f'- {p}' for p in existing_files) or '(пусто)'
        body = '\n'.join(f'### {p}\n```\n{c[:6000]}\n```' for p, c in full.items())
        user = (
            f"PROJECT.md:\n{self.project.project_md_content}\n\n"
            f"Шаг #{step_index}:\n{step_text}\n\n"
            f"Все файлы проекта:\n{listing}\n\n"
            f"Содержимое релевантных файлов:\n{body}"
        )
        data = self.run_json(CODER_SYSTEM, user, model=model, max_tokens=8192)
        files = data.get('files', {})
        if allowed_files:
            files = {p: c for p, c in files.items() if p in allowed_files}
        return files
