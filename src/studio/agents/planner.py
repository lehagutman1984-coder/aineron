import re

from .base import BaseAgent, MODEL_SMART

PLANNER_SYSTEM = (
    "Ты планировщик. На основе PROJECT.md составь COMMITS.md — пошаговый план реализации. "
    "Каждый шаг (commit) атомарный, с заголовком и списком создаваемых/изменяемых файлов. "
    "Помечай заголовок шага тегом [COMPLEX], если шаг включает auth, оплату, "
    "интеграции, realtime, миграции БД или затрагивает 5+ файлов. "
    "Например: ## [COMPLEX] Настройка аутентификации. "
    "В КОНЦЕ документа верни строку-маркер: <STEPS_COUNT>N</STEPS_COUNT>, где N — число шагов. "
    "Markdown на русском, без преамбулы."
)


class PlannerAgent(BaseAgent):
    name = 'planner'
    model = MODEL_SMART

    def run(self) -> tuple:
        self.log('Составляю план реализации...')
        user = f"PROJECT.md:\n\n{self.project.project_md_content}"
        md_raw = self.run_prompt(PLANNER_SYSTEM, user, model=MODEL_SMART, max_tokens=8192)
        m = re.search(r'<STEPS_COUNT>(\d+)</STEPS_COUNT>', md_raw)
        marker = int(m.group(1)) if m else 0
        md = re.sub(r'<STEPS_COUNT>\d+</STEPS_COUNT>', '', md_raw).strip()
        from ..tasks import _split_steps
        steps = len(_split_steps(md)) or marker or 5
        if steps > 15:
            self.log(f'Предупреждение: план содержит {steps} шагов (рекомендуется ≤15)', level='warning')
        self.project.commits_md_content = md
        self.project.save(update_fields=['commits_md_content'])
        self.log(f'COMMITS.md готов: {steps} шагов')
        return md, steps
