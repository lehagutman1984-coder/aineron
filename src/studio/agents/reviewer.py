from .base import BaseAgent, MODEL_SMART

REVIEWER_SYSTEM = (
    "Ты ревьюер кода. Проверь изменённые файлы на синтаксис, импорты, баги, соответствие шагу. "
    "Список всех файлов проекта — только для контекста; проверяй только раздел «Изменённые файлы». "
    "Верни СТРОГО JSON ReviewReport: "
    '{"passed": bool, "issues": [{"file": "...", "severity": "error|warning", "message": "..."}], "summary": "..."}.'
)


class ReviewerAgent(BaseAgent):
    name = 'reviewer'
    model = MODEL_SMART

    def run(self, step_text: str, files: dict, all_files: dict = None) -> dict:
        body = '\n'.join(f'### {p}\n{c}' for p, c in files.items())
        listing = '\n'.join(f'- {p}' for p in (all_files or {}) if p not in files) or ''
        ctx = f"\n\nВсе остальные файлы (только список):\n{listing}" if listing else ''
        user = f"Шаг:\n{step_text}\n\nИзменённые файлы:\n{body}{ctx}"
        report = self.run_json(REVIEWER_SYSTEM, user, model=MODEL_SMART, max_tokens=6000)
        report.setdefault('passed', not report.get('issues'))
        return report
