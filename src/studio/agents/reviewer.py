from .base import BaseAgent, MODEL_SMART

REVIEWER_SYSTEM = (
    "Ты ревьюер кода. Проверь файлы на синтаксис, импорты, баги, соответствие шагу. "
    "Верни СТРОГО JSON ReviewReport: "
    '{"passed": bool, "issues": [{"file": "...", "severity": "error|warning", "message": "..."}], "summary": "..."}.'
)


class ReviewerAgent(BaseAgent):
    name = 'reviewer'
    model = MODEL_SMART

    def run(self, step_text: str, files: dict) -> dict:
        body = '\n'.join(f'### {p}\n{c}' for p, c in files.items())
        user = f"Шаг:\n{step_text}\n\nФайлы:\n{body}"
        report = self.run_json(REVIEWER_SYSTEM, user, model=MODEL_SMART, max_tokens=6000)
        report.setdefault('passed', not report.get('issues'))
        return report
