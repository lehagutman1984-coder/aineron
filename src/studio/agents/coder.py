import re
from .base import BaseAgent
from ..models_catalog import ESCALATION_MAP, MODEL_TIER

CODER_SYSTEM = (
    "You are a senior software engineer. Implement EXACTLY ONE step from COMMITS.md. "
    "Write production-ready code: type-safe, no TODO stubs, with error handling and loading states. "
    "For Vite projects: vite.config.ts MUST include server:{host:true,port:3000}. "
    "For Next.js projects: package.json dev script MUST be \"next dev -p 3000 -H 0.0.0.0\". "
    "Never invent nonexistent dependencies. Respect existing project files (provided in context) — "
    "do not duplicate or break them. If a FixPlan is provided, change ONLY the listed files. "
    "Return STRICTLY JSON: {\"files\":{\"relative/path\":\"full file content\"}} — whole files, never diffs. "
    "Code comments may be in Russian."
)


def _select_context_files(step_text: str, existing_files: dict) -> dict:
    """Return up to 8 files explicitly mentioned in the step text (by path or backtick)."""
    mentioned = [p for p in existing_files if p in step_text]
    for token in re.findall(r'`([^`]+)`', step_text):
        if token in existing_files and token not in mentioned:
            mentioned.append(token)
    return {p: existing_files[p] for p in mentioned[:8]}


class CoderAgent(BaseAgent):
    name = 'coder'
    last_model: str = ''

    def _pick_model(self, step_title: str) -> str:
        base = self.resolve_model()
        if '[COMPLEX]' in (step_title or '') and MODEL_TIER.get(base) == 'fast':
            return ESCALATION_MAP.get(base, base)
        return base

    def run(self, step_index: int, step_text: str, existing_files: dict,
            allowed_files: list = None) -> dict:
        model = self._pick_model(step_text)
        self.last_model = model
        full = _select_context_files(step_text, existing_files)
        listing = '\n'.join(f'- {p}' for p in existing_files) or '(пусто)'
        body = '\n'.join(f'### {p}\n```\n{c[:6000]}\n```' for p, c in full.items())
        user = (
            f"PROJECT.md:\n{self.project.project_md_content}\n\n"
            f"Step #{step_index}:\n{step_text}\n\n"
            f"All project files:\n{listing}\n\n"
            f"Content of relevant files:\n{body}"
        )
        data = self.run_json(CODER_SYSTEM, user, model=model, max_tokens=8192)
        files = data.get('files', {})
        if allowed_files:
            files = {p: c for p, c in files.items() if p in allowed_files}
        return files
