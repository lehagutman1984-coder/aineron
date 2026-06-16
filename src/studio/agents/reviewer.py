from .base import BaseAgent, pick_prompt

SYSTEM_RU = (
    "Ты ревьюер кода уровня senior. Проверь ТОЛЬКО изменённые файлы. "
    "Проверяй: синтаксис и типы, корректность импортов, соответствие шагу, явные баги, "
    "БЕЗОПАСНОСТЬ (XSS, инъекции, секреты в коде, dangerouslySetInnerHTML/eval, открытые CORS). "
    "severity=error — блокирует; severity=warning — желательно. "
    "Верни СТРОГО JSON: {\"passed\":bool,\"issues\":[{\"file\":\"...\",\"severity\":\"error|warning\",\"message\":\"...\"}],\"summary\":\"...\"}. "
    "summary — на русском."
)

SYSTEM_EN = (
    "You are a senior code reviewer. Review ONLY the changed files. "
    "Check: syntax and types, import correctness and paths, conformance to the step, "
    "obvious bugs and edge cases, SECURITY (XSS, injection, secrets in code, "
    "unsafe dangerouslySetInnerHTML/eval, permissive CORS). "
    "severity=error blocks; severity=warning is advisory. "
    "Return STRICTLY JSON: {\"passed\":bool,\"issues\":[{\"file\":\"...\",\"severity\":\"error|warning\",\"message\":\"...\"}],\"summary\":\"...\"}. "
    "The \"summary\" and \"message\" text MUST be in Russian."
)


class ReviewerAgent(BaseAgent):
    name = 'reviewer'

    def run(self, step_text: str, files: dict, all_files: dict = None) -> dict:
        system = pick_prompt(SYSTEM_RU, SYSTEM_EN)
        body = '\n'.join(f'### {p}\n{c}' for p, c in files.items())
        listing = '\n'.join(f'- {p}' for p in (all_files or {}) if p not in files) or ''
        ctx = f"\n\nAll other files (list only):\n{listing}" if listing else ''
        user = f"Step:\n{step_text}\n\nChanged files:\n{body}{ctx}"
        report = self.run_json(system, user, model=self.resolve_model(), max_tokens=6000)
        report.setdefault('passed', not report.get('issues'))
        return report
